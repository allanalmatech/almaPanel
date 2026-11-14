#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Exercise encrypted backup, selective retrieval and import with real restic."""
import io
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent import file_tools
from installer import offsite_backup as backup


class WebsiteRecovery(unittest.TestCase):
    def test_encrypted_restic_round_trip_and_scoped_retention(self):
        restic = os.environ.get('ALMA_TEST_RESTIC') or shutil.which('restic')
        if not restic:
            self.fail('Install restic or pass its path in ALMA_TEST_RESTIC.')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state, web, private, repo = (root / name for name in ('state', 'web', 'private', 'repository'))
            for path in (state, web, private, repo, private / 'backups'):
                path.mkdir()
            token = root / 'password'
            token.write_text(secrets.token_urlsafe(32))
            token.chmod(0o600)
            env = {'RESTIC_REPOSITORY': str(repo), 'RESTIC_PASSWORD_FILE': str(token), 'PATH': '/usr/bin:/bin'}
            settings = ([restic, '--no-cache'], env, 'website-test')
            other = (settings[0], settings[1], 'unrelated-test')
            inventory = {'hosting': {'state': 'active'}}
            website = web / 'index.html'
            website.write_text('first version')

            def capture(account, destination):
                self.assertEqual(account, 'hosting')
                with file_tools.folder(web_fd, []) as fd, destination.open('xb') as output:
                    file_tools.write_zip(fd, output, file_tools.BACKUP_BYTES, compress=False)

            web_fd = os.open(web, file_tools.NOFOLLOW_DIR)
            try:
                backup.run_restic(settings, 'init')
                backup.website_snapshot(settings, state, inventory, capture)
                first = backup.snapshots(settings, state)[0]['id']
                self.assertFalse((state / 'upload').exists())
                website.write_text('second version')
                backup.website_snapshot(settings, state, inventory, capture)
                backup.website_snapshot(other, state, inventory, capture)
                unrelated = backup.snapshots(other, state)[0]['id']
                with self.assertRaisesRegex(ValueError, 'outside this host'):
                    backup.restore(settings, state, unrelated, 'hosting')
                archive = backup.restore(settings, state, first, 'hosting')
                with zipfile.ZipFile(archive) as recovered:
                    self.assertEqual(recovered.read('index.html'), b'first version')
                with file_tools.folder(web_fd, []) as fd:
                    private_fd = os.open(private, file_tools.NOFOLLOW_DIR)
                    try:
                        with archive.open('rb') as source:
                            name = file_tools.import_backup(private_fd, source)
                        members = file_tools.private_operation(fd, private_fd, [name], {'action': 'backup_contents'})
                        file_tools.private_operation(fd, private_fd, [name], {
                            'action': 'backup_restore_file', 'member': 'index.html',
                            'destination': 'recovered.html', 'revision': members['revision']
                        })
                    finally:
                        os.close(private_fd)
                self.assertEqual(website.read_text(), 'second version')
                self.assertEqual((web / 'recovered.html').read_text(), 'first version')
                with self.assertRaisesRegex(ValueError, 'Unable to read'):
                    backup.restore(settings, state, first, 'unknown')
                self.assertEqual(len(list(state.glob('restore-*'))), 1)
                backup.retention(settings, state, 1)
                self.assertEqual(len(backup.snapshots(settings, state)), 2)
                backup.retention(settings, state, 1, apply=True)
                self.assertEqual(len(backup.snapshots(settings, state)), 1)
                self.assertEqual(backup.snapshots(other, state)[0]['id'], unrelated)
                backup.run_restic(settings, 'check', '--read-data')
                with patch.object(backup, 'ARCHIVE_LIMIT', 32):
                    with self.assertRaisesRegex(ValueError, 'exceeds its size'):
                        backup.restore(settings, state, backup.snapshots(settings, state)[0]['id'], 'hosting')
                self.assertEqual(len(list(state.glob('restore-*'))), 1)
                invalid = ({**env, 'RESTIC_PASSWORD_FILE': str(root / 'wrong-password')})
                (root / 'wrong-password').write_text(secrets.token_urlsafe(32))
                with self.assertRaises(subprocess.CalledProcessError):
                    backup.snapshots((settings[0], invalid, settings[2]), state)
            finally:
                os.close(web_fd)

    def test_import_rejects_invalid_zip_without_leaving_a_partial_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'backups').mkdir()
            fd = os.open(root, file_tools.NOFOLLOW_DIR)
            try:
                with self.assertRaises(ValueError):
                    file_tools.import_backup(fd, io.BytesIO(b'invalid archive'))
                self.assertEqual(list((root / 'backups').iterdir()), [])
            finally:
                os.close(fd)


if __name__ == '__main__':
    unittest.main()
