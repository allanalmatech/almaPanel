#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ACCEPT=0; PREFLIGHT=0; PUBLIC=0; HOST=localhost
while (($#)); do
 case "$1" in
 --accept-alpha) ACCEPT=1;;
 --preflight) PREFLIGHT=1;;
 --public-panel) PUBLIC=1;;
 --hostname) [[ $# -ge 2 ]] || exit 2; HOST=$2; shift;;
 --help) echo 'Usage: sudo bash installer/install.sh [--preflight] [--accept-alpha] [--public-panel --hostname panel.example.com]'; exit 0;;
 *) echo "Unknown argument: $1" >&2; exit 2;;
 esac
 shift
done
fail(){ echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run as root.'
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || fail 'Only Ubuntu 24.04 LTS is targeted. No other distribution adapter is validated.'
case "$(uname -m)" in x86_64|aarch64) ;; *) fail 'Only amd64 and arm64 are targeted.';; esac
[[ $(ps -p 1 -o comm=) == systemd ]] || fail 'A full systemd VM is required, not an application container.'
[[ $HOST == localhost || $HOST =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] || fail 'Invalid hostname.'
[[ ${#HOST} -le 253 ]] || fail 'Hostname too long.'
(( ! PUBLIC )) || [[ $HOST != localhost ]] || fail '--public-panel requires a DNS hostname.'
[[ $(awk '/MemTotal/{print $2}' /proc/meminfo) -ge 900000 ]] || fail 'At least approximately 1 GiB RAM is required. 2 GiB recommended.'
[[ $(df -Pm / | awk 'NR==2 {print $4}') -ge 5120 ]] || fail 'At least 5 GiB free disk required.'
for path in /opt/almapanel /etc/almapanel /var/lib/almapanel /var/lib/almapanel-agent /srv/almapanel; do
 [[ ! -e $path ]] || fail "Existing state at $path. Use diagnostics and documented recovery; installation refuses overwrite."
done
! getent passwd almapanel >/dev/null || fail 'almapanel system user already exists.'
for service in nginx apache2 mysql mariadb postgresql postfix dovecot named bind9 php8.3-fpm; do
 if systemctl cat "$service.service" >/dev/null 2>&1; then fail "Existing service $service detected. Use a clean VM; migration is not automated."; fi
done
for port in 80 443 8443 9080; do
 if ss -H -ltn "sport = :$port" | read -r _; then fail "TCP port $port is occupied."; fi
done
getent ahosts archive.ubuntu.com >/dev/null || fail 'DNS resolution failed.'
if (( PREFLIGHT )); then
 echo 'Local preflight passed. No changes made. APT connectivity, TLS and service execution remain to be tested.'
 exit 0
fi
if (( ! ACCEPT )); then
 [[ -r /dev/tty ]] || fail 'Noninteractive alpha install requires --accept-alpha.'
 echo 'almaPanel by Alma Tech Labs Inc. — evaluation alpha, not production certified.'
 read -r -p 'Type INSTALL-ALPHA to install on this clean server: ' consent </dev/tty
 [[ $consent == INSTALL-ALPHA ]] || fail 'Installation cancelled.'
fi
install -d -m 700 /var/log/almapanel
exec > >(tee -a /var/log/almapanel/install.log) 2>&1
trap 'rc=$?; echo "Installation failed (exit $rc, line $LINENO). Preserve /var/log/almapanel/install.log. Do not rerun blindly. See docs/TROUBLESHOOTING.md."; exit "$rc"' ERR
exec 9>/run/almapanel-install.lock
flock -n 9 || fail 'Another installer is running.'
echo '[1/7] Installing Ubuntu repository packages'
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get -o Acquire::Retries=3 install -y --no-install-recommends python3 python3-waitress nginx php8.3-fpm php8.3-cli acl openssl curl ca-certificates rsync git
# No third-party PPAs, application downloads, default passwords, or firewall resets.
echo '[2/7] Creating dedicated control-plane identity'
useradd --system --user-group --home-dir /var/lib/almapanel --shell /usr/sbin/nologin almapanel
install -d -m 700 -o almapanel -g almapanel /var/lib/almapanel
install -d -m 700 /var/lib/almapanel-agent /etc/almapanel /var/backups/almapanel
install -d -m 711 /srv/almapanel /srv/almapanel/accounts
install -d -m 755 /opt/almapanel
rsync -a --exclude=.git --exclude=__pycache__ --exclude=dist --exclude=.coverage --exclude='*.pyc' "$ROOT/" /opt/almapanel/
chown -R root:root /opt/almapanel
chmod -R go-w /opt/almapanel
echo '[3/7] Initializing panel database and one-time setup token'
runuser -u almapanel -- env PYTHONPATH=/opt/almapanel /usr/bin/python3 -c 'from backend.core import initialize; initialize()'
if (( PUBLIC )); then BIND=0.0.0.0; ORIGIN="https://$HOST:8443"; else BIND=127.0.0.1; ORIGIN=https://localhost:8443; fi
printf 'ALMA_ORIGIN=%s\nALMA_STATE=/var/lib/almapanel\n' "$ORIGIN" > /etc/almapanel/panel.env
chmod 600 /etc/almapanel/panel.env
echo '[4/7] Creating local TLS certificate'
openssl req -x509 -newkey rsa:3072 -sha256 -days 30 -nodes -keyout /etc/almapanel/panel.key -out /etc/almapanel/panel.crt -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
chmod 600 /etc/almapanel/panel.key
sed -e "s/@BIND@/$BIND/g" -e "s/@HOST@/$HOST/g" /opt/almapanel/services/nginx/panel.conf > /etc/nginx/conf.d/almapanel.conf
# Only the default site installed in this transaction is removed.
rm -f /etc/nginx/sites-enabled/default
install -m 644 /opt/almapanel/services/nginx/default.conf /etc/nginx/conf.d/almapanel-default.conf
# Remove package's shared PHP pool; each hosting account gets a private ondemand pool.
mv /etc/php/8.3/fpm/pool.d/www.conf /etc/almapanel/package-www.conf.disabled
# PHP-FPM requires one pool to start before any hosting accounts exist.
install -m 644 /opt/almapanel/services/php/idle.conf /etc/php/8.3/fpm/pool.d/alma-idle.conf
echo '[5/7] Installing systemd services'
install -m 644 /opt/almapanel/services/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now almapanel-agent almapanel-api almapanel-worker
/usr/sbin/nginx -t
/usr/sbin/php-fpm8.3 -t
systemctl enable nginx php8.3-fpm
systemctl restart php8.3-fpm nginx
echo '[6/7] Checking installed service health'
bash /opt/almapanel/installer/healthcheck.sh
dpkg-query -W -f='${Package}\t${Version}\n' python3 python3-waitress nginx php8.3-fpm > /etc/almapanel/package-versions.txt
echo '[7/7] Installation completed'
echo "almaPanel URL: $ORIGIN"
echo "Administrator setup: $ORIGIN (select First installation)"
echo "Version: $(cat /opt/almapanel/VERSION) | OS: $PRETTY_NAME"
echo 'Retrieve setup token locally: sudo cat /var/lib/almapanel/setup-token'
echo 'Configuration: /etc/almapanel | Log: /var/log/almapanel + systemd journal'
echo 'Documentation: /opt/almapanel/docs and /opt/almapanel/DEPLOYMENT.md'
echo 'Local certificate expires in 30 days. Verify its fingerprint over SSH before trusting it:'
openssl x509 -in /etc/almapanel/panel.crt -noout -fingerprint -sha256
if (( ! PUBLIC )); then echo 'Access tunnel: ssh -L 8443:127.0.0.1:8443 ubuntu@YOUR_EC2_IP'; fi
echo 'Host firewall and AWS security groups were preserved. Configure access explicitly; see DEPLOYMENT.md.'
echo 'This is an evaluation install. Production release gates remain open.'
