# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from agent import mail, server
from backend import core as c
from tests import test_core


class MailRegistry(unittest.TestCase):
    def setUp(self):
        self.data = {
            'hosting': {'state': 'active', 'domains': ['example.com']},
            'second': {'state': 'active', 'domains': ['second.example.net']},
        }
        self.settings = {'hostname': 'mail.example.org', 'uid': 500, 'gid': 500, 'listen': 'loopback'}
        self.enterContext(patch.object(mail, 'profile', return_value=self.settings))
        self.enterContext(patch.object(mail, 'apply', side_effect=lambda data, _, run, atomic, persist: persist(data)))
        self.password = secrets.token_urlsafe(24)

    def request(self, action, account='hosting', **fields):
        def save(data):
            self.data = data
        return mail.manage('mail.' + action, account, self.data, fields, server.run, Mock(), save)

    def test_mailbox_hash_quota_archive_restore_and_suspension(self):
        email = 'hello@example.com'
        self.request('domain', domain='example.com', enabled=True)
        self.request('create', address=email, quota_mib=7, password=self.password)
        self.request('quota', address=email, quota_mib=9)
        files = mail.configuration(self.data, self.settings)
        self.assertIn(email + ':{SHA512-CRYPT}$6$', files[mail.PASSWD])
        self.assertIn('/var/vmail/hosting/example.com/hello::userdb_quota_rule=*:bytes=9M', files[mail.PASSWD])
        self.assertNotIn(self.password, repr(self.data))
        self.assertNotIn('hash', self.request('list')['mailboxes'][0])
        self.data['hosting']['state'] = 'suspended'
        suspended = mail.configuration(self.data, self.settings)
        self.assertEqual(suspended[mail.PASSWD], '')
        self.assertEqual(suspended[mail.MAP_DIR / 'recipients'], '')
        self.assertIn('example.com 1', suspended[mail.MAP_DIR / 'domains'])
        self.data['hosting']['state'] = 'active'
        self.request('retire', address=email, confirm=email)
        self.assertTrue(self.request('list')['mailboxes'][0]['retired'])
        self.assertEqual(mail.configuration(self.data, self.settings)[mail.PASSWD], '')
        self.request('domain', domain='example.com', enabled=False)
        self.request('domain', domain='example.com', enabled=True)
        self.request('restore', address=email, password=secrets.token_urlsafe(24))
        self.assertTrue(self.request('list')['mailboxes'][0]['enabled'])

    def test_scope_invalid_per_address_quota_and_cross_domain_forwarding_loop(self):
        self.request('domain', domain='example.com', enabled=True)
        self.request('domain', account='second', domain='second.example.net', enabled=True)
        with self.assertRaises(ValueError):
            self.request('create', address='hello@second.example.net', quota_mib=1, password=self.password)
        with self.assertRaises(ValueError):
            self.request('create', address='hello@example.com', quota_mib=True, password=self.password)
        self.request('forward', address='alias@example.com', target='inbox@second.example.net')
        with self.assertRaisesRegex(ValueError, 'would create a loop'):
            self.request('forward', account='second', address='inbox@second.example.net', target='alias@example.com')
        self.assertEqual(self.request('list', account='second')['forwarders'], [])

    def test_disabling_routing_requires_archiving_mailboxes_and_removing_forwarders(self):
        self.request('domain', domain='example.com', enabled=True)
        self.request('forward', address='alias@example.com', target='inbox@second.example.net')
        with self.assertRaisesRegex(ValueError, 'remove the forwarders'):
            self.request('domain', domain='example.com', enabled=False)
        self.request('unforward', address='alias@example.com')
        self.request('domain', domain='example.com', enabled=False)
        self.assertEqual(self.request('list')['domains'], [])


class MailConfiguration(unittest.TestCase):
    def test_validation_failure_restores_all_maps_without_saving_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            passwd = root / 'passwd'
            maps = [root / filename for filename in ('domains', 'recipients', 'aliases', 'senders')]
            for path in [passwd, *maps]:
                path.write_text(path.name + '\n')
            run = Mock(side_effect=[subprocess.CalledProcessError(1, 'doveconf'), 'reloaded'])
            def atomic(path, content, mode, group=None):
                self.assertEqual(group, 8 if path == passwd else None)
                path.write_text(content)
                path.chmod(mode)
            save = Mock()
            with patch.object(mail, 'MAP_DIR', root), patch.object(mail, 'PASSWD', passwd), patch.object(
                mail, 'PROFILE', root / 'profile.json'
            ), patch.object(mail.grp, 'getgrnam') as group:
                group.return_value.gr_gid = 8
                with self.assertRaises(subprocess.CalledProcessError):
                    mail.apply({}, {}, run, atomic, save)
            for path in [passwd, *maps]:
                self.assertEqual(path.read_text(), path.name + '\n')
            save.assert_not_called()
            self.assertIn('reload', run.call_args.args[0])


class MailAPI(unittest.TestCase):
    setUp = test_core.API.setUp
    tearDown = test_core.API.tearDown
    request = test_core.API.request
    setup_admin = test_core.API.setup_admin
    login = test_core.API.login
    package = test_core.API.package
    seed_account = test_core.API.seed_account

    def test_tenant_cannot_read_other_accounts_or_enable_unverified_domains(self):
        self.setup_admin()
        package = self.package()
        account = self.seed_account('hosting', 1, package)
        other = self.seed_account('second', 1, package)
        with c.connect() as db:
            db.execute("INSERT INTO domains(account_id,name,state,created) VALUES(?,?,'active',?)",
                       (account, 'example.com', int(time.time())))
        self.login('hosting')
        with patch.object(c, 'rpc') as call:
            self.assertEqual(self.request(f'/api/accounts/{other}/mail')['status'], 404)
            self.assertEqual(self.request(f'/api/accounts/{account}/mail',
                                         {'action': 'domain', 'domain': 'example.com', 'enabled': True})['status'], 409)
            call.assert_not_called()
