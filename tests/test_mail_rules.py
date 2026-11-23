# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Email tools: rule validation, Sieve generation, real Dovecot delivery, catch-all maps,
delivery tracking and deliverability checks."""
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent import mail, mail_rules

address = mail.address


def rule(**values):
    base = {'name': 'Rule', 'field': 'subject', 'match': 'contains', 'value': 'invoice', 'action': 'move', 'target': 'Receipts'}
    return {**base, **values}


class Validation(unittest.TestCase):
    def test_rules(self):
        result = mail_rules.rules([rule(), rule(action='forward', target='Boss@Example.com'.lower()),
                                   rule(action='discard', target=None)], address)
        self.assertEqual([item['action'] for item in result], ['move', 'forward', 'discard'])
        self.assertNotIn('target', result[2])
        for bad in ([rule(field='received')], [rule(match='regex')], [rule(action='reject')],
                    [rule(target='../etc')], [rule(target='a.b')], [rule(target='x' * 41)],
                    [rule(action='forward', target='not an address')], [rule(value='')],
                    [rule(value='x\x00y')], [rule(name='n' * 61)], [rule()] * 26,
                    [rule(action='forward', target=f'a{n}@example.com') for n in range(6)], 'rules'):
            with self.subTest(bad=str(bad)[:60]), self.assertRaises(ValueError):
                mail_rules.rules(bad, address)

    def test_autoresponder(self):
        value = mail_rules.autoresponder({'subject': 'Away', 'body': 'Back Monday.\r\nThanks', 'interval_days': 3,
                                          'start': '2026-12-01', 'end': '2026-12-05'}, 'me@example.com')
        self.assertEqual(value['body'], 'Back Monday.\nThanks')
        self.assertIsNone(mail_rules.autoresponder(None, 'me@example.com'))
        for bad in ({'subject': '', 'body': 'x'}, {'subject': 'x\ny', 'body': 'x'}, {'subject': 'x', 'body': 'x' * 4001},
                    {'subject': 'x', 'body': 'x', 'interval_days': 0}, {'subject': 'x', 'body': 'x', 'interval_days': '2'},
                    {'subject': 'x', 'body': 'x', 'start': '2026-13-01'},
                    {'subject': 'x', 'body': 'x', 'start': '2026-12-05', 'end': '2026-12-01'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mail_rules.autoresponder(bad, 'me@example.com')

    def test_quoting(self):
        self.assertEqual(mail_rules.quote('say "hi" \\o/'), '"say \\"hi\\" \\\\o/"')
        self.assertEqual(mail_rules.wildcard('50% *off*?'), '50% \\*off\\*\\?')


@unittest.skipUnless(Path('/usr/bin/sievec').is_file(), 'Requires the Dovecot Sieve compiler.')
class Compile(unittest.TestCase):
    def test_hostile_text_compiles_as_data(self):
        tricky = 'x" ; discard ; if true { keep } "\\ *?'
        content = mail_rules.script(
            mail_rules.rules([rule(value=tricky), rule(field='from', match='begins', value=tricky, action='discard')], address),
            mail_rules.rules([rule(field='any', match='ends', value='}"{', action='forward', target='a@example.com')], address),
            mail_rules.autoresponder({'subject': tricky, 'body': 'line one\n.\n' + tricky, 'start': '2026-01-01'}, 'me@example.com'))
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'test.sieve'
            source.write_text(content)
            subprocess.run(['/usr/bin/sievec', str(source), str(source.with_suffix('.svbin'))], check=True,
                           capture_output=True)
            dump = subprocess.run(['/usr/bin/sieve-dump', str(source.with_suffix('.svbin'))], capture_output=True, text=True).stdout
        # Exactly the generated actions exist: hostile text did not add commands.
        self.assertEqual(dump.count('FILEINTO'), 1)
        self.assertEqual(dump.count('DISCARD'), 1)
        self.assertEqual(dump.count('REDIRECT'), 1)
        self.assertEqual(dump.count('VACATION'), 1)

    def test_no_rules_no_script(self):
        self.assertIsNone(mail_rules.script([], [], None))


LDA = next((path for path in ('/usr/lib/dovecot/dovecot-lda', '/usr/libexec/dovecot/dovecot-lda') if Path(path).is_file()), None)


@unittest.skipUnless(LDA and Path('/usr/bin/sievec').is_file() and os.geteuid() == 0,
                     'Requires Dovecot with Sieve and root to deliver test mail.')
class RealDelivery(unittest.TestCase):
    """Deliver messages through Dovecot's delivery agent using generated scripts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        root.chmod(0o755)
        user = pwd.getpwnam('nobody')
        self.uid, self.gid = user.pw_uid, user.pw_gid
        self.vmail = root / 'vmail'
        self.vmail.mkdir(mode=0o755)
        self.outbox = root / 'outbox'
        self.outbox.mkdir()
        self.outbox.chmod(0o777)
        sendmail = root / 'sendmail'
        sendmail.write_text(f'#!/bin/sh\nfile=$(mktemp {self.outbox}/msg.XXXXXX)\nprintf "%s\\n" "$*" > "$file"\ncat >> "$file"\n')
        sendmail.chmod(0o755)
        home = self.vmail / 'shop' / 'example.com' / 'me'
        (root / 'passwd').write_text(f'me@example.com::{self.uid}:{self.gid}::{home}::\n')
        sieve = Path('services/mail/dovecot-sieve.conf').read_text().replace('protocol lmtp', 'protocol lda')
        (root / 'dovecot.conf').write_text(
            f'mail_location = maildir:~/Maildir\nfirst_valid_uid = 1\nlog_path = /dev/stderr\n'
            f'base_dir = {root}/run\nstate_dir = {root}/state\nsendmail_path = {sendmail}\n'
            f'postmaster_address = postmaster@example.com\nhostname = mail.example.com\n'
            f'userdb {{\n driver = passwd-file\n args = {root}/passwd\n}}\n'
            f'passdb {{\n driver = passwd-file\n args = {root}/passwd\n}}\n' + sieve)
        self.root = root
        self.home = home

    def install(self, content):
        with patch.object(mail_rules, 'VMAIL', self.vmail):
            os.chown(self.vmail, self.uid, self.gid)
            mail_rules.write_script('shop', 'me@example.com', content, self.uid, self.gid)

    def deliver(self, sender, subject, body='Hello'):
        message = f'From: {sender}\nTo: me@example.com\nSubject: {subject}\nMessage-ID: <{subject.replace(" ", "")}@test>\n\n{body}\n'
        # Run as the mailbox owner with its home, as a local delivery would after the user lookup.
        result = subprocess.run([LDA, '-c', str(self.root / 'dovecot.conf'), '-f', sender, '-a', 'me@example.com'],
                                input=message, text=True, capture_output=True, user=self.uid, group=self.gid,
                                extra_groups=[], env={'HOME': str(self.home), 'USER': 'me@example.com', 'PATH': '/usr/bin:/bin'})
        self.assertEqual(result.returncode, 0, result.stderr)

    def folder(self, name=''):
        path = self.home / 'Maildir' / (('.' + name) if name else '') / 'new'
        return [item.read_text() for item in path.iterdir()] if path.is_dir() else []

    def test_filters_and_autoresponder(self):
        content = mail_rules.script(
            mail_rules.rules([rule(name='Receipts', value='Invoice')], address),
            mail_rules.rules([rule(name='Block', field='from', match='ends', value='@spam.example', action='discard'),
                              rule(name='Copy boss', field='from', match='is', value='boss@corp.example',
                                   action='forward', target='assistant@example.org')], address),
            mail_rules.autoresponder({'subject': 'Out of office', 'body': 'Back on "Monday".\nThanks.', 'interval_days': 1},
                                     'me@example.com'))
        self.install(content)
        self.deliver('client@buyer.example', 'Invoice 42')
        self.assertEqual(len(self.folder('Receipts')), 1)
        self.deliver('promo@spam.example', 'You won')
        self.deliver('boss@corp.example', 'Quarterly plan')
        inbox = self.folder()
        self.assertEqual([('Quarterly plan' in item) for item in inbox], [True])  # Spam discarded, boss kept.
        outbox = [item.read_text() for item in self.outbox.iterdir()]
        forwarded = [item for item in outbox if 'assistant@example.org' in item.splitlines()[0]]
        replies = [item for item in outbox if 'Subject: Out of office' in item]
        self.assertEqual(len(forwarded), 1)
        self.assertIn('Subject: Quarterly plan', forwarded[0])
        # Filed and kept messages both get one reply per sender; discarded spam does not.
        self.assertEqual(len(replies), 1)
        self.assertIn('boss@corp.example', replies[0])
        self.assertIn('Back on "Monday".', replies[0])
        self.deliver('boss@corp.example', 'Follow up')
        self.assertEqual(len([item for item in self.outbox.iterdir() if 'Subject: Out of office' in item.read_text()]), 1)

    def test_removing_rules_removes_script(self):
        self.install(mail_rules.script(mail_rules.rules([rule(action='discard', target=None)], address), [], None))
        self.deliver('a@b.example', 'invoice')
        self.assertEqual(self.folder(), [])
        self.install(None)
        self.assertFalse((self.home / mail_rules.SCRIPT_NAME).exists())
        self.deliver('a@b.example', 'invoice again')
        self.assertEqual(len(self.folder()), 1)


