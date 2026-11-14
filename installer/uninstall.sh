#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || exit 1
[[ ${1:-} == --disable-panel ]] || { echo 'Usage: uninstall.sh --disable-panel (preserves ALL customer data, accounts, services and backups)'; exit 2; }
systemctl disable --now almapanel-worker almapanel-api almapanel-agent
if [[ -f /etc/nginx/conf.d/almapanel.conf ]]; then
 mv /etc/nginx/conf.d/almapanel.conf /etc/almapanel/panel-nginx.disabled
 if nginx -t; then systemctl reload nginx; else
  mv /etc/almapanel/panel-nginx.disabled /etc/nginx/conf.d/almapanel.conf
  echo 'Nginx validation failed; configuration restored.'; exit 1
 fi
fi
echo 'Panel disabled. Customer websites, PHP pools, users, files, configuration and backups are preserved.'
