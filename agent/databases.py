# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Local SQL provisioning via a fixed set of administrative statements."""
import hashlib
from pathlib import Path
import re
import secrets

from backend.core import name

CONFIG = Path('/etc/almapanel/database-engines')
MARIA = '/usr/bin/mariadb'
PGSQL = '/usr/bin/psql'
ENGINES = {'mariadb': 3306, 'postgresql': 5432}
LABEL = re.compile(r'[a-z][a-z0-9]{0,23}\Z')
SECRET = re.compile(r'[A-Za-z0-9_~-]{16,96}\Z')
MAX_DATABASES = 10


def installed():
    if not CONFIG.is_file():
        return []
    return [engine for engine in CONFIG.read_text().splitlines() if engine in ENGINES]


def label(value):
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise ValueError('Use 1–24 lowercase letters and digits, starting with a letter.')
    return value


def identifier(account, slug):
    name(account)
    label(slug)
    # No LIKE wildcards in MariaDB identifiers. Names stay under both engines' limits.
    hashed = hashlib.sha256(f'{account}/{slug}'.encode()).hexdigest()[:24]
    return f'ap{hashed}'


def mariadb(run, sql):
    return run([MARIA, '--no-defaults', '--user=root', '--protocol=socket',
                '--batch', '--skip-column-names', '--binary-mode'], input=sql)


def postgres(run, sql, db='postgres'):
    return run(['/usr/sbin/runuser', '-u', 'postgres', '--', PGSQL,
                '--no-psqlrc', '--no-password', '--set=ON_ERROR_STOP=1',
                '--tuples-only', '--no-align', '--host=/var/run/postgresql', '--dbname', db], input=sql)


def new_password(value):
    if value is None or value == '':
        return secrets.token_urlsafe(24)
    if not isinstance(value, str) or not SECRET.fullmatch(value):
        raise ValueError('Use 16–96 letters, numbers, underscores, hyphens or tildes.')
    return value


def sql_error():
    # Client stderr and SQL bodies can contain credentials. Never return or log them.
    raise ValueError('Database server rejected the operation. Check the service and its configuration.') from None


def maria_name_exists(run, bare):
    result = mariadb(run, f"""SELECT
      (SELECT COUNT(*) FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='{bare}') +
      (SELECT COUNT(*) FROM mysql.user WHERE User='{bare}');""")
    return result.strip() != '0'


def pg_name_exists(run, bare):
    return postgres(run, f"""SELECT
      (SELECT COUNT(*) FROM pg_database WHERE datname='{bare}') +
      (SELECT COUNT(*) FROM pg_roles WHERE rolname='{bare}');""").strip() != '0'


def pg_guard(run):
    rules = postgres(run, """SELECT count(*) FROM pg_hba_file_rules
      WHERE error IS NULL AND 'almapanel_tenants' = ANY (
          ARRAY(SELECT replace(value, '+', '') FROM unnest(user_name) AS value))
      AND auth_method IN ('reject', 'scram-sha-256');""")
    if rules.strip() != '6':
        raise ValueError('The managed PostgreSQL tenant authentication rules are missing.')


def create(engine, bare, password, run):
    if engine == 'mariadb':
        if maria_name_exists(run, bare):
            raise ValueError('This database or login already exists outside the panel registry.')
        mariadb(run, f"CREATE DATABASE `{bare}` CHARACTER SET utf8mb4;")
        created = False
        try:
            mariadb(run, f"CREATE USER '{bare}'@'localhost' IDENTIFIED BY '{password}';")
            created = True
            mariadb(run, f"GRANT ALL PRIVILEGES ON `{bare}`.* TO '{bare}'@'localhost';")
        except Exception:
            try:
                if created:
                    mariadb(run, f"DROP USER IF EXISTS '{bare}'@'localhost';")
            finally:
                mariadb(run, f"DROP DATABASE IF EXISTS `{bare}`;")
            raise
    else:
        pg_guard(run)
        if pg_name_exists(run, bare):
            raise ValueError('This database or login already exists outside the panel registry.')
        postgres(run, f"""CREATE ROLE "{bare}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                 NOREPLICATION NOBYPASSRLS IN ROLE almapanel_tenants PASSWORD '{password}';""")
        try:
            postgres(run, f'CREATE DATABASE "{bare}" OWNER "{bare}" TEMPLATE template0;')
        except Exception:
            postgres(run, f'DROP ROLE IF EXISTS "{bare}";')
            raise
        try:
            postgres(run, f'REVOKE CONNECT, TEMPORARY ON DATABASE "{bare}" FROM PUBLIC;')
        except Exception:
            drop(engine, bare, run)
            raise


def drop(engine, bare, run):
    if engine == 'mariadb':
        mariadb(run, f"DROP DATABASE IF EXISTS `{bare}`; DROP USER IF EXISTS '{bare}'@'localhost';")
    else:
        postgres(run, f'DROP DATABASE IF EXISTS "{bare}" WITH (FORCE); DROP ROLE IF EXISTS "{bare}";')


def connection(item, bare):
    return {'engine': item['engine'], 'label': item['label'], 'database': bare, 'username': bare,
            'host': 'localhost' if item['engine'] == 'mariadb' else '127.0.0.1',
            'database_port': ENGINES[item['engine']]}


def usage(engine, bare, run):
    if engine == 'mariadb':
        result = mariadb(run, f"""SELECT IFNULL(SUM(DATA_LENGTH+INDEX_LENGTH),0)
            FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{bare}';""")
    else:
        result = postgres(run, f"SELECT pg_database_size('{bare}');")
    return int(result.strip())


def manage(operation, account, meta, args, run, persist):
    import subprocess

    inventory = meta.setdefault('databases', {})
    enabled = installed()
    if operation == 'database.list':
        return {'engines': enabled, 'limit': MAX_DATABASES, 'databases': [
            connection(item, identifier(account, slug)) for slug, item in sorted(inventory.items())
        ]}
    slug = label(args.get('label'))
    bare = identifier(account, slug)
    item = inventory.get(slug)
    try:
        if operation == 'database.create':
            engine = args.get('engine')
            if engine not in enabled:
                raise ValueError('The server administrator must enable this engine first.')
            if item:
                raise ValueError('This database label is already in use.')
            if len(inventory) >= MAX_DATABASES:
                raise ValueError('Account database limit reached.')
            password = new_password(args.get('password'))
            create(engine, bare, password, run)
            item = {'engine': engine, 'label': slug}
            inventory[slug] = item
            try:
                persist()
            except OSError:
                drop(engine, bare, run)
                raise
            return {**connection(item, bare), 'password': password}
        if not item:
            raise ValueError('Database does not belong to this account.')
        engine = item['engine']
        if operation == 'database.usage':
            return {'bytes': usage(engine, bare, run)}
        if operation == 'database.password':
            password = new_password(args.get('password'))
            if engine == 'mariadb':
                mariadb(run, f"ALTER USER '{bare}'@'localhost' IDENTIFIED BY '{password}';")
            else:
                postgres(run, f'ALTER ROLE "{bare}" PASSWORD \'{password}\';')
            return {**connection(item, bare), 'password': password}
        if operation == 'database.delete':
            if args.get('confirm') != slug:
                raise ValueError('Type the database label to confirm deletion.')
            drop(engine, bare, run)
            del inventory[slug]
            persist()
            return {'message': 'Database and its login deleted.'}
        raise ValueError('Database operation not allowed.')
    except subprocess.SubprocessError:
        sql_error()
