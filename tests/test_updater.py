# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from installer import updater


class UpdaterTests(unittest.TestCase):
    def test_release_order(self):
        self.assertLess(updater.version_key('0.1.0-alpha.9'), updater.version_key('0.1.0-alpha.10'))
        self.assertLess(updater.version_key('0.1.0-rc.1'), updater.version_key('0.1.0'))
        with self.assertRaises(ValueError):
            updater.version_key('main')

    def test_archive_rejects_traversal_and_symlinks(self):
        for name, link in [('almapanel/backend/../../escape', False), ('almapanel/backend/link', True)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with tarfile.open(root / 'bad.tgz', 'w:gz') as archive:
                    entry = tarfile.TarInfo(name)
                    if link:
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = '/etc/passwd'
                    archive.addfile(entry, io.BytesIO())
                with self.assertRaises(ValueError):
                    updater.stage_archive(root / 'bad.tgz', root / 'stage', '0.1.0')

    def test_recovery_uses_checkout_health_check_and_clears_marker_on_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            marker = state / 'in-progress'
            marker.touch()
            backup = state / 'rollback'
            backup.mkdir()
            (backup / 'VERSION').write_text('0.1.0-alpha.2')
            for part in updater.DIRS:
                (backup / part).mkdir()
            with patch.object(updater, 'STATE', state), patch.object(updater, 'run') as run, patch.object(
                updater, 'sync_code'
            ) as sync:
                run.side_effect = [None, None, subprocess.CalledProcessError(7, 'bash')]
                with self.assertRaises(subprocess.CalledProcessError):
                    updater.recover()
                self.assertTrue(marker.exists())
                run.side_effect = None
                self.assertTrue(updater.recover())
                self.assertFalse(marker.exists())
                sync.assert_called_with(backup)
                run.assert_called_with('/usr/bin/bash', str(updater.HEALTHCHECK))
                self.assertEqual(updater.HEALTHCHECK, Path(updater.__file__).resolve().with_name('healthcheck.sh'))

    def test_incomplete_recovery_does_not_stop_running_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / 'in-progress').touch()
            with patch.object(updater, 'STATE', state), patch.object(updater, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'application backup'):
                    updater.recover()
            run.assert_not_called()
