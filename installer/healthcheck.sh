#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/platform.sh"

wait_for_health() {
 local label=$1 result deadline=$((SECONDS + 25))
 shift
 while :; do
  if result=$("$@" 2>&1); then
   printf '%s: %s\n' "$label" "$result"
   return 0
  fi
  if ((SECONDS >= deadline)); then
   printf '%s failed: %s\n' "$label" "$result" >&2
   return 1
  fi
  sleep 1
 done
}

check_http() {
 local response
 response=$(curl --disable --noproxy '*' --fail --silent --show-error \
  --connect-timeout 2 --max-time 3 "$@") || return
 if ! "$PANEL_PY" -I -c '
import json
import sys
try:
    health = json.load(sys.stdin)
    ok = health["status"] == "ok" and health["version"] == sys.argv[1]
except (ValueError, TypeError, KeyError):
    ok = False
raise SystemExit(0 if ok else 1)
' "$version" <<< "$response"; then
  echo 'Unexpected health status or installed version.' >&2
  return 1
 fi
 printf '%s\n' "$response"
}

version=$(cat /opt/almapanel/VERSION)
origin=$(awk -F= '$1 == "ALMA_ORIGIN" {print substr($0, index($0, "=") + 1)}' /etc/almapanel/panel.env)
if [[ ! $origin =~ ^https://([a-z0-9][a-z0-9.-]*):8443$ ]]; then
 echo 'Set ALMA_ORIGIN in /etc/almapanel/panel.env to the HTTPS panel URL on port 8443.' >&2
 exit 1
fi
hostname=${BASH_REMATCH[1]}

nginx -t
"$PHP_BIN" -t
if ! wait_for_health 'Panel API socket' check_http \
 --unix-socket /run/almapanel-api/http.sock http://localhost/api/health; then
 echo 'Inspect: sudo journalctl -u almapanel-api -u almapanel-agent -n 40 --no-pager' >&2
 exit 1
fi
if ! wait_for_health 'Panel HTTPS listener' check_http \
 --cacert /etc/almapanel/panel.crt --resolve "$hostname:8443:127.0.0.1" "$origin/api/health"; then
 echo 'Inspect: sudo ss -ltnp "sport = :8443" and sudo journalctl -u nginx -n 40 --no-pager' >&2
 exit 1
fi
if ! wait_for_health 'Privileged agent' timeout 6s runuser -u almapanel -- "$PANEL_PY" -I -c '
import sys
sys.path.insert(0, "/opt/almapanel")
from backend.core import rpc
print(rpc("system.stats"))
'; then
 echo 'Inspect: sudo journalctl -u almapanel-agent -n 40 --no-pager' >&2
 exit 1
fi
for unit in almapanel-agent almapanel-api almapanel-worker nginx "$PHP_UNIT"; do
 systemctl is-active --quiet "$unit" || { echo "$unit failed" >&2; exit 1; }
 echo "$unit: active"
done
