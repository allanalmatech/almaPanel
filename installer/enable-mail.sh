#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
if [[ $EUID -ne 0 || ! -f /opt/almapanel/VERSION || $# -lt 3 || $# -gt 4 ]]; then
 echo 'Usage: sudo bash installer/enable-mail.sh mail.example.com fullchain.pem privkey.pem [--public|--loopback]' >&2
 exit 2
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT/installer/platform.sh"
hostname=$1
case "${4:-}" in
 '') listen='' ;;
 --loopback|--public) listen=${4#--} ;;
 *) echo 'Use --public or --loopback for the listener.' >&2; exit 2 ;;
esac
"$PANEL_PY" -I - "$ROOT" "$hostname" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from backend.core import domain
domain(sys.argv[2])
PY
for certificate in "$2" "$3"; do
 [[ -f $certificate && -r $certificate ]] || { echo 'Supply a readable certificate chain and private key.' >&2; exit 2; }
done

state=/etc/almapanel/mail
install -d -m 700 "$state"
exec 8>"$state/lock"
flock -n 8 || { echo 'Wait for the other almaPanel mail operation to finish.' >&2; exit 1; }
configured=0
if [[ -f $state/profile.json ]]; then
 configured=1
 existing=$("$PANEL_PY" -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["hostname"])' "$state/profile.json")
 [[ $existing == "$hostname" ]] ||
  { echo 'Changing the mail hostname requires a migration.' >&2; exit 1; }
 if [[ -z $listen ]]; then
  listen=$("$PANEL_PY" -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["listen"])' "$state/profile.json")
 fi
elif [[ -f $state/installing ]]; then
 [[ $(cat "$state/installing") == "$hostname" ]] ||
  { echo 'Resume with the hostname from the previous attempt.' >&2; exit 1; }
else
 for unit in postfix.service dovecot.service exim4.service sendmail.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then
   echo "An existing $unit requires a migration plan." >&2
   exit 1
  fi
 done
 for port in 25 587 993; do
  if ss -H -ltn "sport = :$port" | awk 'NF {busy=1} END {exit !busy}'; then
   echo "Mail port $port is in use." >&2
   exit 1
  fi
 done
 if getent passwd almapanel-mail >/dev/null || [[ -e /var/vmail || -e /etc/postfix/main.cf || -e /etc/dovecot/dovecot.conf ]]; then
  echo 'Existing mail configuration, account or files detected. Use a clean mail host.' >&2
  exit 1
 fi
fi
case "${listen:-loopback}" in
 loopback) listen=loopback; smtp_listen=loopback-only; imap_listen=127.0.0.1 ;;
 public) smtp_listen=all; imap_listen=0.0.0.0 ;;
 *) echo 'Invalid listener setting in the installed mail profile.' >&2; exit 1 ;;
esac

stage=$(mktemp -d "$state/.setup.XXXXXXXX")
files=("$state/fullchain.pem" "$state/private.pem" /etc/dovecot/dovecot.conf /etc/postfix/main.cf /etc/postfix/master.cf)
changed=0
masked=0
finish() {
 local status=$? position
 trap - EXIT
 set +e
 if ((masked)); then
  systemctl unmask --runtime dovecot.service postfix.service
 fi
 if ((status)); then
  if ((changed)); then
   for position in "${!files[@]}"; do
    if [[ -f $stage/old-$position ]]; then
     cp -p -- "$stage/old-$position" "${files[position]}"
    else
     rm -f -- "${files[position]}"
    fi
   done
   if ((configured)); then
    systemctl daemon-reload
    systemctl restart dovecot.service postfix.service
   fi
  fi
  if ((!configured)) && [[ -f $state/installing ]]; then
   systemctl disable --now dovecot.service postfix.service 2>/dev/null
  fi
  echo 'Mail setup failed. Check journalctl -u dovecot -u postfix and rerun the same command after correcting the error.' >&2
 fi
 rm -rf -- "$stage"
 exit "$status"
}
trap finish EXIT
install -m 644 -- "$2" "$stage/fullchain.pem"
install -m 600 -- "$3" "$stage/private.pem"
openssl x509 -in "$stage/fullchain.pem" -noout -checkhost "$hostname" |
 awk '/does match certificate/{matched=1} END {exit !matched}'
openssl x509 -in "$stage/fullchain.pem" -noout -checkend 0
openssl x509 -in "$stage/fullchain.pem" -noout -pubkey > "$stage/chain.pub"
openssl pkey -in "$stage/private.pem" -passin pass: -pubout > "$stage/key.pub"
cmp "$stage/chain.pub" "$stage/key.pub"

