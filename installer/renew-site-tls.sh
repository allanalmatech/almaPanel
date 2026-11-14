#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
/usr/bin/certbot renew --config-dir /etc/almapanel/acme/config \
 --work-dir /var/lib/almapanel-agent/acme-work --logs-dir /var/log/almapanel/acme \
 --no-directory-hooks --deploy-hook '/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx'
