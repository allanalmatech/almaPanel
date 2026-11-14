#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ $EUID -eq 0 && -d /etc/almapanel ]] || { echo 'Run as root on an almaPanel host.' >&2; exit 1; }
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$SOURCE/installer/platform.sh"
if [[ ! -x /usr/bin/certbot ]]; then
 if [[ $ID == ubuntu ]]; then
  apt-get install -y certbot
 elif dnf -q list certbot >/dev/null 2>&1; then
  dnf install -y certbot
 else
  echo 'Install a supported Certbot build at /usr/bin/certbot before enabling site renewal.' >&2
  exit 1
 fi
fi
install -m 644 "$SOURCE/installer/renew-site-tls.sh" /opt/almapanel/installer/renew-site-tls.sh
install -m 644 "$SOURCE"/services/systemd/almapanel-site-tls.{timer,service} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now almapanel-site-tls.timer
echo 'Website TLS renewal enabled. Issue the first certificate from SSL/TLS in almaPanel.'