class ScriptFiles(unittest.TestCase):
    def test_refuses_links_in_the_mail_store(self):
        with tempfile.TemporaryDirectory() as folder:
            vmail = Path(folder) / 'vmail'
            vmail.mkdir()
            outside = Path(folder) / 'outside'
            outside.mkdir()
            (vmail / 'shop').symlink_to(outside)
            with patch.object(mail_rules, 'VMAIL', vmail), self.assertRaises(OSError):
                mail_rules.write_script('shop', 'me@example.com', 'keep;\n', os.getuid(), os.getgid())
            self.assertEqual(list(outside.iterdir()), [])

    def test_mailbox_usage_ignores_links(self):
        with tempfile.TemporaryDirectory() as folder:
            maildir = Path(folder) / 'Maildir' / 'cur'
            maildir.mkdir(parents=True)
            (maildir / 'a').write_bytes(b'x' * 100)
            (maildir / 'big').symlink_to('/etc/passwd')
            self.assertEqual(mail_rules.directory_bytes(Path(folder) / 'Maildir'), 100)
            self.assertEqual(mail_rules.directory_bytes(Path(folder) / 'missing'), 0)


class CatchAll(unittest.TestCase):
    settings = {'hostname': 'mail.example.com', 'uid': 5000, 'gid': 5000, 'listen': 'loopback', 'sieve': True}

    def data(self, defaults):
        return {'shop': {'state': 'active', 'domains': ['example.com', 'other.example'], 'mail': {
            'domains': ['example.com'], 'forwarders': {'sales@example.com': 'me@example.com'},
            'mailboxes': {'me@example.com': {'hash': '$6$salt$' + 'a' * 86, 'quota_mib': 10, 'enabled': True}},
            'defaults': defaults}}}

    def test_identity_entries_keep_real_mailboxes(self):
        paths = mail.configuration(self.data({'example.com': 'me@example.com'}), self.settings)
        aliases = paths[mail.MAP_DIR / 'aliases'].splitlines()
        self.assertIn('@example.com me@example.com', aliases)
        self.assertIn('me@example.com me@example.com', aliases)
        self.assertIn('sales@example.com me@example.com', aliases)
        without = mail.configuration(self.data({}), self.settings)[mail.MAP_DIR / 'aliases']
        self.assertNotIn('@example.com', without.replace('sales@example.com', '').replace('me@example.com', ''))

    def test_postfix_reads_the_generated_map(self):
        if not shutil.which('postmap'):
            self.skipTest('Requires Postfix postmap.')
        paths = mail.configuration(self.data({'example.com': 'me@example.com'}), self.settings)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'aliases'
            target.write_text(paths[mail.MAP_DIR / 'aliases'])
            (Path(folder) / 'main.cf').touch()
            query = lambda key: subprocess.run(['postmap', '-c', folder, '-q', key, f'texthash:{target}'],
                                               capture_output=True, text=True).stdout.strip()
            self.assertEqual(query('@example.com'), 'me@example.com')
            self.assertEqual(query('me@example.com'), 'me@example.com')

    def test_default_targets_must_exist_locally(self):
        state = self.data({})['shop']['mail']
        mail.validate_default(state, 'example.com', 'me@example.com')
        mail.validate_default(state, 'example.com', 'sales@example.com')
        mail.validate_default(state, 'example.com', 'someone@outside.example')
        with self.assertRaises(ValueError):
            mail.validate_default(state, 'example.com', 'nobody@example.com')

    def test_registry_rejects_foreign_default(self):
        with self.assertRaises(ValueError):
            mail.configuration(self.data({'other.example': 'me@example.com'}), self.settings)


