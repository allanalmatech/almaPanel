# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

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
