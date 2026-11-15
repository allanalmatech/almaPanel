#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$SOURCE/installer/platform.sh"
[[ -f /opt/almapanel/VERSION && -f /var/lib/almapanel/panel.sqlite3 ]] || { echo 'Install almaPanel before upgrading.' >&2; exit 1; }
# Run only from a reviewed, trusted checkout.
"$PANEL_PY" - "$SOURCE" <<'PY'
import fcntl
from pathlib import Path
import sys

source = Path(sys.argv[1])
sys.path.insert(0, str(source / "installer"))
import os
import subprocess
import tempfile
import updater

def configure_provisioning():
    # The package updater replaces application code only. This explicit maintenance
    # command also corrects the agent unit used by earlier installations.
    directory = Path('/etc/systemd/system/almapanel-agent.service.d')
    directory.mkdir(mode=0o755, exist_ok=True)
    target = directory / '20-almapanel-provisioning.conf'
    content = '# Managed by almaPanel. Allow local account and service configuration.\n[Service]\nProtectSystem=yes\n'
    if target.is_symlink() or (target.exists() and (not target.is_file() or target.read_text() != content)):
        raise ValueError(f'{target} is customized. Set ProtectSystem=yes for the agent and reconcile this drop-in.')
    if not target.exists():
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, prefix='.almapanel-', delete=False) as stream:
            temp = Path(stream.name)
            try:
                os.fchmod(stream.fileno(), 0o644)
                stream.write(content)
                stream.flush()
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
    updater.run('/usr/bin/systemctl', 'daemon-reload')

updater.STATE.mkdir(mode=0o700, exist_ok=True)
updater.STATUS.mkdir(mode=0o755, exist_ok=True)
with (updater.STATE / "lock").open("w") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another almaPanel update is running.")
    try:
        incoming = (source / "VERSION").read_text().strip()
        incoming_version = updater.version_key(incoming)
        configure_provisioning()
        updater.recover()
        installed = (updater.ROOT / "VERSION").read_text().strip()
        if incoming_version < updater.version_key(installed):
            raise SystemExit("Checkout is older than installed code.")
        if incoming != installed:
            updater.apply(source)
        else:
            updater.run('/usr/bin/systemctl', 'restart', *updater.UNITS)
            updater.restart_and_verify()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(f"almaPanel update stopped. {error}") from None
PY
if [[ $SOURCE != /opt/almapanel ]]; then
 for helper in updater.py update.sh healthcheck.sh backup.sh enable-databases.sh enable-dns.sh enable-domain-verification.sh enable-site-tls.sh enable-sftp.sh enable-mail.sh renew-site-tls.sh enable-offsite-backup.sh backup_stream.py offsite_database.py offsite_dns.py offsite_backup.py; do
  install -m 644 "$SOURCE/installer/$helper" "/opt/almapanel/installer/$helper"
 done
 install -m 644 "$SOURCE"/services/systemd/almapanel-site-tls.{timer,service} /opt/almapanel/services/systemd/
 install -d -m 755 /opt/almapanel/services/sftp /opt/almapanel/services/mail
 install -m 644 "$SOURCE/services/sftp/sshd_config" /opt/almapanel/services/sftp/
 install -m 644 "$SOURCE/services/systemd/almapanel-sftp.service" /opt/almapanel/services/systemd/
 install -m 644 "$SOURCE"/services/systemd/almapanel-offsite-backup.{timer,service} /opt/almapanel/services/systemd/
 install -m 644 "$SOURCE/services/mail/"{dovecot-alma,postfix-main,postfix-submission}.conf /opt/almapanel/services/mail/
 install -m 644 "$SOURCE/docs/"{HOSTING,MAIL,UPDATES,BACKUPS}.md /opt/almapanel/docs/
fi
sed "s@^ExecStart=/usr/bin/python3 @ExecStart=$PANEL_PY @" \
 "$SOURCE/services/systemd/almapanel-update.service" > /etc/systemd/system/almapanel-update.service
chmod 644 /etc/systemd/system/almapanel-update.service
install -m 644 "$SOURCE/services/systemd/almapanel-update.timer" /etc/systemd/system/
systemctl daemon-reload
if [[ -f /etc/almapanel/update-public.pem ]]; then
 systemctl enable --now almapanel-update.timer
else
 echo 'Update controls installed. Enroll the release verification key to enable automatic checks. See docs/UPDATES.md.'
fi