LOG = '''2026-11-23T10:00:01+0300 mail postfix/smtpd[100]: 4F2A31C0A3: client=sender.example[192.0.2.5]
2026-11-23T10:00:01+0300 mail postfix/cleanup[101]: 4F2A31C0A3: message-id=<a@sender.example>
2026-11-23T10:00:01+0300 mail postfix/qmgr[102]: 4F2A31C0A3: from=<alice@sender.example>, size=900, nrcpt=1 (queue active)
2026-11-23T10:00:02+0300 mail postfix/lmtp[103]: 4F2A31C0A3: to=<me@example.com>, relay=mail[private/alma-lmtp], delay=0.1, status=sent (250 2.0.0 <me@example.com> Saved)
2026-11-23T11:00:01+0300 mail postfix/qmgr[102]: 5B1C22D0E4: from=<me@example.com>, size=500, nrcpt=2 (queue active)
2026-11-23T11:00:03+0300 mail postfix/smtp[104]: 5B1C22D0E4: to=<bob@far.example>, relay=mx.far.example[198.51.100.7]:25, delay=2, status=bounced (host said: 550 5.1.1 User unknown)
2026-11-23T11:00:04+0300 mail postfix/smtp[104]: 5B1C22D0E4: to=<carol@far.example>, relay=none, delay=3, status=deferred (connect timed out)
2026-11-23T12:00:00+0300 mail postfix/qmgr[102]: 6C2D33E1F5: from=<x@unrelated.example>, size=1, nrcpt=1 (queue active)
2026-11-23T12:00:01+0300 mail postfix/smtp[104]: 6C2D33E1F5: to=<y@unrelated.example>, relay=none, status=sent (ok)
2026-11-23T12:00:02+0300 mail postfix/anvil[105]: statistics: max connection rate 1/60s
'''


