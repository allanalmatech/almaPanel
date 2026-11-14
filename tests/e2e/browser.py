#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Real Chromium + HTTPS + WSGI + SQLite test. No Linux service simulation.
Requires playwright and Chromium. Screenshots are temporary QA output only.
"""
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
from wsgiref.simple_server import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
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
            page.locator('#main h1').filter(has_text='Tools').wait_for()
            page.get_by_role('link',name='Packages',exact=True).click()
            page.locator('#package-form input[name=name]').fill('Browser package')
            page.locator('#package-form input[name=max_domains]').fill('3')
            page.get_by_role('button',name='Create package',exact=True).click()
            page.get_by_role('cell',name='Browser package',exact=True).wait_for()
            page.get_by_role('link',name='Dashboard',exact=True).click()
            page.locator('#search').fill('file manager')
            page.locator('.tool[href="#files"]').wait_for()
            assert page.locator('.tool').count()==1
            page.locator('#search').fill('')
            page.locator('#nav a[href="#preferences"]').click()
            page.get_by_role('heading',name='Two-factor authentication').wait_for()
            page.locator('#profile-form [name=display_name]').fill('Panel admin')
            page.get_by_role('button',name='Save contact information').click()
            page.get_by_text('Contact information saved.',exact=True).wait_for()
            page.locator('#nav a[href="#tokens"]').click()
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
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#menu').click()
            page.locator('#nav a[href="#about"]').click()
            page.get_by_role('heading',name='About almaPanel').wait_for()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#logout').click()
            page.get_by_role('heading',name='Sign in to your account').wait_for()
            assert not errors, errors
            browser.close()
            print('Browser acceptance passed: setup, login, packages, search, profile, API tokens, theme, mobile navigation and logout; no page errors.')
    finally:
        server.shutdown();thread.join();os.environ.pop('ALMA_ORIGIN',None)
