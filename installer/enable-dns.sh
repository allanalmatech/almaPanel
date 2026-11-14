#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 022
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT/installer/platform.sh"
[[ -d /etc/almapanel && $# -ge 1 && $# -le 4 ]] || { echo 'Usage: enable-dns.sh ns1.example.com [ns2.example.com ...]'; exit 2; }
[[ ! -e /etc/almapanel/dns-profile.json ]] || { echo 'Managed DNS is already configured.'; exit 0; }
if systemctl cat named.service >/dev/null 2>&1; then
 echo 'An existing BIND installation requires separate migration.' >&2
 exit 1
fi
if ss -H -lntu 'sport = :53' | awk '$5 !~ /^127\.0\.0\.(53|54)(%lo)?:53$/ && $5 !~ /^\[::1\]:53$/ { occupied=1 } END { exit !occupied }'; then
 echo 'DNS port 53 is in use.' >&2
 exit 1
fi
if [[ $ID == ubuntu ]]; then layout=ubuntu; directory=/etc/bind; main=/etc/bind/named.conf; else
 layout=amazon; directory=/var/named; main=/etc/named.conf
fi
profile=$("$PANEL_PY" - "$ROOT" "$layout" "$@" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
from backend.core import domain
print(json.dumps({'layout': sys.argv[2], 'nameservers': [domain(x) for x in dict.fromkeys(sys.argv[3:])]}))
PY
)
if [[ $ID == ubuntu ]]; then
 apt-get install -y bind9 bind9-utils
 # On Ubuntu's resolved hosts, the loopback stub remains available.
 options=/var/cache/bind
else
 dnf install -y bind bind-utils
 options=/var/named
fi
if [[ $ID == ubuntu ]]; then
 # Enumerate assigned non-loopback addresses to coexist with systemd-resolved.
 listen4=$(ip -o -4 addr show scope global | awk '{sub(/\/.*/, "", $4); printf "%s; ", $4}')
 listen6=$(ip -o -6 addr show scope global | awk '{sub(/\/.*/, "", $4); printf "%s; ", $4}')
 listen4=${listen4:-none;}
 listen6=${listen6:-none;}
else
 listen4='any;'
 listen6='any;'
fi
cp -p -- "$main" "$main.package-before-almapanel"
install -m 644 /dev/null "$directory/almapanel-zones.conf"
cat > "$main" <<CONF
options {
 directory "$options";
 listen-on port 53 { $listen4 };
 listen-on-v6 port 53 { $listen6 };
 recursion no;
 allow-query { any; };
 allow-transfer { none; };
 version none;
};
include "$directory/almapanel-zones.conf";
CONF
if ! named-checkconf -z || ! systemctl restart named.service; then
 cp -p -- "$main.package-before-almapanel" "$main"
 echo 'DNS configuration failed validation or startup. Package configuration restored.' >&2
 exit 1
fi
systemctl enable named.service
printf '%s\n' "$profile" > /etc/almapanel/dns-profile.json
chmod 600 /etc/almapanel/dns-profile.json
echo 'Authoritative DNS is available to panel administrators. Configure delegation and required EC2 rules separately.'
