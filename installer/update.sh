#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
[[ -f /etc/almapanel/update-public.pem ]] || { echo 'Enroll the release public key first. See docs/UPDATES.md.' >&2; exit 1; }
systemctl start almapanel-update.service
cat /var/lib/almapanel-update-status/status.json
