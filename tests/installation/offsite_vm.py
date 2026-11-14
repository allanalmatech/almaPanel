# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Disposable-VM acceptance for staging and importing a real restic backup."""
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess
import tempfile
import zipfile


def offsite(*args):
    return subprocess.run(['bash', '/opt/almapanel/installer/backup.sh', '--offsite', *args],
                          check=True, capture_output=True, text=True, timeout=120).stdout


if os.environ.get('ALMA_DISPOSABLE_VM') != 'YES' or os.geteuid() != 0:
    raise SystemExit('Requires a disposable VM with administrator access.')
config = Path('/etc/almapanel/offsite-backup')
os.umask(0o077)
if any(config.iterdir()):
    raise SystemExit('Use an empty backup configuration on the disposable VM.')
with tempfile.TemporaryDirectory(prefix='alma-restic-acceptance-', dir='/var/backups') as repository:
    repo = Path(repository)
    (config / 'password').write_text(secrets.token_urlsafe(32) + '\n')
    (config / 'repository.json').write_text(json.dumps({'repository': str(repo), 'host': 'alma-vm-acceptance'}))
    try:
        offsite('init')
        offsite('snapshot')
        offsite('check', '--read-data')
        status = json.loads(Path('/var/lib/almapanel-backup-status/status.json').read_text())
        assert status['state'] == 'succeeded', status
        entries = json.loads(offsite('list'))
        assert len(entries) == 1
        output = offsite('restore', entries[0]['id'], 'vmtenant', '--import-to', 'vmsecond')
        filename = re.search(r'Imported (website-[a-f0-9]{16}\.zip) into', output).group(1)
        archive = Path('/srv/almapanel/accounts/vmsecond/panel-files/backups') / filename
        assert archive.stat().st_uid == pwd.getpwnam('ap_vmsecond').pw_uid
        assert archive.stat().st_mode & 0o077 == 0
        with zipfile.ZipFile(archive) as backup:
            assert backup.read('next/index.php') == b'<?php echo "new-root";'
        assert not Path('/srv/almapanel/accounts/vmsecond/public_html/recovered.php').exists()
    finally:
        (config / 'password').unlink(missing_ok=True)
        (config / 'repository.json').unlink(missing_ok=True)
print('Live off-site workflow passed for backup creation, encrypted storage, verification and tenant-owned import.')
