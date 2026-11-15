# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Logical, account-scoped database backup and recovery."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile
import warnings

from agent import databases, sqltransfer
from backend.core import name
from installer.backup_stream import stream

DB_LIMIT = 128 * 1024 * 1024
DB_SUFFIX = {'mariadb': '.sql', 'postgresql': '.pgdump'}
REGISTRATION = 'database-logins.json'

# A single-transaction MariaDB snapshot guarantees consistency for InnoDB
# tables. Refuse objects that this portable table-only workflow cannot restore.
MARIA_UNSUPPORTED = """SELECT
  (SELECT COUNT(*) FROM information_schema.TABLES
   WHERE TABLE_SCHEMA=DATABASE() AND (TABLE_TYPE <> 'BASE TABLE' OR ENGINE <> 'InnoDB')) +
  (SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()) +
  (SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE()) +
  (SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE());"""
MARIA_NONEMPTY = """SELECT
  (SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()) +
  (SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE()) +
  (SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE());"""
PG_NONEMPTY = """SELECT (
    EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('public', 'information_schema') AND nspname !~ '^pg_')
 OR EXISTS (SELECT 1 FROM pg_class WHERE relnamespace = 'public'::regnamespace)
 OR EXISTS (SELECT 1 FROM pg_proc WHERE pronamespace = 'public'::regnamespace)
 OR EXISTS (SELECT 1 FROM pg_type WHERE typnamespace = 'public'::regnamespace)
 OR EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')
)::int;"""


def login_password(prompt, from_stdin=False):
    if from_stdin:
        value = sys.stdin.readline(98).removesuffix('\n')
    else:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                value = getpass.getpass(prompt)
            except getpass.GetPassWarning as error:
                raise ValueError('A terminal is required or use --password-stdin.') from error
            except EOFError as error:
                raise ValueError('Supply the current database password.') from error
    if not value:
        raise ValueError('Supply the current database password.')
    return databases.new_password(value)


def managed_database(inventory, account, label, *, active_only=False):
    name(account)
    databases.label(label)
    meta = inventory.get(account, {})
    states = ('active',) if active_only else ('active', 'suspended')
    entry = meta.get('databases', {}).get(label)
    if meta.get('state') not in states or not entry or entry.get('engine') not in DB_SUFFIX:
        raise ValueError(f'{account}/{label} is outside the eligible managed databases.')
    return {
        'account': account, 'label': label, 'engine': entry['engine'],
        'database': databases.identifier(account, label),
    }


def load_registrations(state):
    path = state / REGISTRATION
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {}
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('Database backup credentials must be stored in a private administrator file.')
    entries = json.loads(path.read_text())
    if not isinstance(entries, dict):
        raise ValueError('Invalid database backup enrollment inventory.')
    return entries


def save_registrations(state, entries):
    with tempfile.NamedTemporaryFile(dir=state, mode='w', prefix='.database-logins-', delete=False) as f:
        temporary = Path(f.name)
        try:
            json.dump(entries, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            temporary.replace(state / REGISTRATION)
        finally:
            temporary.unlink(missing_ok=True)


def tenant_options(db, credentials):
    tenant = pwd.getpwnam('ap_' + db['account'])
    if not tenant.pw_uid or not tenant.pw_gid:
        raise ValueError('Database transfer requires an unprivileged hosting identity.')
    return {
        'user': tenant.pw_uid, 'group': tenant.pw_gid, 'extra_groups': [],
        'env': {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/nonexistent', **credentials},
        'cwd': '/', 'umask': 0o077, 'stderr': subprocess.DEVNULL,
    }


def probe(db, options, process, query):
    if db['engine'] == 'mariadb':
        command = [sqltransfer.MARIADB, *options, '--batch', '--skip-column-names', '--binary-mode',
                   '--local-infile=0', '--execute', query, db['database']]
    else:
        command = [sqltransfer.PSQL, *options, '--no-psqlrc', '--tuples-only', '--no-align',
                   '--set=ON_ERROR_STOP=1', '--command', query]
    try:
        output = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
                                check=True, timeout=25, **process)
        return int(output.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError(f'Database check failed for {db["account"]}/{db["label"]}. Verify service and credentials.') from None


def authenticate(db, password):
    options, env = sqltransfer.connection_options(db['engine'], db['database'], password)
    return options, tenant_options(db, env)


def enroll(state, db, password):
    options, process = authenticate(db, password)
    probe(db, options, process, 'SELECT 1;')
    entries = load_registrations(state)
    entries[f'{db["account"]}/{db["label"]}'] = {**db, 'password': password}
    save_registrations(state, entries)


def exclude(state, account, label):
    key = f'{name(account)}/{databases.label(label)}'
    entries = load_registrations(state)
    if key not in entries:
        raise ValueError('That database is not enrolled for off-site backups.')
    del entries[key]
    save_registrations(state, entries)


def plan(state, inventory):
    selected = []
    for key, saved in sorted(load_registrations(state).items()):
        if not isinstance(saved, dict):
            raise ValueError('Invalid database backup enrollment.')
        db = managed_database(inventory, saved.get('account'), saved.get('label'))
        if key != f'{db["account"]}/{db["label"]}' or any(db[field] != saved.get(field) for field in db):
            raise ValueError(f'Database enrollment changed for {key}. Enroll the current managed database.')
        password = saved.get('password')
        if not password:
            raise ValueError(f'A database password is missing for {key}.')
        selected.append((db, databases.new_password(password)))
    return selected


def archive_path(db):
    return Path('databases') / db['account'] / (db['label'] + DB_SUFFIX[db['engine']])


def file_digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def dump(db, password, path):
    engine, dbname = db['engine'], db['database']
    options, process = authenticate(db, password)
    exporter, _, _ = sqltransfer.transfer_commands(engine, dbname, options)
    if engine == 'mariadb':
        if probe(db, options, process, MARIA_UNSUPPORTED):
            raise ValueError(f'{db["account"]}/{db["label"]} contains objects outside the InnoDB table backup scope.')
        exporter[-1:-1] = ['--skip-lock-tables', '--skip-add-locks', '--skip-add-drop-table',
                           '--skip-triggers', '--hex-blob', '--skip-dump-date']
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with path.open('xb') as output:
            size = stream(exporter, output, limit=DB_LIMIT, timeout=300, failure='Database dump failed.',
                          **process)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise ValueError(f'Could not back up {db["account"]}/{db["label"]}. {error}') from None
    if engine == 'mariadb' and probe(db, options, process, MARIA_UNSUPPORTED):
        raise ValueError('The database acquired objects outside the InnoDB table backup scope during capture.')
    return {'account': db['account'], 'label': db['label'], 'engine': engine,
            'size': size, 'sha256': file_digest(path)}


def import_dump(db, password, archive):
    engine, dbname = db['engine'], db['database']
    options, process = authenticate(db, password)
    empty_check = MARIA_NONEMPTY if engine == 'mariadb' else PG_NONEMPTY
    if probe(db, options, process, empty_check):
        raise ValueError('Choose a new, empty destination database.')
    _, importer, _ = sqltransfer.transfer_commands(engine, dbname, options)
    try:
        with archive.open('rb') as source:
            subprocess.run(importer, stdin=source, stdout=subprocess.DEVNULL,
                           check=True, timeout=300, **process)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Database import failed. The staged dump is available. Check and replace the destination before retrying.') from None
