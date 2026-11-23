#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Real Chromium + HTTPS + WSGI + SQLite test. No Linux service simulation.
Requires playwright and Chromium. Screenshots are temporary QA output only.
"""
import io
import os
import json
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
import wave
import zlib
import struct
from wsgiref.simple_server import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from agent.files import operate
from agent.file_tools import NOFOLLOW_DIR
from backend import core as c
from backend.app import application
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass
with tempfile.TemporaryDirectory() as temp:
    c.STATE=Path(temp)/'state';c.initialize()
    cert=Path(temp)/'cert.pem';key=Path(temp)/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(key),'-out',str(cert),'-subj','/CN=localhost'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    server=make_server('127.0.0.1',0,application,handler_class=Quiet)
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key)
    server.socket=ctx.wrap_socket(server.socket,server_side=True)
    origin=f'https://localhost:{server.server_port}'
    os.environ['ALMA_ORIGIN']=origin
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000})
            page=context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin)
            page.get_by_role('button',name='First installation? Set up administrator').click()
            password=secrets.token_urlsafe(24)
            page.locator('#login-form input[name=username]').fill('browseradmin')
            page.locator('#login-form input[name=password]').fill(password)
            page.locator('#login-form input[name=token]').fill((c.STATE/'setup-token').read_text())
            page.get_by_role('button',name='Create administrator',exact=True).click()
            page.get_by_role('button',name='Sign in',exact=True).wait_for()
            page.get_by_role('button',name='Sign in',exact=True).click()
            page.locator('#main h1').filter(has_text='Dashboard').wait_for()

            def open_tool(href):
                # Secondary tools live in dashboard groups rather than the short sidebar.
                page.locator('#nav a[href="#dashboard"]').click()
                page.locator(f'.tool[href="#{href}"]').click()

            def qa_shot(name):
                if os.environ.get('ALMA_QA_DIR'):
                    page.screenshot(path=str(Path(os.environ['ALMA_QA_DIR']) / f'{name}.png'))

            def sidebar_links():
                return page.locator('#nav a').evaluate_all('links => links.map(a => a.textContent.trim())')

            assert sidebar_links() == ['Dashboard', 'Hosting Accounts', 'File Manager', 'Domains', 'Preferences']
            open_tool('packages')
            page.locator('#package-form input[name=name]').fill('Browser package')
            page.locator('#package-form input[name=max_domains]').fill('3')
            page.get_by_role('button',name='Create package',exact=True).click()
            page.get_by_role('cell',name='Browser package',exact=True).wait_for()
            with c.connect() as db:
                actor = db.execute("SELECT id FROM users WHERE username='browseradmin'").fetchone()[0]
                package = db.execute("SELECT id FROM packages WHERE name='Browser package'").fetchone()[0]
                db.execute("""INSERT INTO accounts(user_id,name,owner_id,package_id,state,created)
                              VALUES(?, 'browserhost', ?, ?, 'active', 0)""", (actor, actor, package))
                user = db.execute("""INSERT INTO users(username,password,role,owner_id,enabled,created)
                    VALUES('retryhost',?,'user',?,0,0)""", (c.password_hash(password), actor)).lastrowid
                failed = db.execute("""INSERT INTO accounts(user_id,name,owner_id,package_id,state,created)
                    VALUES(?,'retryhost',?,?,'failed',0)""", (user, actor, package)).lastrowid
                db.execute("""INSERT INTO jobs(actor_id,account_id,operation,payload,state,created)
                    VALUES(?,?,'account.create','{}','failed',0)""", (actor, failed))
            def browser_mail(route):
                if route.request.method == 'GET':
                    route.fulfill(json={'available': True, 'hostname': 'mail.example.com', 'listen': 'loopback',
                                        'domains': ['example.com'], 'mailboxes': [], 'forwarders': []})
                else:
                    body = route.request.post_data_json
                    assert body['action'] == 'create' and body['address'] == 'hello@example.com'
                    assert body['quota_mib'] == 32
                    route.fulfill(json={'message': 'Mail configuration saved.'})
            page.route('**/api/accounts/*/mail', browser_mail)
            page.reload()
            page.get_by_role('link', name='Hosting Accounts', exact=True).click()
            page.get_by_role('row').filter(has_text='retryhost').get_by_role('button', name='Retry setup').click()
            page.get_by_role('button', name='Confirm', exact=True).click()
            page.get_by_role('heading', name='Operation history').wait_for()
            page.get_by_role('cell', name='queued', exact=True).wait_for()
            with c.connect() as db:
                queued = db.execute('SELECT payload FROM jobs WHERE account_id=? AND state=\'queued\'', (failed,)).fetchone()
                assert json.loads(queued['payload']) == {'name': 'retryhost', 'retry': True}
            open_tool('mail')
            page.get_by_role('heading',name='Email Accounts').wait_for()
            page.get_by_text('Mail listeners accept only local connections.',exact=False).wait_for()
            page.locator('#mail-create [name=local]').fill('hello')
            page.locator('#mail-create [name=password]').fill(password)
            page.locator('#mail-create [name=quota_mib]').fill('32')
            page.get_by_role('button',name='Create mailbox',exact=True).click()
            page.get_by_text('Mail configuration saved.',exact=True).wait_for()
            website = Path(temp) / 'website'
            private = Path(temp) / 'private'
            website.mkdir()
            (private / 'backups').mkdir(parents=True)
            (private / 'trash').mkdir()
            (website / 'page.html').write_text('Back up this page.')

            other_operations = c.rpc

            def local_files(operation, **args):
                if args.get('name') != 'browserhost' or operation not in ('files', 'account.stats'):
                    return other_operations(operation, **args)
                if operation == 'account.stats':
                    return {'disk_bytes': sum(item.stat().st_size for item in website.rglob('*') if item.is_file())}
                root = os.open(website, NOFOLLOW_DIR)
                state = os.open(private, NOFOLLOW_DIR)
                try:
                    return operate(root, args['request'], state)
                except (OSError, ValueError) as error:
                    raise c.Problem(str(error), 502) from error
                finally:
                    os.close(state)
                    os.close(root)

            file_fixture = patch.object(c, 'rpc', side_effect=local_files)
            file_fixture.start()
            open_tool('backups')
            page.get_by_role('button',name='Create website backup').click()
            page.get_by_role('button',name='Browse files').click()
            page.get_by_role('cell',name='page.html').wait_for()
            page.get_by_role('button',name='Verify archive').click()
            page.get_by_text('ZIP integrity check passed. 1 file checked.',exact=True).wait_for()
            page.get_by_role('button',name='Restore file',exact=True).click()
            page.get_by_role('textbox',name='New path under public_html').fill('recovered.html')
            page.get_by_role('button',name='Restore to path').click()
            page.get_by_text('Restored to recovered.html.',exact=True).wait_for()
            assert (website / 'recovered.html').read_text() == 'Back up this page.'

            (website / 'assets' / 'icons').mkdir(parents=True)
            (website / '.settings').write_text('visible when requested')
            page.locator('#nav a[href="#files"]').click()
            page.get_by_text('used in this account', exact=False).wait_for()
            page.get_by_role('checkbox', name='Show hidden files').check()
            page.get_by_role('button', name='.settings', exact=True).wait_for()
            page.get_by_role('checkbox', name='Show hidden files').uncheck()
            page.get_by_role('button', name='.settings', exact=True).wait_for(state='hidden')
            tree = page.get_by_role('navigation', name='Folder tree')
            tree.get_by_role('button', name='Expand assets', exact=True).click()
            tree.get_by_role('button', name='icons', exact=True).click()
            page.get_by_role('navigation', name='Current folder').get_by_role('button', name='icons').wait_for()

            big_file = b'a' * 520000 + b'b' * 600000
            php = b'\xef\xbb\xbf<?php\r\necho "before";\r\n'
            page.locator('#upload').set_input_files([
                {'name': 'large.bin', 'mimeType': 'application/octet-stream', 'buffer': big_file},
                {'name': 'file.php', 'mimeType': 'text/plain', 'buffer': php},
            ])
            page.get_by_text('file.php · Uploaded', exact=True).wait_for()
            folder = website / 'assets' / 'icons'
            assert (folder / 'large.bin').read_bytes() == big_file
            with page.expect_download() as download:
                page.get_by_role('combobox', name='Action for large.bin').select_option('download')
            assert download.value.path().read_bytes() == big_file
            dropped = page.evaluate_handle('''() => {
                const transfer = new DataTransfer();
                transfer.items.add(new File(['dropped'], 'drop.txt', {type: 'text/plain'}));
                return transfer;
            }''')
            page.locator('#drop-files').dispatch_event('drop', {'dataTransfer': dropped})
            page.get_by_text('drop.txt · Uploaded', exact=True).wait_for()
            assert (folder / 'drop.txt').read_text() == 'dropped'

            page.get_by_role('button', name='file.php', exact=True).click()
            page.locator('.source-editor .code-keyword').filter(has_text='echo').wait_for()
            page.get_by_role('textbox', name='File contents').fill('<?php\necho "after";\n')
            page.get_by_role('button', name='Save file', exact=True).click()
            page.locator('[data-editor-status]').get_by_text('File saved.', exact=True).wait_for()
            assert (folder / 'file.php').read_bytes() == php.replace(b'before', b'after')
            page.get_by_role('button', name='Close file', exact=True).click()
            page.get_by_role('button', name='New file', exact=True).click()
            dialog = page.get_by_role('dialog', name='New file', exact=True)
            dialog.get_by_role('textbox', name='Name', exact=True).fill('created.txt')
            dialog.get_by_role('button', name='Open editor', exact=True).click()
            page.get_by_role('textbox', name='File contents').fill('created by File Manager')
            page.get_by_role('button', name='Save file', exact=True).click()
            page.locator('[data-editor-status]').get_by_text('File saved.', exact=True).wait_for()
            assert (folder / 'created.txt').read_text() == 'created by File Manager'
            page.get_by_role('button', name='Close file', exact=True).click()
            page.get_by_role('navigation', name='Current folder').get_by_role('button', name='public_html').click()
            page.locator('#file-crumbs [aria-current=page]').get_by_text('public_html', exact=True).wait_for()
            page.get_by_role('searchbox', name='Search this folder and its subfolders').fill('created')
            page.get_by_role('button', name='Search', exact=True).click()
            page.get_by_role('cell', name='assets/icons/created.txt', exact=True).wait_for()
            page.get_by_role('textbox', name='Folder path').fill('assets/icons')
            page.get_by_role('button', name='Go', exact=True).click()
            page.get_by_role('combobox', name='Action for file.php').select_option('mode')
            page.get_by_role('group', name='Owner').get_by_role('checkbox', name='Execute').check()
            page.get_by_role('button', name='Save permissions', exact=True).click()
            page.get_by_role('dialog', name='Change permissions').wait_for(state='hidden')
            assert (folder / 'file.php').stat().st_mode & 0o100

            page.get_by_role('combobox', name='Action for file.php').select_option('copy')
            dialog = page.get_by_role('dialog', name='Copy file.php')
            dialog.get_by_role('textbox', name='Name', exact=True).fill('copied.php')
            dialog.get_by_role('button', name='Copy', exact=True).click()
            page.get_by_role('combobox', name='Action for copied.php').select_option('rename')
            dialog = page.get_by_role('dialog', name='Move or rename copied.php')
            dialog.get_by_text('Browse folders', exact=True).click()
            dialog.get_by_role('button', name='public_html', exact=True).click()
            dialog.get_by_role('textbox', name='Name', exact=True).fill('moved.php')
            dialog.get_by_role('button', name='Move', exact=True).click()
            dialog.wait_for(state='hidden')
            assert (website / 'moved.php').is_file() and not (folder / 'copied.php').exists()

            page.get_by_role('combobox', name='Action for file.php').select_option('archive')
            page.get_by_role('dialog').get_by_role('button', name='Create ZIP', exact=True).click()
            page.get_by_role('button', name='file.php.zip', exact=True).click()
            page.get_by_text('1 file in this ZIP', exact=True).wait_for()
            page.get_by_role('combobox', name='Action for file.php.zip').select_option('extract')
            dialog = page.get_by_role('dialog', name='Extract file.php.zip')
            dialog.get_by_role('textbox', name='Name', exact=True).fill('unpacked')
            dialog.get_by_role('button', name='Extract', exact=True).click()
            dialog.wait_for(state='hidden')
            assert (folder / 'unpacked' / 'file.php').read_bytes() == (folder / 'file.php').read_bytes()

            def png_chunk(kind, data):
                return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))

            picture = b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            picture += png_chunk(b'IDAT', zlib.compress(b'\0\1\2\3')) + png_chunk(b'IEND', b'')
            (folder / 'photo.png').write_bytes(picture)
            audio = io.BytesIO()
            with wave.open(audio, 'wb') as wav:
                wav.setparams((1, 1, 8000, 0, 'NONE', 'not compressed'))
                wav.writeframes(bytes([128]) * 800)
            (folder / 'tone.wav').write_bytes(audio.getvalue())
            page.get_by_role('button', name='Reload', exact=True).click()
            page.get_by_role('button', name='photo.png', exact=True).click()
            page.get_by_role('spinbutton', name='Width (pixels)').fill('3')
            page.get_by_role('combobox', name='Output format').select_option('webp')
            page.get_by_role('button', name='Save image copy', exact=True).click()
            page.get_by_text('Image saved.', exact=True).wait_for()
            assert (folder / 'photo-resized.webp').read_bytes()[8:12] == b'WEBP'
            assert (folder / 'photo.png').read_bytes() == picture
            page.get_by_role('button', name='tone.wav', exact=True).click()
            page.wait_for_function("() => document.querySelector('audio')?.readyState >= 1")

            page.get_by_role('combobox', name='Action for drop.txt').select_option('trash')
            page.get_by_role('button', name='Confirm', exact=True).click()
            page.get_by_role('button', name='drop.txt', exact=True).wait_for(state='hidden')
            page.get_by_role('link', name='Trash', exact=True).click()
            page.get_by_role('button', name='Restore', exact=True).click()
            page.get_by_role('button', name='Restore entry', exact=True).click()
            page.get_by_text('Entry restored.', exact=True).wait_for()
            assert (folder / 'drop.txt').read_text() == 'dropped'
            page.set_viewport_size({'width': 412, 'height': 860})
            page.evaluate("() => { location.hash = 'files'; }")
            page.get_by_role('heading', name='File Manager', exact=True).wait_for()
            assert page.evaluate('() => document.documentElement.scrollWidth === document.documentElement.clientWidth')
            page.set_viewport_size({'width': 1440, 'height': 1000})
            file_fixture.stop()
            offsite_status = {'state': 'succeeded', 'message': 'Encrypted website snapshot saved.'}

            def browser_offsite(route):
                if route.request.method == 'POST':
                    offsite_status.update(state='running', message='Uploading encrypted website archives.',
                                          completed=1, total=1, updated_at=100)
                    route.fulfill(json={'message': 'Off-site backup requested.'})
                else:
                    route.fulfill(json=offsite_status)

            page.route('**/api/offsite-backups', browser_offsite)
            open_tool('offsite-backups')
            page.get_by_role('heading',name='Off-site backups',exact=True).wait_for()
            page.get_by_role('button',name='Run backup').click()
            page.get_by_text('Off-site backup requested.',exact=True).wait_for()
            page.get_by_role('progressbar',name='Backup items prepared').wait_for()
            host = 'site.example.com'
            page.route('**/api/accounts/*/domains', lambda route: route.fulfill(
                json=[{'name': host, 'state': 'active'}]))
            page.route('**/api/accounts/*/dns?domain=*', lambda route: route.fulfill(
                json={'available': True, 'active': True, 'nameservers': ['ns1.example.com'], 'records': []}))
            open_tool('dns')
            importer = page.locator('#zone-import')
            sample = {'format': 1, 'domain': 'another.example.com', 'serial': 1234,
                      'records': [{'name': '@', 'type': 'A', 'value': '192.0.2.10', 'ttl': 3600}]}
            importer.set_input_files({'name': 'records.json', 'mimeType': 'application/json',
                                      'buffer': json.dumps(sample).encode()})
            page.get_by_text('Select the domain named in this DNS backup.',exact=True).wait_for()
            sample['domain'] = host
            importer.set_input_files({'name': 'records.json', 'mimeType': 'application/json',
                                      'buffer': json.dumps(sample).encode()})
            page.get_by_role('cell',name='192.0.2.10',exact=True).wait_for()
            page.get_by_text('Records loaded into the draft.',exact=False).wait_for()
            # Compact navigation: dashboard groups, search, breadcrumbs, active state and layout.
            page.get_by_role('link',name='Dashboard',exact=True).click()
            page.get_by_role('heading',name='Dashboard',exact=True).wait_for()
            groups = page.locator('.tool-groups .section h2').evaluate_all(
                'items => items.map(h => h.firstChild.textContent.trim())')
            assert groups == ['Hosting Management', 'Files', 'Domains', 'Databases', 'Email', 'Software', 'Metrics',
                              'Advanced', 'Security', 'Account', 'Help', 'Server Administration'], groups
            total = page.locator('.tool').count()
            assert page.locator('#tool-count').inner_text() == f'{total} tools in 12 groups'
            page.locator('#search').fill('file manager')
            page.locator('.tool[href="#files"]').wait_for()
            assert page.locator('.tool').count()==1
            assert page.locator('#tool-count').inner_text() == f'1 of {total} tools match “file manager”'
            page.locator('#search').fill('advanced')  # category name only
            assert sorted(page.locator('.tool').evaluate_all('a => a.map(x => x.hash)')) == ['#cron', '#dns-lookup']
            page.locator('#search').fill('mariadb')  # description only
            assert page.locator('.tool').evaluate_all('a => a.map(x => x.hash)') == ['#databases']
            page.locator('#search').fill('no such hosting tool')
            page.get_by_role('heading', name='No tools match “no such hosting tool”').wait_for()
            page.get_by_role('button', name='Clear search', exact=True).click()
            assert page.locator('.tool').count() == total
            assert page.evaluate("document.activeElement.id") == 'search'
            page.locator('#search').fill('trash')
            page.keyboard.press('Escape')
            assert page.locator('.tool').count() == total
            page.locator('.tool[href="#availability"]').click()
            page.get_by_role('heading', name='Feature availability', exact=True).wait_for()
            crumbs = page.get_by_role('navigation', name='Breadcrumb')
            assert crumbs.locator('li').all_inner_texts() == ['Home', 'Help', 'Feature Availability'], crumbs.inner_text()
            assert page.title() == 'Feature Availability · almaPanel'
            assert 'active' in page.locator('#nav a[href="#dashboard"]').get_attribute('class')
            assert page.locator('#nav a[aria-current=page]').count() == 0
            page.locator('#nav a[href="#files"]').click()
            page.get_by_role('heading', name='File Manager', exact=True).wait_for()
            assert page.locator('#nav a[aria-current=page]').get_attribute('href') == '#files'
            assert 'active' not in (page.locator('#nav a[href="#dashboard"]').get_attribute('class') or '')
            page.locator('#nav a[href="#dashboard"]').click()

            def layout_ok():
                return page.evaluate('''() => {
                    const grid = document.querySelector('.tool-groups').getBoundingClientRect();
                    const rows = {};
                    for (const s of document.querySelectorAll('.tool-groups .section')) {
                        const r = s.getBoundingClientRect(), top = Math.round(r.top);
                        (rows[top] ||= []).push({left: r.left, right: r.right, wide: s.classList.contains('wide')});
                    }
                    const list = Object.values(rows);
                    return {overflow: document.documentElement.scrollWidth > innerWidth, rows: list.length,
                            sections: list.flat().length, maxPerRow: Math.max(...list.map(r => r.length)),
                            // Each row starts at the left edge and ends at the right edge: no empty columns.
                            filled: list.every(r => Math.abs(Math.min(...r.map(x => x.left)) - grid.left) < 2
                                                 && Math.abs(Math.max(...r.map(x => x.right)) - grid.right) < 2),
                            wideAlone: list.every(r => !r.some(x => x.wide) || r.length === 1)};
                }''')

            for width in (1024, 1280, 1440, 1920):
                page.set_viewport_size({'width': width, 'height': 1000})
                result = layout_ok()
                # Smaller categories sit side by side; large ones span the row; no row leaves a gap.
                assert not result['overflow'] and result['filled'] and result['wideAlone'], (width, result)
                assert result['maxPerRow'] == (3 if width >= 1700 else 2), (width, result)
                assert result['rows'] < result['sections'], (width, result)
            qa_shot('dashboard-1920')
            page.set_viewport_size({'width': 800, 'height': 1000})
            result = layout_ok()
            assert not result['overflow'] and result['rows'] == result['sections'] and result['filled'], result
            page.set_viewport_size({'width': 1440, 'height': 1000})

            # Desktop collapse to an icon rail, persisted across reloads.
            assert page.locator('#menu').get_attribute('aria-expanded') == 'true'
            page.locator('#menu').click()
            assert 'collapsed' in page.locator('body').get_attribute('class')
            assert page.locator('#menu').get_attribute('aria-expanded') == 'false'
            page.wait_for_function("() => document.getElementById('sidebar').getBoundingClientRect().width <= 70")
            qa_shot('collapsed-1440')
            page.reload()
            page.get_by_role('heading', name='Dashboard', exact=True).wait_for()
            assert 'collapsed' in page.locator('body').get_attribute('class')
            page.get_by_role('link', name='File Manager', exact=True).click()
            page.get_by_role('heading', name='File Manager', exact=True).wait_for()
            page.get_by_role('button', name='Expand navigation').click()
            assert 'collapsed' not in page.locator('body').get_attribute('class')
            page.wait_for_function("() => document.getElementById('sidebar').getBoundingClientRect().width > 150")
            page.locator('#nav a[href="#preferences"]').click()
            page.get_by_role('heading',name='Two-factor authentication').wait_for()
            page.locator('#profile-form [name=display_name]').fill('Panel admin')
            page.get_by_role('button',name='Save contact information').click()
            page.get_by_text('Contact information saved.',exact=True).wait_for()
            open_tool('tokens')
            page.get_by_role('heading',name='API Tokens').wait_for()
            page.locator('#token-form [name=label]').fill('Browser check')
            page.locator('#token-form [name=password]').fill(password)
            page.get_by_role('button',name='Create token',exact=True).click()
            page.get_by_text('Save this token now').wait_for()
            assert page.locator('#token-confirmation input').input_value().startswith('alma_ro_')
            page.get_by_role('button',name='Done',exact=True).click()
            page.get_by_role('cell',name='Browser check',exact=True).wait_for()
            page.locator('#nav a[href="#dashboard"]').click()
            page.locator('#theme').click()
            assert 'dark' in page.locator('body').get_attribute('class')
            page.locator('#theme').click()
            if os.environ.get('ALMA_QA_SCREENSHOT'):page.screenshot(path=os.environ['ALMA_QA_SCREENSHOT'],full_page=True)
            # Mobile drawer: open, focus, Escape, scrim, link navigation and secondary tools from dashboard.
            page.set_viewport_size({'width':390,'height':844})
            assert not page.locator('#sidebar').is_visible()
            page.locator('#menu[aria-label="Open navigation"][aria-expanded=false]').wait_for()
            page.locator('#menu').click()
            page.locator('#sidebar').wait_for(state='visible')
            assert page.locator('#menu').get_attribute('aria-expanded') == 'true'
            assert page.evaluate("document.activeElement.getAttribute('href')") == '#dashboard'
            qa_shot('mobile-drawer')
            page.keyboard.press('Shift+Tab')  # focus stays inside the open drawer
            assert page.evaluate("document.getElementById('sidebar').contains(document.activeElement)")
            page.keyboard.press('Escape')
            page.locator('#sidebar').wait_for(state='hidden')
            assert page.evaluate("document.activeElement.id") == 'menu'
            page.locator('#menu').click()
            page.mouse.click(380, 400)  # scrim outside the drawer
            page.locator('#sidebar').wait_for(state='hidden')
            page.locator('#menu').click()
            page.locator('#sidebar').get_by_role('button', name='Close navigation').click()
            page.locator('#sidebar').wait_for(state='hidden')
            page.locator('#menu').click()
            page.locator('#nav a[href="#preferences"]').click()
            page.get_by_role('heading',name='Two-factor authentication').wait_for()
            page.locator('#sidebar').wait_for(state='hidden')
            page.locator('#menu').click()
            page.locator('#nav a[href="#dashboard"]').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('.tool[href="#about"]').click()
            page.get_by_role('heading',name='About almaPanel').wait_for()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('#logout').click()
            page.get_by_role('heading',name='Sign in to your account').wait_for()

            # Role-based sidebar and dashboard groups for resellers and hosting users.
            with c.connect() as db:
                for name, role in (('browserseller', 'reseller'), ('browseruser', 'user')):
                    db.execute("INSERT INTO users(username,password,role,owner_id,enabled,created) VALUES(?,?,?,?,1,0)",
                               (name, c.password_hash(password), role, actor))
            expected = {
                'browserseller': (['Dashboard', 'Hosting Accounts', 'File Manager', 'Domains', 'Preferences'], True),
                'browseruser': (['Dashboard', 'File Manager', 'Domains', 'Preferences'], False),
            }
            for name, (links, manages) in expected.items():
                page.locator('#login-form input[name=username]').fill(name)
                page.locator('#login-form input[name=password]').fill(password)
                page.get_by_role('button',name='Sign in',exact=True).click()
                page.get_by_role('heading', name='Dashboard', exact=True).wait_for()
                assert sidebar_links() == links, (name, sidebar_links())
                result = layout_ok()
                assert not result['overflow'] and result['filled'] and result['wideAlone'], (name, result)
                qa_shot(f'dashboard-{name}')
                headings = page.locator('.tool-groups .section h2').all_inner_texts()
                assert any(h.startswith('HOSTING MANAGEMENT') for h in headings) == manages, (name, headings)
                assert not any(h.startswith('SERVER ADMINISTRATION') for h in headings), (name, headings)
                for admin_only in ('system', 'audit', 'resellers', 'dns', 'offsite-backups'):
                    assert page.locator(f'.tool[href="#{admin_only}"]').count() == 0
                page.locator('#search').fill('resellers')
                page.get_by_role('heading', name='No tools match “resellers”').wait_for()
                page.locator('#search').fill('')
                page.locator('#logout').click()
                page.get_by_role('heading',name='Sign in to your account').wait_for()
            assert not errors, errors
            browser.close()
            print('Browser acceptance passed for compact role-based navigation, dashboard search and layout, desktop collapse, '
                  'mobile drawer focus handling, account setup and retry, file uploads/downloads, editing, ZIP, images, '
                  'Trash, mail, backups, DNS and preferences.')
    finally:
        server.shutdown();thread.join();os.environ.pop('ALMA_ORIGIN',None)
