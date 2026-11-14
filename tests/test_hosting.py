# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import base64
import os
from pathlib import Path
import stat
import secrets
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import zipfile

from agent import databases, deployments, dns, file_tools, metrics, php_settings, sftp_access, site_security, sites
from agent.files import operate
from backend import core as c, schedules, security
from tests import test_core
from worker.main import tick


class FileTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        self.root = directory / 'public_html'
        self.private = directory / 'private'
        self.root.mkdir()
        self.private.mkdir()
        (self.private / 'trash').mkdir()
        (self.private / 'backups').mkdir()
        self.webfd = os.open(self.root, file_tools.NOFOLLOW_DIR)
        self.privatefd = os.open(self.private, file_tools.NOFOLLOW_DIR)
        self.addCleanup(os.close, self.webfd)
        self.addCleanup(os.close, self.privatefd)

    def op(self, action, path='', **kwargs):
        return operate(self.webfd, {'action': action, 'path': path, **kwargs}, self.privatefd)

    def test_archive_round_trip_and_absolute_rejection(self):
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'test.txt').write_text('example')
        self.op('archive', 'src', destination='copy.zip')
        self.op('extract', 'copy.zip', destination='out')
        self.assertEqual((self.root / 'out' / 'test.txt').read_text(), 'example')
        with self.assertRaises(FileExistsError):
            self.op('extract', 'copy.zip', destination='out')
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['copy.zip', 'out', 'src'])

    def test_unsafe_zip_entries_clean_up_entire_staging_folder(self):
        for filename, mode in [('x/../../escaped', stat.S_IFREG), ('/outside.txt', stat.S_IFREG),
                               ('abc\\outside', stat.S_IFREG), ('link', stat.S_IFLNK)]:
            with self.subTest(filename=filename):
                with zipfile.ZipFile(self.root / 'bad.zip', 'w') as archive:
                    archive.writestr('okay.txt', 'not published')
                    entry = zipfile.ZipInfo(filename)
                    entry.external_attr = (mode | 0o600) << 16
                    archive.writestr(entry, 'content')
                with self.assertRaises(ValueError):
                    self.op('extract', 'bad.zip', destination='new')
                self.assertEqual(list(self.root.iterdir()), [self.root / 'bad.zip'])

    def test_archive_rejects_link_and_stops_at_size_budget(self):
        (self.root / 'input').mkdir()
        (self.root / 'input' / 'bad').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            self.op('archive', 'input', destination='unsafe.zip')
        with zipfile.ZipFile(self.root / 'large.zip', 'w') as archive:
            archive.writestr('file.txt', '12345')
        with self.assertRaises(ValueError):
            file_tools.extract_zip(self.webfd, ['large.zip'], self.webfd, ['too-large'], max_bytes=4)
        self.assertFalse((self.root / 'too-large').exists())

    def test_backup_schedule_retention_preserves_manual_backups(self):
        (self.root / 'index.html').write_text('manual version')
        manual = self.op('backup_create')['name']
        (self.root / 'index.html').write_text('first scheduled version')
        stale = self.op('backup_scheduled', retain=1)['name']
        (self.root / 'index.html').write_text('second scheduled version')
        latest = self.op('backup_scheduled', retain=1)['name']
        self.assertEqual({item['name'] for item in self.op('backups')}, {manual, latest})
        self.assertFalse((self.private / 'backups' / stale).exists())
        self.op('backup_restore', latest, destination='restore')
        self.assertEqual((self.root / 'restore' / 'index.html').read_text(), 'second scheduled version')

    def test_browse_verify_and_restore_file_from_an_existing_website_zip(self):
        target = self.root / 'docs'
        target.mkdir()
        (target / 'page.html').write_text('backup version')
        (target / 'other.html').write_text('other backed-up file')
        name = self.op('backup_create')['name']
        selected = self.op('backup_contents', name, query='PAGE')
        self.assertEqual(selected['entries'], [{'path': 'docs/page.html', 'size': 14}])
        self.assertEqual(self.op('backup_verify', name, revision=selected['revision'])['files'], 2)
        (target / 'page.html').write_text('live version')
        request = {'member': 'docs/page.html', 'revision': selected['revision']}
        with self.assertRaises(FileExistsError):
            self.op('backup_restore_file', name, destination='docs/page.html', **request)
        self.op('backup_restore_file', name, destination='docs/recovered.html', **request)
        self.assertEqual((target / 'page.html').read_text(), 'live version')
        self.assertEqual((target / 'recovered.html').read_text(), 'backup version')
        self.assertEqual(len(list(target.iterdir())), 3)

    def test_backup_listing_pages_and_rejects_restore_after_archive_replacement(self):
        name = 'website-0123456789abcdef.zip'
        archive_path = self.private / 'backups' / name
        with zipfile.ZipFile(archive_path, 'w') as archive:
            for index in range(file_tools.BACKUP_PAGE_SIZE + 1):
                archive.writestr(f'{index:03}.txt', b'original')
        first = self.op('backup_contents', name)
        second = self.op('backup_contents', name, offset=first['next_offset'], revision=first['revision'])
        self.assertEqual(len(first['entries']), file_tools.BACKUP_PAGE_SIZE)
        self.assertEqual(len(second['entries']), 1)
        self.assertIsNone(second['next_offset'])
        with zipfile.ZipFile(archive_path, 'w') as archive:
            archive.writestr('000.txt', b'changed')
        with self.assertRaisesRegex(ValueError, 'Backup changed'):
            self.op('backup_restore_file', name, member='000.txt', destination='recover.txt',
                    revision=first['revision'])
        self.assertFalse((self.root / 'recover.txt').exists())

    def test_corrupt_member_and_symlink_destination_leave_no_restore_output(self):
        name = 'scheduled-0123456789abcdef.zip'
        archive_path = self.private / 'backups' / name
        with zipfile.ZipFile(archive_path, 'w') as archive:
            archive.writestr('page.txt', b'unique-data')
        (self.root / 'outside').symlink_to(self.private)
        revision = self.op('backup_contents', name)['revision']
        with self.assertRaises(OSError):
            self.op('backup_restore_file', name, destination='outside/page.txt', member='page.txt', revision=revision)
        self.assertFalse((self.private / 'page.txt').exists())
        archive_path.write_bytes(archive_path.read_bytes().replace(b'unique-data', b'corrupt-dat'))
        revision = self.op('backup_contents', name)['revision']
        with self.assertRaisesRegex(ValueError, 'damaged'):
            self.op('backup_verify', name, revision=revision)
        with self.assertRaisesRegex(ValueError, 'damaged'):
            self.op('backup_restore_file', name, member='page.txt', destination='restore.txt', revision=revision)
        self.assertEqual([entry.name for entry in self.root.iterdir()], ['outside'])

    def test_trash_restore_cannot_overwrite(self):
        path = self.root / 'page.html'
        path.write_text('original')
        self.op('trash', 'page.html')
        entry = self.op('trash_list')[0]
        self.assertEqual(entry['path'], 'page.html')
        path.write_text('replacement')
        with self.assertRaises(FileExistsError):
            self.op('trash_restore', id=entry['id'], destination='page.html')
        self.op('trash_restore', id=entry['id'], destination='recovered.html')
        self.assertEqual(self.op('trash_list'), [])
        self.assertEqual(path.read_text(), 'replacement')

    def test_copy_and_search_do_not_follow_directory_symlinks(self):
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'target.txt').write_text('data')
        (self.root / 'untrusted').symlink_to(self.root / 'src')
        result = self.op('search', query='target')
        self.assertEqual([x['path'] for x in result['matches']], ['src/target.txt'])
        self.op('copy_tree', 'src', destination='clone')
        self.assertEqual((self.root / 'clone' / 'target.txt').read_text(), 'data')
        (self.root / 'src' / 'link').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            self.op('copy_tree', 'src', destination='rejected')
        self.assertFalse((self.root / 'rejected').exists())

    def test_create_upload_race_never_overwrites(self):
        (self.root / 'file').write_text('original')
        with self.assertRaises(FileExistsError):
            self.op('write', 'file', create_only=True, content=base64.b64encode(b'new').decode())
        self.assertEqual((self.root / 'file').read_text(), 'original')


