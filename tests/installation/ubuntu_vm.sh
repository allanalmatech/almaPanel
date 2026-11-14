#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
# DESTRUCTIVE TEST ENVIRONMENT: use only a disposable Ubuntu 24.04 EC2/VM.
set -Eeuo pipefail
[[ ${ALMA_DISPOSABLE_VM:-} == YES ]] || { echo 'Set ALMA_DISPOSABLE_VM=YES on a disposable VM only.'; exit 2; }
[[ $EUID -eq 0 ]] || exit 1
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
bash "$ROOT/installer/install.sh" --accept-alpha
python3 "$ROOT/tests/e2e/live_vm.py"
bash /opt/almapanel/installer/healthcheck.sh
# Persistence, hostile tenant tests, reboot and full restore remain separate manual gates.
