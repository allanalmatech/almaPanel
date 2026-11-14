#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 && -d /etc/almapanel ]] || { echo 'Run as root on an almaPanel host.' >&2; exit 1; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
port=2222
listen=127.0.0.1
while (($#)); do
 case "$1" in
  --port) [[ $# -ge 2 ]]; port=$2; shift ;;
  --public) listen=0.0.0.0 ;;
  *) echo 'Usage: enable-sftp.sh [--port 2222] [--public]' >&2; exit 2 ;;
 esac
 shift
done
[[ $port =~ ^[1-9][0-9]{3,4}$ ]] && ((port >= 1024 && port <= 65535 && port != 8443 && port != 9080)) ||
 { echo 'Choose an unused port from 1024 to 65535, excluding panel ports 8443 and 9080.' >&2; exit 2; }
if [[ -f /etc/almapanel/sftp/profile.json ]]; then
 echo 'The separate SFTP listener is already configured.'
 exit 0
fi
[[ -x /usr/sbin/sshd && -x /usr/bin/ssh-keygen ]] ||
 { echo 'Install the OpenSSH server and ssh-keygen for your distribution.' >&2; exit 1; }
if ss -H -ltn "sport = :$port" | awk 'NF {occupied=1} END {exit !occupied}'; then
 echo "TCP port $port is already in use." >&2
 exit 1
fi
# sshd reads public key files with the target login's privileges. This public
# key directory must have a traversable parent independent of /etc/almapanel.
install -d -m 755 /etc/almapanel-sftp-keys
install -d -m 700 /etc/almapanel/sftp
if [[ ! -f /etc/almapanel/sftp/host_ed25519 ]]; then
 ssh-keygen -q -t ed25519 -N '' -f /etc/almapanel/sftp/host_ed25519
fi
sed -e "s/@PORT@/$port/g" -e "s/@LISTEN@/$listen/g" \
 "$ROOT/services/sftp/sshd_config" > /etc/almapanel/sftp/sshd_config
/usr/sbin/sshd -t -f /etc/almapanel/sftp/sshd_config
install -m 644 "$ROOT/services/systemd/almapanel-sftp.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now almapanel-sftp.service
systemctl is-active --quiet almapanel-sftp.service
printf '{"port":%s,"listen":"%s"}\n' "$port" "$listen" > /etc/almapanel/sftp/profile.json
echo "almaPanel SFTP is listening on $listen:$port. The system SSH listener uses its existing configuration."
ssh-keygen -lf /etc/almapanel/sftp/host_ed25519.pub
