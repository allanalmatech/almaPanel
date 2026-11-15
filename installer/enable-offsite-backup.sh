#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 && -f /opt/almapanel/VERSION ]] || { echo 'Run as root on an almaPanel host.' >&2; exit 1; }
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$SOURCE/installer/platform.sh"
case "${1:-}" in
 '') ;;
 --daily) ;;
 *) echo 'Usage: sudo bash installer/enable-offsite-backup.sh [--daily]' >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || exit 2
config=/etc/almapanel/offsite-backup
install -d -m 700 "$config" /var/lib/almapanel-offsite
install -d -m 755 /var/lib/almapanel-backup-status
if [[ ! -x /usr/bin/restic && ! -x /usr/local/bin/restic ]]; then
 if [[ $ID == amzn ]]; then
  if dnf -q list restic >/dev/null 2>&1; then
   dnf install -y restic
  else
   echo 'Install a verified restic executable in /usr/local/bin first. See docs/BACKUPS.md.' >&2
   exit 1
  fi
 else
  apt-get install -y restic
 fi
fi
if [[ $SOURCE != /opt/almapanel ]]; then
 install -m 644 "$SOURCE"/installer/{backup_stream,offsite_database,offsite_dns,offsite_backup}.py /opt/almapanel/installer/
 install -m 644 "$SOURCE/docs/BACKUPS.md" /opt/almapanel/docs/
fi
sed -E "s@^(ExecStart|ExecStopPost)=/usr/bin/python3 @\1=$PANEL_PY @" \
 "$SOURCE/services/systemd/almapanel-offsite-backup.service" > /etc/systemd/system/almapanel-offsite-backup.service
chmod 644 /etc/systemd/system/almapanel-offsite-backup.service
install -m 644 "$SOURCE/services/systemd/almapanel-offsite-backup.timer" /etc/systemd/system/
systemctl daemon-reload
if [[ -z ${1:-} ]]; then
 echo 'Software installed. Configure the repository and credentials using docs/BACKUPS.md, then initialize and test it.'
 exit 0
fi
"$PANEL_PY" -I /opt/almapanel/installer/offsite_backup.py check
systemctl enable --now almapanel-offsite-backup.timer
systemctl list-timers almapanel-offsite-backup.timer --no-pager