class Validation(unittest.TestCase):
    def test_document_roots_and_aliases(self):
        with self.assertRaises(ValueError):
            sites.docroot('../other')
        with self.assertRaises(ValueError):
            sites.docroot('hello /etc/nginx')
        with self.assertRaises(ValueError):
            sites.settings({'domains': [], 'sites': {}}, 'alias.example.com',
                           {'kind': 'alias', 'target': 'other.example.com'})
        data = {'domains': ['main.example.com', 'alias.example.com'], 'sites': {
            'main.example.com': {'kind': 'site', 'root': 'www'},
            'alias.example.com': {'kind': 'alias', 'target': 'main.example.com'},
        }}
        config = sites.render(Path('/srv/almapanel/accounts'), '/run/php', 'hosting', 'alias.example.com', data)
        self.assertIn('root /srv/almapanel/accounts/hosting/public_html/www;', config)

    def test_dns_rejects_record_injection_and_cname_conflicts(self):
        for value in ['a\n@ IN NS wrong.example', 'a\x00b']:
            with self.assertRaises(ValueError):
                dns.records([{'name': '@', 'type': 'TXT', 'value': value}], 'example.com')
        with self.assertRaises(ValueError):
            dns.records([{'name': '@', 'type': 'CNAME', 'value': 'ago.example'}], 'example.com')
        with self.assertRaises(ValueError):
            dns.records([{'name': 'sub', 'type': 'AAAA', 'value': '192.0.2.2'}], 'example.com')
        result = dns.render('example.com', ['ns.example.com'], 1, dns.records([
            {'name': 'policy', 'type': 'TXT', 'value': 'escape "value"'}
        ], 'example.com'))
        self.assertIn(r'escape \"value\"', result)

    def test_tenant_database_generation_and_failure_redaction(self):
        self.assertNotEqual(databases.identifier('hosting', 'app'), databases.identifier('other', 'app'))
        for name in ['\x00bad', 'ab_;', 'a'*25]:
            with self.assertRaises(ValueError):
                databases.identifier('hosting', name)
        with patch.object(databases, 'installed', return_value=['mariadb']), patch.object(
            databases, 'create', side_effect=subprocess.CalledProcessError(1, ['command'], stderr='private')):
            with self.assertRaisesRegex(ValueError, '^Database server rejected') as error:
                databases.manage('database.create', 'hosting', {}, {'label':'app','engine':'mariadb'},
                                 Mock(), Mock())
            self.assertNotIn('private', str(error.exception))

    def test_git_ref_and_origin_validation(self):
        for repo in ['file:///home/test', 'https://github.com:443/a/b', 'https://user@github.com/a/b',
                     'https://evil.test/a/b', 'https://github.com/a/b?token=none']:
            with self.subTest(repo=repo), self.assertRaises(ValueError):
                deployments.source_repository(repo)
        self.assertEqual(deployments.source_repository('https://github.com/org/project'),
                         'https://github.com/org/project.git')
        with self.assertRaises(ValueError):
            deployments.branch_name('--help')
        self.assertEqual(deployments.branch_name('feature/site'), 'feature/site')

    def test_sftp_stores_only_valid_public_keys_and_disables_suspended_users(self):
        key = 'ssh-ed25519 ' + base64.b64encode(sftp_access.ED25519 + secrets.token_bytes(32)).decode()
        with tempfile.TemporaryDirectory() as temporary:
            keys = Path(temporary)
            profile = {'listen': '127.0.0.1', 'port': 2222}
            data = {'hosting': {'state': 'active'}}
            with patch.object(sftp_access, 'KEYS', keys), patch.object(sftp_access, 'read_profile', return_value=profile):
                def atomic(path, content, mode):
                    path.write_text(content)
                    path.chmod(mode)
                save = Mock()
                with self.assertRaises(ValueError):
                    sftp_access.manage('sftp.add', 'hosting', data,
                                       {'public_key': key + '\nother', 'label': 'test'}, atomic, save)
                sftp_access.manage('sftp.add', 'hosting', data,
                                   {'public_key': key + ' comment', 'label': 'test'}, atomic, save)
                self.assertEqual((keys / 'ap_hosting').read_text(), 'restrict ' + key + '\n')
                data['hosting']['state'] = 'suspended'
                sftp_access.sync('hosting', data['hosting'], atomic)
                self.assertFalse((keys / 'ap_hosting').exists())

    def test_directory_rule_and_php_settings_validation(self):
        with self.assertRaises(ValueError):
            site_security.rules_path('/../etc')
        with self.assertRaises(ValueError):
            site_security.networks(['0.0.0.0/0'])
        with self.assertRaises(ValueError):
            php_settings.settings({**php_settings.DEFAULTS, 'memory_mib': '32M\nuser=root'})
        self.assertEqual(site_security.networks(['192.0.2.4']), ['192.0.2.4/32'])