if ((!configured)); then
 printf '%s\n' "$hostname" > "$state/installing"
 masked=1
 systemctl mask --runtime dovecot.service postfix.service
 if [[ $ID == amzn ]]; then
  dnf install -y postfix dovecot
 else
  printf 'postfix postfix/main_mailer_type select No configuration\n' | debconf-set-selections
  DEBIAN_FRONTEND=noninteractive apt-get install -y postfix dovecot-core dovecot-imapd dovecot-lmtpd
 fi
fi
if ! getent passwd almapanel-mail >/dev/null; then
 useradd --system --user-group --no-create-home --home-dir /var/vmail --shell /usr/sbin/nologin almapanel-mail
fi
mail_uid=$(id -u almapanel-mail)
mail_gid=$(id -g almapanel-mail)
install -d -m 750 -o almapanel-mail -g almapanel-mail /var/vmail
install -d -m 750 -o root -g postfix /etc/postfix/almapanel
install -d -m 755 /etc/dovecot/almapanel
for map in domains recipients aliases senders; do
 map_path=/etc/postfix/almapanel/$map
 [[ -f $map_path ]] || install -m 644 /dev/null "$map_path"
done
passwd_path=/etc/dovecot/almapanel/passwd
[[ -f $passwd_path ]] || install -m 640 -o root -g dovecot /dev/null "$passwd_path"
for position in "${!files[@]}"; do
 if [[ -f ${files[position]} ]]; then cp -p -- "${files[position]}" "$stage/old-$position"; fi
done
if ((configured)); then
 cp -p /etc/postfix/main.cf "$stage/main.cf"
else
 install -m 644 /dev/null "$stage/main.cf"
fi
cp -p /etc/postfix/master.cf "$stage/master.cf"
sed -e "s/@HOST@/$hostname/g" -e "s/@LISTEN@/$smtp_listen/g" \
 "$ROOT/services/mail/postfix-main.conf" > "$stage/alma-main.cf"
while IFS= read -r setting; do
 [[ -z $setting || $setting == \#* ]] || postconf -c "$stage" -e "$setting"
done < "$stage/alma-main.cf"
postconf -c "$stage" -m | awk '$0=="texthash"{supported=1} END {exit !supported}'
postconf -c "$stage" -a | awk '$0=="dovecot"{supported=1} END {exit !supported}'
postconf -c "$stage" -M 'submission/inet=submission inet n - n - - smtpd'
while IFS= read -r setting; do
 [[ -z $setting || $setting == \#* ]] || postconf -c "$stage" -P "submission/inet/$setting"
done < "$ROOT/services/mail/postfix-submission.conf"
sed -e "s/@UID@/$mail_uid/g" -e "s/@GID@/$mail_gid/g" -e "s/@LISTEN@/$imap_listen/g" \
 "$ROOT/services/mail/dovecot-alma.conf" > "$stage/dovecot.conf"
changed=1
install -m 644 "$stage/fullchain.pem" "$state/fullchain.pem"
install -m 600 "$stage/private.pem" "$state/private.pem"
install -m 644 "$stage/dovecot.conf" /etc/dovecot/dovecot.conf
install -m 644 "$stage/main.cf" /etc/postfix/main.cf
install -m 644 "$stage/master.cf" /etc/postfix/master.cf
doveconf -n >/dev/null
postfix check
if ((masked)); then
 systemctl unmask --runtime dovecot.service postfix.service
 masked=0
fi
systemctl daemon-reload
systemctl restart dovecot.service postfix.service
systemctl is-active --quiet dovecot.service
systemctl is-active --quiet postfix.service
for port in 25 587 993; do
 for attempt in {1..20}; do
  if ss -H -ltn "sport = :$port" | awk 'NF {ready=1} END {exit !ready}'; then break; fi
  sleep 0.25
 done
 if ((attempt == 20)) && ! ss -H -ltn "sport = :$port" | awk 'NF {ready=1} END {exit !ready}'; then
  echo "Mail port $port failed to start." >&2
  exit 1
 fi
done
systemctl enable dovecot.service postfix.service
printf '{"hostname":"%s","uid":%s,"gid":%s,"listen":"%s"}\n' "$hostname" "$mail_uid" "$mail_gid" "$listen" > "$stage/profile.json"
mv -- "$stage/profile.json" "$state/profile.json"
rm -f -- "$state/installing"
echo "Mail services listening on $imap_listen on TCP 25, 587 and 993 for $hostname. See docs/MAIL.md to test delivery."
