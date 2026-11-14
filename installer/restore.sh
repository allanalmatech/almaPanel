#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo 'Run as root'; exit 1; }
[[ $# -eq 2 && $2 == --confirm-control-plane-restore ]] || { echo 'Usage: restore.sh /var/backups/almapanel/control-ID --confirm-control-plane-restore'; exit 2; }
SNAP=$(realpath -e -- "$1")
[[ $SNAP == /var/backups/almapanel/control-* && -d $SNAP && ! -L $1 ]] || { echo 'Only a trusted local root-owned snapshot is accepted.'; exit 1; }
[[ $(stat -c %u "$SNAP") == 0 && $(stat -c %a "$SNAP") == 700 ]] || exit 1
# Restoring database state against changed OS resources would violate ownership guarantees.
# Reject unexpected symlinks/ownership anywhere in the trusted snapshot.
if find "$SNAP" -type l -o ! -user root | read -r _; then echo 'Untrusted snapshot contents'; exit 1; fi
cmp "$SNAP/VERSION" /opt/almapanel/VERSION
(cd "$SNAP" && sha256sum -c SHA256SUMS)
systemctl stop almapanel-worker almapanel-api almapanel-agent
trap 'systemctl start almapanel-agent almapanel-api almapanel-worker' EXIT
python3 - "$SNAP" <<'PYS'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
a=json.loads((p/'agent/registry.json').read_text()) if (p/'agent/registry.json').exists() else {}
b=json.loads(Path('/var/lib/almapanel-agent/registry.json').read_text()) if Path('/var/lib/almapanel-agent/registry.json').exists() else {}
if a!=b: raise SystemExit('Agent state changed. Refusing database-only restore; reconcile OS resources first.')
PYS
SAVE=$(mktemp -d /var/backups/almapanel/before-restore-XXXXXXXX)
cp -a /var/lib/almapanel/. "$SAVE/"
rm -f /var/lib/almapanel/panel.sqlite3-wal /var/lib/almapanel/panel.sqlite3-shm
install -m 600 -o almapanel -g almapanel "$SNAP/panel.sqlite3" /var/lib/almapanel/panel.sqlite3
python3 - <<'PYS'
import sqlite3
with sqlite3.connect('/var/lib/almapanel/panel.sqlite3') as db:
 if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise SystemExit('Database integrity failed')
 db.execute('DELETE FROM sessions')
PYS
echo "Restored control database only; previous database preserved in $SAVE. TLS configuration and customer files were not overwritten."
