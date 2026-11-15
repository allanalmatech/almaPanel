# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Protect and recover website files and managed SQL on a disposable VM."""
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess
import tempfile
import zipfile


def offsite(*args, password=None):
    return subprocess.run(['bash', '/opt/almapanel/installer/backup.sh', '--offsite', *args],
                          input=password + '\n' if password else None, check=True,
                          capture_output=True, text=True, timeout=180).stdout


def query(db, sql):
    if db['engine'] == 'mariadb':
        args = ['/usr/bin/mariadb', '--no-defaults', '--protocol=socket', '--batch', '--skip-column-names',
                '--user', db['username'], db['database']]
        env = {**os.environ, 'MYSQL_PWD': db['password']}
    else:
        args = ['/usr/bin/psql', '-X', '-w', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                '-h', '127.0.0.1', '-U', db['username'], '-d', db['database']]
        env = {**os.environ, 'PGPASSWORD': db['password']}
    return subprocess.run(args, input=sql, env=env, text=True, capture_output=True,
                          check=True, timeout=15).stdout.strip()


def accept(call, account_url, database_probes):
    if os.environ.get('ALMA_DISPOSABLE_VM') != 'YES' or os.geteuid() != 0:
        raise SystemExit('Requires a disposable VM with administrator access.')
    config = Path('/etc/almapanel/offsite-backup')
    if any(config.iterdir()) or Path('/var/lib/almapanel-offsite/database-logins.json').exists():
        raise SystemExit('Use an empty backup configuration on the disposable VM.')
    enrolled = []
    old_mask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix='alma-restic-acceptance-', dir='/var/backups') as repository:
            (config / 'password').write_text(secrets.token_urlsafe(32) + '\n')
            (config / 'repository.json').write_text(json.dumps({'repository': repository, 'host': 'alma-vm-acceptance'}))
            for source in database_probes:
                offsite('database-include', 'vmtenant', source['label'], '--password-stdin', password=source['password'])
                enrolled.append(source['label'])
            offsite('init')
            offsite('snapshot')
            offsite('check', '--read-data')
            status = call('/offsite-backups')
            assert status['state'] == 'succeeded', status
            entries = json.loads(offsite('list'))
            assert len(entries) == 1
            snapshot = entries[0]['id']
            sql = json.loads(offsite('database-list', snapshot))
            assert {entry['label'] for entry in sql} == set(enrolled)
            for source in database_probes:
                target = call(account_url + '/databases',
                              {'action': 'create', 'engine': source['engine'], 'label': 'recovery' + source['engine']})
                args = ('restore-db', snapshot, 'vmtenant', source['label'], '--import-to', target['label'],
                        '--password-stdin')
                offsite(*args, password=target['password'])
                assert query(target, 'SELECT id FROM acceptance;') == '17'
                assert query(source, 'SELECT id FROM acceptance;') == '17'
                try:
                    offsite(*args, password=target['password'])
                except subprocess.CalledProcessError as error:
                    assert 'empty destination database' in error.stderr
                else:
                    raise AssertionError('Repeated recovery modified the existing destination.')
            output = offsite('restore', snapshot, 'vmtenant', '--import-to', 'vmsecond')
            filename = re.search(r'Imported (website-[a-f0-9]{16}\.zip) into', output).group(1)
            archive = Path('/srv/almapanel/accounts/vmsecond/panel-files/backups') / filename
            assert archive.stat().st_uid == pwd.getpwnam('ap_vmsecond').pw_uid
            assert archive.stat().st_mode & 0o077 == 0
            with zipfile.ZipFile(archive) as backup:
                assert backup.read('next/index.php') == b'<?php echo "new-root";'
            assert not Path('/srv/almapanel/accounts/vmsecond/public_html/recovered.php').exists()
    finally:
        for label in enrolled:
            offsite('database-exclude', 'vmtenant', label)
        (config / 'password').unlink(missing_ok=True)
        (config / 'repository.json').unlink(missing_ok=True)
        os.umask(old_mask)
    print('Live encrypted backup and recovery passed for websites, PostgreSQL and MariaDB.' if enrolled
          else 'Live encrypted backup and recovery passed for websites.')