class HostingApi(unittest.TestCase):
    setUp = test_core.API.setUp
    tearDown = test_core.API.tearDown
    request = test_core.API.request
    setup_admin = test_core.API.setup_admin
    login = test_core.API.login
    package = test_core.API.package
    seed_account = test_core.API.seed_account

    def test_offsite_backup_endpoint_requires_administrator(self):
        self.setup_admin()
        self.seed_account('hosting', 1, self.package())
        self.login('hosting')
        with patch.object(c, 'rpc') as broker:
            self.assertEqual(self.request('/api/offsite-backups')['status'], 403)
            self.assertEqual(self.request('/api/offsite-backups', {})['status'], 403)
            broker.assert_not_called()
            broker.return_value = {'message': 'Website backup requested.'}
            self.login('admin')
            self.assertEqual(self.request('/api/offsite-backups', {})['status'], 200)
            broker.assert_called_once_with('backup.offsite.trigger')

    def login_with_code(self, username, code):
        return self.request('/api/login', {'username':username,'password':'correct horse battery','code':code})

    def test_mfa_consumes_recovery_codes_and_revokes_sessions(self):
        self.setup_admin()
        password = 'correct horse battery'
        response = self.request('/api/mfa', {'action':'begin','password':password})
        secret = response['body']['secret']
        code = security.totp(secret, int(time.time()) // 30)
        result = self.request('/api/mfa', {'action':'confirm','password':password,'code':code})
        self.assertEqual(result['status'], 200, result)
        self.assertEqual(self.request('/api/me')['status'], 401)
        self.assertEqual(self.login_with_code('admin', code)['status'], 401)
        recovery = result['body']['recovery_codes'][0]
        self.assertEqual(self.login_with_code('admin', recovery)['status'], 200)
        self.assertEqual(self.login_with_code('admin', recovery)['status'], 401)

    def test_bearer_token_cannot_mutate_and_revocation_applies(self):
        self.setup_admin()
        item = self.request('/api/tokens', {'action':'create','label':'Read accounts','password':'correct horse battery'})
        self.assertEqual(item['status'], 200, item)
        value = 'Bearer ' + item['body']['token']
        with c.connect() as db:
            self.assertEqual(security.authenticate_token(db, value, '/api/accounts', 'GET')['username'], 'admin')
            with self.assertRaises(c.Problem):
                security.authenticate_token(db, value, '/api/accounts', 'POST')
            with self.assertRaises(c.Problem):
                security.authenticate_token(db, value, '/api/accounts/1/files', 'GET')
        item_id = self.request('/api/tokens')['body'][0]['id']
        self.assertEqual(self.request('/api/tokens', {'action':'revoke','id':item_id})['status'], 200)
        with c.connect() as db, self.assertRaises(c.Problem):
            security.authenticate_token(db, value, '/api/accounts', 'GET')

    def test_nonadmin_requires_dns_proof_before_claim(self):
        self.setup_admin()
        account = self.seed_account('hosting', 1, self.package())
        self.login('hosting')
        path = f'/api/accounts/{account}/domains'
        fields = {'domain':'site.example.com'}
        self.assertEqual(self.request(path, fields)['status'], 409)
        proof = self.request(path, {**fields, 'action':'challenge'})
        self.assertEqual(proof['body']['name'], '_almapanel.site.example.com')
        with patch('backend.core.rpc', return_value={'verified':True}) as rpc:
            self.assertEqual(self.request(path, {**fields, 'action':'verify'})['status'], 200)
            rpc.assert_called_once_with('dns.verify', domain=fields['domain'], token=proof['body']['value'])
        self.assertEqual(self.request(path, fields)['body']['state'], 'queued')

    def test_notifications_respect_account_scope_and_per_user_dismissal(self):
        self.setup_admin()
        pack = self.package()
        owned = self.seed_account('hosting', 1, pack)
        other = self.seed_account('outside', 1, pack)
        with c.connect() as db:
            for item in (owned, other):
                db.execute("""INSERT INTO jobs(actor_id,account_id,operation,payload,state,created)
                    VALUES(1,?,'domain.create','{}','failed',?)""", (item, int(time.time())))
        ids = {entry['account']:entry['id'] for entry in self.request('/api/notifications')['body']}
        self.login('hosting')
        self.assertEqual([entry['account'] for entry in self.request('/api/notifications')['body']], ['hosting'])
        self.assertEqual(self.request('/api/notifications', {'id':ids['outside']})['status'], 404)
        self.assertEqual(self.request('/api/notifications', {'id':ids['hosting']})['status'], 200)
        self.assertEqual(self.request('/api/notifications')['body'], [])
        self.assertEqual(len(self.request('/api/notifications', cookie=self.admin_cookie)['body']), 2)

    def test_backup_schedule_never_queues_inactive_accounts_or_duplicates(self):
        self.setup_admin()
        account = self.seed_account('hosting', 1, self.package())
        self.assertEqual(self.request(f'/api/accounts/{account}/backup-schedule', {
            'interval_hours':24, 'retain':2,
        })['status'], 200)
        due = int(time.time()) + 86401
        with c.connect() as db:
            db.execute("UPDATE accounts SET state='suspended' WHERE id=?", (account,))
        self.assertEqual(schedules.queue_due(due), 0)
        with c.connect() as db:
            db.execute("UPDATE accounts SET state='active' WHERE id=?", (account,))
        self.assertEqual(schedules.queue_due(due), 1)
        self.assertEqual(schedules.queue_due(due), 0)
        with patch('backend.core.rpc', return_value={'message':'Test archive'}) as rpc:
            self.assertTrue(tick())
            rpc.assert_called_once_with('backup.scheduled', name='hosting', retain=2)


if __name__ == '__main__':
    unittest.main()
