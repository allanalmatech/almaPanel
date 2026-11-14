#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ACCEPT=0; PREFLIGHT=0; PUBLIC=0; RESUME=0; HOST=localhost
while (($#)); do
 case "$1" in
 --accept-alpha) ACCEPT=1;;
 --preflight) PREFLIGHT=1;;
 --resume-identity) RESUME=1;;
 --public-panel) PUBLIC=1;;
 --hostname) [[ $# -ge 2 ]] || exit 2; HOST=$2; shift;;
 --help) echo 'Usage: sudo bash installer/install.sh [--preflight] [--accept-alpha] [--resume-identity] [--public-panel --hostname panel.example.com]'; exit 0;;
 *) echo "Unknown argument: $1" >&2; exit 2;;
 esac
 shift
done
fail(){ echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run as root.'
source "$ROOT/installer/platform.sh"
if [[ $ID == amzn && -x /usr/sbin/getenforce ]] && [[ $(/usr/sbin/getenforce) == Enforcing ]]; then
 fail 'SELinux enforcing support is pending. This installer will not change the host policy.'
fi
case "$(uname -m)" in x86_64|aarch64) ;; *) fail 'Only amd64 and arm64 are targeted.';; esac
[[ $(ps -p 1 -o comm=) == systemd ]] || fail 'A full systemd VM is required, not an application container.'
[[ $HOST == localhost || $HOST =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] || fail 'Invalid hostname.'
[[ ${#HOST} -le 253 ]] || fail 'Hostname too long.'
(( ! PUBLIC )) || [[ $HOST != localhost ]] || fail '--public-panel requires a DNS hostname.'
[[ $(awk '/MemTotal/{print $2}' /proc/meminfo) -ge 900000 ]] || fail 'At least approximately 1 GiB RAM is required. 2 GiB recommended.'
[[ $(df -Pm / | awk 'NR==2 {print $4}') -ge 5120 ]] || fail 'At least 5 GiB free disk required.'
if (( RESUME )); then
 [[ $ID == amzn ]] || fail 'Identity-stage resume is for Amazon Linux 2023.'
 [[ $(getent passwd almapanel | cut -d: -f6,7) == /var/lib/almapanel:/usr/sbin/nologin ]] ||
  fail 'Expected almaPanel system identity is missing.'
 for path in /opt/almapanel /etc/almapanel /var/lib/almapanel /var/lib/almapanel-agent /srv/almapanel /srv/almapanel/accounts /var/backups/almapanel; do
  [[ -d $path && ! -L $path ]] || fail "Unexpected install directory: $path"
 done
 for path in /etc/almapanel /var/lib/almapanel /var/lib/almapanel-agent /srv/almapanel/accounts; do
  [[ -z $(find "$path" -mindepth 1 -print -quit) ]] || fail "Resume requires empty state at $path."
 done
 [[ $(stat -c '%U:%G' /var/lib/almapanel) == almapanel:almapanel ]] || fail 'Unexpected state directory ownership.'
 [[ -f /var/log/almapanel/install.log && -f /opt/almapanel/venv/pyvenv.cfg ]] || fail 'Partial installation was not found.'
 for path in /etc/nginx/conf.d/almapanel.conf /etc/nginx/conf.d/almapanel-default.conf "$PHP_POOL/alma-idle.conf" /etc/systemd/system/php-fpm.service.d/almapanel.conf; do
  [[ ! -e $path && ! -L $path ]] || fail "Resume found configured state at $path."
 done
 [[ -f "$PHP_POOL/www.conf" ]] || fail 'Expected package PHP pool is missing.'
 rpm -q nginx php8.3-fpm python3.12 python3.12-pip >/dev/null || fail 'Required packages are missing.'
else
 for path in /opt/almapanel /etc/almapanel /var/lib/almapanel /var/lib/almapanel-agent /srv/almapanel; do
  [[ ! -e $path && ! -L $path ]] || fail "Existing state at $path. Use diagnostics and documented recovery."
 done
 ! getent passwd almapanel >/dev/null || fail 'almapanel system user already exists.'
fi
for service in almapanel-api almapanel-agent almapanel-worker nginx apache2 httpd mysql mysqld mariadb postgresql postfix dovecot named bind9 php8.3-fpm php-fpm; do
 if (( RESUME )) && [[ $service == nginx || $service == php-fpm ]]; then
  systemctl is-active --quiet "$service.service" && fail "Existing active service $service detected."
  continue
 fi
 if systemctl cat "$service.service" >/dev/null 2>&1; then fail "Existing service $service detected. Use a clean VM; migration is not automated."; fi
done
for port in 80 443 8443 9080; do
 if ss -H -ltn "sport = :$port" | read -r _; then fail "TCP port $port is occupied."; fi
done
if [[ $ID == ubuntu ]]; then
 getent ahosts archive.ubuntu.com >/dev/null || fail 'Ubuntu repository DNS resolution failed.'
else
 dnf -q list php8.3-fpm nginx python3.12 python3.12-pip >/dev/null || fail 'Required packages are unavailable in the configured Amazon Linux repositories.'
 getent ahosts pypi.org >/dev/null || fail 'PyPI DNS resolution failed.'
fi
if (( PREFLIGHT )); then
 echo 'Local preflight passed. No changes made. Package installation, TLS and service execution remain to be tested.'
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
if (( ! RESUME )); then
echo '[1/7] Installing platform packages'
if [[ $ID == ubuntu ]]; then
 export DEBIAN_FRONTEND=noninteractive
 apt-get -o Acquire::Retries=3 update
 apt-get -o Acquire::Retries=3 install -y --no-install-recommends python3 python3-waitress nginx php8.3-fpm php8.3-cli acl openssl curl ca-certificates rsync git
else
 dnf install -y python3.12 python3.12-pip nginx php8.3-fpm php8.3-cli acl openssl ca-certificates rsync git
fi
echo '[2/7] Creating dedicated control-plane identity'
useradd --system --user-group --home-dir /var/lib/almapanel --shell /usr/sbin/nologin almapanel
install -d -m 700 -o almapanel -g almapanel /var/lib/almapanel
install -d -m 700 /var/lib/almapanel-agent /etc/almapanel /var/backups/almapanel
install -d -m 711 /srv/almapanel /srv/almapanel/accounts
install -d -m 755 /opt/almapanel
fi
rsync -a --chmod=D755,Fu=rw,Fgo=r --exclude=/venv --exclude=.env --exclude=.git --exclude=__pycache__ --exclude=dist --exclude=.coverage --exclude='*.pyc' "$ROOT/" /opt/almapanel/
if (( RESUME )); then
 # The old installer created this root-owned virtual environment under umask 077.
 chmod -R a+rX,go-w /opt/almapanel/venv
fi
chown -R root:root /opt/almapanel
chmod -R go-w /opt/almapanel
if [[ $ID == amzn ]]; then
 (
 umask 022
 /usr/bin/python3.12 -m venv /opt/almapanel/venv
 "$PANEL_PY" -m pip --isolated install --index-url https://pypi.org/simple --disable-pip-version-check --only-binary=:all: --require-hashes -r /opt/almapanel/installer/requirements-al2023.txt
 )
fi
echo '[3/7] Initializing panel database and one-time setup token'
runuser -u almapanel -- env PYTHONPATH=/opt/almapanel "$PANEL_PY" -c 'from backend.core import initialize; initialize()'
if (( PUBLIC )); then BIND=0.0.0.0; ORIGIN="https://$HOST:8443"; else BIND=127.0.0.1; ORIGIN=https://localhost:8443; fi
printf 'ALMA_ORIGIN=%s\nALMA_STATE=/var/lib/almapanel\n' "$ORIGIN" > /etc/almapanel/panel.env
printf 'ALMA_PHP_UNIT=%s\nALMA_PHP_BIN=%s\nALMA_PHP_POOL=%s\nALMA_PHP_RUN=%s\nALMA_WEB_USER=%s\n' \
 "$PHP_UNIT" "$PHP_BIN" "$PHP_POOL" "$PHP_RUN" "$WEB_USER" > /etc/almapanel/agent.env
chmod 600 /etc/almapanel/panel.env /etc/almapanel/agent.env
echo '[4/7] Creating local TLS certificate'
openssl req -x509 -newkey rsa:3072 -sha256 -days 30 -nodes -keyout /etc/almapanel/panel.key -out /etc/almapanel/panel.crt -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
chmod 600 /etc/almapanel/panel.key
sed -e "s/@BIND@/$BIND/g" -e "s/@HOST@/$HOST/g" /opt/almapanel/services/nginx/panel.conf > /etc/nginx/conf.d/almapanel.conf
# Only the default site installed in this transaction is removed.
if [[ $ID == ubuntu ]]; then
 rm -f /etc/nginx/sites-enabled/default
else
 cp -p /etc/nginx/nginx.conf /etc/almapanel/package-nginx.conf
 install -m 644 /opt/almapanel/services/nginx/amazon-linux.conf /etc/nginx/nginx.conf
 install -d -m 755 /etc/systemd/system/php-fpm.service.d
 printf '[Service]\nRuntimeDirectory=php-fpm\n' > /etc/systemd/system/php-fpm.service.d/almapanel.conf
fi
install -m 644 /opt/almapanel/services/nginx/default.conf /etc/nginx/conf.d/almapanel-default.conf
# Remove package's shared PHP pool; each hosting account gets a private ondemand pool.
mv "$PHP_POOL/www.conf" /etc/almapanel/package-www.conf.disabled
# PHP-FPM requires one pool to start before any hosting accounts exist.
sed -e "s@/run/php/@$PHP_RUN/@g" -e "s/^group = nogroup$/group = $(id -gn nobody)/" \
 /opt/almapanel/services/php/idle.conf > "$PHP_POOL/alma-idle.conf"
echo '[5/7] Installing systemd services'
for unit in /opt/almapanel/services/systemd/almapanel-{agent,api,worker,update}.service; do
 sed -e "s@^ExecStart=/usr/bin/python3 @ExecStart=$PANEL_PY @" \
     -e "s/^Group=www-data$/Group=$WEB_USER/" "$unit" > "/etc/systemd/system/${unit##*/}"
 chmod 644 "/etc/systemd/system/${unit##*/}"
done
install -m 644 /opt/almapanel/services/systemd/almapanel-update.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now almapanel-agent almapanel-api almapanel-worker
/usr/sbin/nginx -t
"$PHP_BIN" -t
systemctl enable nginx "$PHP_UNIT"
systemctl restart "$PHP_UNIT" nginx
echo '[6/7] Checking installed service health'
bash /opt/almapanel/installer/healthcheck.sh
if [[ $ID == ubuntu ]]; then
 dpkg-query -W -f='${Package}\t${Version}\n' python3 python3-waitress nginx php8.3-fpm > /etc/almapanel/package-versions.txt
else
 rpm -q python3.12 python3.12-pip nginx php8.3-fpm > /etc/almapanel/package-versions.txt
fi
echo '[7/7] Installation completed'
echo "almaPanel URL: $ORIGIN"
echo "Administrator setup: $ORIGIN (select First installation)"
echo "Version: $(cat /opt/almapanel/VERSION) | OS: $PRETTY_NAME"
echo 'Retrieve setup token locally: sudo cat /var/lib/almapanel/setup-token'
echo 'Configuration: /etc/almapanel | Log: /var/log/almapanel + systemd journal'
echo 'Documentation: /opt/almapanel/docs and /opt/almapanel/DEPLOYMENT.md'
echo 'Local certificate expires in 30 days. Verify its fingerprint over SSH before trusting it:'
openssl x509 -in /etc/almapanel/panel.crt -noout -fingerprint -sha256
if (( ! PUBLIC )); then
 SSH_USER=ubuntu
 [[ $ID != amzn ]] || SSH_USER=ec2-user
 echo "Access tunnel: ssh -L 8443:127.0.0.1:8443 $SSH_USER@YOUR_EC2_IP"
fi
echo 'Host firewall and AWS security groups were preserved. Configure access explicitly; see DEPLOYMENT.md.'
echo 'This is an evaluation install. Production release gates remain open.'
