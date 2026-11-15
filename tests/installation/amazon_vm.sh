#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ ${ALMA_DISPOSABLE_VM:-} == YES && $EUID -eq 0 ]] || { echo 'Requires root on a disposable VM.' >&2; exit 1; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source /etc/os-release
[[ $ID == amzn && $VERSION_ID == 2023 ]] || { echo 'Use an Amazon Linux 2023 VM.' >&2; exit 1; }
bash "$ROOT/installer/install.sh" --accept-alpha
if [[ ${ALMA_TEST_SQL:-NO} == YES ]]; then
 bash "$ROOT/installer/enable-databases.sh" mariadb
 bash "$ROOT/installer/enable-databases.sh" postgresql
fi
if [[ ${ALMA_TEST_SFTP:-NO} == YES ]]; then
 bash "$ROOT/installer/enable-sftp.sh"
fi
if [[ ${ALMA_TEST_MAIL:-NO} == YES ]]; then
 mail_fixture=$(mktemp -d)
 trap 'rm -rf -- "$mail_fixture"' EXIT
 openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=mail.acceptance.example.com \
  -addext 'subjectAltName=DNS:mail.acceptance.example.com' \
  -keyout "$mail_fixture/key.pem" -out "$mail_fixture/cert.pem"
 bash "$ROOT/installer/enable-mail.sh" mail.acceptance.example.com \
  "$mail_fixture/cert.pem" "$mail_fixture/key.pem" --loopback
 export ALMA_TEST_MAIL_CERT="$mail_fixture/cert.pem"
fi
if [[ ${ALMA_TEST_OFFSITE:-NO} == YES ]]; then
 bash "$ROOT/installer/enable-offsite-backup.sh"
fi
/opt/almapanel/venv/bin/python "$ROOT/tests/e2e/live_vm.py"
bash /opt/almapanel/installer/healthcheck.sh
