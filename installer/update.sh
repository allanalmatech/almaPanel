#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
# Fail closed until versioned upgrade AND rollback tests pass on a real Ubuntu VM.
echo 'Automatic updates are not enabled in 0.1.0-alpha.1. No files changed.' >&2
echo 'See DEPLOYMENT.md: snapshot the VM, test the next version on a clone, then follow its reviewed migration guide.' >&2
exit 3
