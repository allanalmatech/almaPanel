# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

from installer import offsite_backup as backup
from installer import offsite_database as sql


class EnrolledDatabases(unittest.TestCase):
    def setUp(self):
        workspace = self.enterContext(tempfile.TemporaryDirectory())
        self.state = Path(workspace)
        self.inventory = {'hosting': {'state': 'active', 'databases': {'db': {'engine': 'mariadb'}}}}
        self.db = sql.managed_database(self.inventory, 'hosting', 'db')
        self.password = secrets.token_urlsafe(24)

    def test_failed_password_update_preserves_existing_enrollment(self):
        with patch.object(sql, 'authenticate', return_value=([], {})), patch.object(sql, 'probe', return_value=1):
            sql.enroll(self.state, self.db, self.password)
        file = self.state / sql.REGISTRATION
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        with patch.object(sql, 'authenticate', return_value=([], {})), patch.object(
            sql, 'probe', side_effect=ValueError('Credential rejected.')
        ):
            with self.assertRaisesRegex(ValueError, 'Credential rejected'):
                sql.enroll(self.state, self.db, secrets.token_urlsafe(24))
        self.assertEqual(sql.plan(self.state, self.inventory), [(self.db, self.password)])

    def test_stale_enrollment_requires_explicit_removal(self):
        sql.save_registrations(self.state, {'hosting/db': {**self.db, 'password': self.password}})
        self.inventory['hosting']['databases'].clear()
        with self.assertRaisesRegex(ValueError, 'outside the eligible'):
            sql.plan(self.state, self.inventory)
        sql.exclude(self.state, 'hosting', 'db')
        self.assertEqual(sql.plan(self.state, self.inventory), [])

    def test_occupied_destination_never_executes_dump(self):
        with patch.object(sql, 'authenticate', return_value=([], {})), patch.object(
            sql, 'probe', return_value=1
        ), patch.object(sql.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'empty destination'):
                sql.import_dump(self.db, self.password, self.state / 'unopened.sql')
            run.assert_not_called()

    def test_restore_removes_a_dump_that_fails_manifest_integrity(self):
        entry = {'account': 'hosting', 'label': 'db', 'engine': 'mariadb', 'size': 3, 'sha256': '0' * 64}
        target = self.state / 'restore-123'
        target.mkdir()
        stage_file = target / 'db.sql'
        stage_file.write_bytes(b'SQL')
        with patch.object(backup, 'snapshot_databases', return_value=[entry]), patch.object(
            backup, 'stage_member', return_value=stage_file
        ):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                backup.restore_database(None, self.state, '1' * 64, 'hosting', 'db')
        self.assertFalse(target.exists())

    def test_previous_database_snapshot_still_lists_dumps_and_has_no_zones(self):
        entry = {'account': 'hosting', 'label': 'db', 'engine': 'mariadb', 'size': 3, 'sha256': '1' * 64}
        with patch.object(backup, 'read_manifest', return_value={'format': 2, 'databases': [entry]}):
            self.assertEqual(backup.snapshot_databases(None, self.state, '1' * 64), [entry])
            self.assertEqual(backup.snapshot_zones(None, self.state, '1' * 64), [])
