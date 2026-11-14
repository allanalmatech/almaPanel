#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/platform.sh" || exit 1
[[ $EUID -eq 0 ]] || exit 1
[[ ${1:-} == --restart-panel ]] || { echo 'Usage: repair.sh --restart-panel. Does not repair failed provisioning; inspect registry and jobs.'; exit 2; }
nginx -t
"$PHP_BIN" -t
systemctl restart almapanel-agent almapanel-api almapanel-worker
bash /opt/almapanel/installer/healthcheck.sh
