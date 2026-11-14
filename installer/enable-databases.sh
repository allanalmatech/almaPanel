#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
source /etc/os-release
engine=${1:-}
[[ $engine == mariadb || $engine == postgresql ]] || { echo 'Usage: enable-databases.sh mariadb|postgresql'; exit 2; }
[[ -d /etc/almapanel ]] || { echo 'Install almaPanel first.' >&2; exit 1; }
if [[ -e /etc/almapanel/database-engines ]] && awk -v engine="$engine" '$0==engine { found=1 } END { exit !found }' /etc/almapanel/database-engines; then
 echo "$engine is already configured."
 exit 0
fi

refuse_service() {
 if systemctl cat "$1" >/dev/null 2>&1; then
  echo "An existing $1 installation needs separate migration. Use a clean SQL server." >&2
  exit 1
 fi
}

case "$ID:$VERSION_ID:$engine" in
 ubuntu:24.04:mariadb)
  refuse_service mariadb.service
  apt-get install -y mariadb-server php8.3-mysql
  config=/etc/mysql/mariadb.conf.d
  php_unit=php8.3-fpm
  ;;
 amzn:2023:mariadb)
  refuse_service mariadb.service
  dnf install -y mariadb105-server mariadb105 php8.3-mysqlnd
  config=/etc/my.cnf.d
  php_unit=php-fpm
  ;;
 ubuntu:24.04:postgresql)
  refuse_service postgresql.service
  apt-get install -y postgresql-16 php8.3-pgsql
  php_unit=php8.3-fpm
  hba=/etc/postgresql/16/main/pg_hba.conf
  pgconfig=/etc/postgresql/16/main/postgresql.conf
  unit=postgresql@16-main.service
  ;;
 amzn:2023:postgresql)
  refuse_service postgresql.service
  dnf install -y postgresql16-server postgresql16 php8.3-pgsql
  postgresql-setup --initdb
  php_unit=php-fpm
  hba=/var/lib/pgsql/data/pg_hba.conf
  pgconfig=/var/lib/pgsql/data/postgresql.conf
  unit=postgresql.service
  ;;
 *) echo 'Unsupported database platform.' >&2; exit 1;;
esac

if [[ $engine == mariadb ]]; then
 install -d -m 755 "$config"
 printf '[mysqld]\nbind-address = 127.0.0.1\nlocal-infile = 0\ninnodb_buffer_pool_size = 64M\nmax_connections = 40\n' > "$config/90-almapanel.cnf"
 chmod 644 "$config/90-almapanel.cnf"
 systemctl enable --now mariadb.service
 systemctl restart mariadb.service
 mariadb --no-defaults --user=root --protocol=socket --batch --skip-column-names -e 'SELECT 1'
 # On a fresh package install, make root local socket-only before exposing the
 # service to hosting UIDs. Remove bootstrap anonymous and test access.
 mariadb --no-defaults --user=root --protocol=socket --batch <<'SQL'
ALTER USER 'root'@'localhost' IDENTIFIED VIA unix_socket;
DROP USER IF EXISTS ''@'localhost', ''@'localhost.localdomain';
DROP DATABASE IF EXISTS test;
SQL
 # Distribution initialization can add a root or anonymous account under the
 # machine hostname. Remove any remaining bootstrap entries on this fresh DB.
 mariadb --no-defaults --user=root --protocol=socket --batch --skip-column-names <<'SQL' |
SELECT CONCAT('DROP USER IF EXISTS ', QUOTE(User), '@', QUOTE(Host), ';') FROM mysql.user
WHERE User='' OR (User='root' AND Host<>'localhost');
SQL
 mariadb --no-defaults --user=root --protocol=socket --batch
else
 cp -p -- "$hba" "$hba.before-almapanel"
 cp -p -- "$pgconfig" "$pgconfig.before-almapanel"
 cat > "$hba" <<'HBA'
# almaPanel local database ownership isolation
local all postgres peer
local sameuser +almapanel_tenants scram-sha-256
local all +almapanel_tenants reject
host sameuser +almapanel_tenants 127.0.0.1/32 scram-sha-256
host all +almapanel_tenants 127.0.0.1/32 reject
host sameuser +almapanel_tenants ::1/128 scram-sha-256
host all +almapanel_tenants ::1/128 reject
HBA
 printf "\nlisten_addresses = 'localhost'\nunix_socket_directories = '/var/run/postgresql'\npassword_encryption = 'scram-sha-256'\nmax_connections = 40\nshared_buffers = '64MB'\n" >> "$pgconfig"
 systemctl enable --now "$unit"
 systemctl restart "$unit"
 runuser -u postgres -- psql -X -w -v ON_ERROR_STOP=1 -h /var/run/postgresql -d postgres -c \
  'CREATE ROLE almapanel_tenants NOLOGIN;'
fi

systemctl restart "$php_unit"
printf '%s\n' "$engine" >> /etc/almapanel/database-engines
chmod 600 /etc/almapanel/database-engines
echo "$engine is ready in almaPanel. Connections are local to this server."
