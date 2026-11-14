#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -uo pipefail
printf 'almaPanel diagnostics — no secrets included\n'
cat /etc/os-release
uname -m
free -m
df -h / /srv
for unit in almapanel-agent almapanel-api almapanel-worker nginx php8.3-fpm; do
 systemctl show "$unit" --property=ActiveState,SubState,ExecMainStatus
done
ss -ltn
# Do not dump env, sessions, setup tokens or config files.
printf 'Review service journals locally with sudo journalctl -u almapanel-agent. Redact before sharing.\n'
