#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
# Control-plane backup only. NOT a customer data / disaster recovery backup.
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo 'Run as root'; exit 1; }
[[ ${1:-} == --control-plane ]] || { echo 'Usage: backup.sh --control-plane'; exit 2; }
install -d -m 700 /var/backups/almapanel
DEST=$(mktemp -d /var/backups/almapanel/control-XXXXXXXX)
export DEST
systemctl stop almapanel-worker almapanel-api almapanel-agent
trap 'systemctl start almapanel-agent almapanel-api almapanel-worker' EXIT
python3 - <<'PYS'
import os,sqlite3
from pathlib import Path
p=Path(os.environ['DEST'])
source=sqlite3.connect('/var/lib/almapanel/panel.sqlite3')
target=sqlite3.connect(p/'panel.sqlite3')
source.backup(target);target.close();source.close()
PYS
cp -a /etc/almapanel "$DEST/config"
cp -a /var/lib/almapanel-agent "$DEST/agent"
cp /opt/almapanel/VERSION "$DEST/VERSION"
(cd "$DEST" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "Control-plane snapshot: $DEST"
echo 'Contains secrets. Keep root-only; encrypt before remote transfer. Customer content and Linux identities are NOT included.'
