#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
for unit in almapanel-agent almapanel-api almapanel-worker nginx php8.3-fpm; do
 systemctl is-active --quiet "$unit" || { echo "$unit failed"; exit 1; }
 echo "$unit: active"
done
nginx -t
php-fpm8.3 -t
curl --retry 10 --retry-connrefused --retry-delay 1 --fail --silent --unix-socket /run/almapanel-api/http.sock http://localhost/api/health
curl --cacert /etc/almapanel/panel.crt --fail --silent https://localhost:8443/api/health
runuser -u almapanel -- env PYTHONPATH=/opt/almapanel /usr/bin/python3 -c 'from backend.core import rpc; print(rpc("system.stats"))'