class Tracking(unittest.TestCase):
    def test_account_scoped_delivery_history(self):
        messages = mail_rules.track(LOG, ['example.com'])
        self.assertEqual([(item['to'], item['status']) for item in messages],
                         [('carol@far.example', 'deferred'), ('bob@far.example', 'bounced'), ('me@example.com', 'sent')])
        self.assertEqual(messages[1]['detail'], 'host said: 550 5.1.1 User unknown')
        self.assertEqual(messages[2]['from'], 'alice@sender.example')
        self.assertEqual([item['to'] for item in mail_rules.track(LOG, ['example.com'], 'BOB')], ['bob@far.example'])
        self.assertEqual(mail_rules.track(LOG, ['nothing.example']), [])


class Deliverability(unittest.TestCase):
    def test_checks_and_suggestions(self):
        answers = {'MX': ['example.com. 300 IN MX 10 mail.example.com.'],
                   'TXT': ['example.com. 300 IN TXT "v=spf1 mx " "~all"', 'example.com. 300 IN TXT "google-site=x"'],
                   'DMARC': []}
        report = {item['name']: item for item in mail_rules.deliverability('example.com', 'mail.example.com', answers)['checks']}
        self.assertEqual(report['MX']['state'], 'pass')
        self.assertEqual(report['SPF']['state'], 'pass')
        self.assertEqual(report['SPF']['found'], ['v=spf1 mx ~all'])
        self.assertEqual(report['DMARC']['state'], 'fail')
        self.assertIn('_dmarc.example.com', report['DMARC']['suggested'])
        other = mail_rules.deliverability('example.com', 'mail.example.com',
                                          {'MX': ['example.com. 1 IN MX 5 aspmx.other.example.'], 'TXT': [], 'DMARC': []})
        self.assertEqual({item['name']: item['state'] for item in other['checks']}['MX'], 'warn')
