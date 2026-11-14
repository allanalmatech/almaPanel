#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$SOURCE/installer/platform.sh"
# Run only from a reviewed, trusted checkout.
"$PANEL_PY" - "$SOURCE" <<'PY'
import fcntl
import os
from pathlib import Path
import sys

source = Path(sys.argv[1])
sys.path.insert(0, str(source / "installer"))
import updater

updater.STATE.mkdir(mode=0o700, exist_ok=True)
updater.STATUS.mkdir(mode=0o755, exist_ok=True)
with (updater.STATE / "lock").open("w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    updater.recover()
    installed = (updater.ROOT / "VERSION").read_text().strip()
    incoming = (source / "VERSION").read_text().strip()
    if updater.version_key(incoming) < updater.version_key(installed):
        raise SystemExit("Checkout is older than installed code.")
    if incoming != installed:
        updater.apply(source)
PY
install -m 644 "$SOURCE/installer/updater.py" /opt/almapanel/installer/updater.py
install -m 644 "$SOURCE/installer/update.sh" /opt/almapanel/installer/update.sh
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
