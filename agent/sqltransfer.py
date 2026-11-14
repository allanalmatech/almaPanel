# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""SQL backup and import run with the database's tenant login and Linux UID."""
import base64
import os
import resource
import subprocess

if __package__:
    from . import file_tools as files
else:
    import file_tools as files

MARIADB_DUMP = '/usr/bin/mariadb-dump'
PG_DUMP = '/usr/bin/pg_dump'
PG_RESTORE = '/usr/bin/pg_restore'


def execute(argv, env, *, source=None, destination=None):
    child_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/nonexistent', **env}
    try:
        subprocess.run(argv, stdin=source or subprocess.DEVNULL, stdout=destination or subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, env=child_env, check=True, timeout=65)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('SQL transfer failed. Check credentials, format and available disk space.') from None


def transfer(root, private, request):
    engine = request['engine']
    name = request['database']
    password = request['password']
    operation = request['action']
    limit = files.MAX_BYTES
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (min(soft, limit) if soft >= 0 else limit, hard))
    if engine == 'mariadb':
        env = {'MYSQL_PWD': password}
        sql = ['--no-defaults', '--protocol=socket', '--user=' + name, '--default-character-set=utf8mb4']
        exporter = [MARIADB_DUMP, *sql, '--single-transaction', '--quick', '--no-tablespaces', name]
        importer = ['/usr/bin/mariadb', *sql, '--batch', '--binary-mode', '--local-infile=0', name]
        suffix = '.sql'
    elif engine == 'postgresql':
        env = {'PGPASSWORD': password, 'PGCONNECT_TIMEOUT': '8', 'PGSSLMODE': 'prefer'}
        sql = ['--host=127.0.0.1', '--no-password', '--username=' + name, '--dbname=' + name]
        exporter = [PG_DUMP, *sql, '--format=custom', '--no-owner', '--no-acl']
        importer = [PG_RESTORE, *sql, '--no-owner', '--no-acl', '--exit-on-error', '--single-transaction']
        suffix = '.pgdump'
    else:
        raise ValueError('Unknown SQL engine.')
    if operation == 'sql_export':
        with files.folder(private, ['sql']) as storage:
            import secrets
            key = 'sql-' + secrets.token_hex(12) + suffix
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=storage)
            try:
                with os.fdopen(fd, 'wb') as target:
                    execute(exporter, env, destination=target)
                    target.flush()
                    os.fsync(target.fileno())
            except Exception:
                os.unlink(key, dir_fd=storage)
                raise
        return {'message': 'Database export created.', 'file': key}
    if operation == 'sql_import':
        content = base64.b64decode(request.get('content', ''), validate=True)
        if not content or len(content) > 1024 * 1024:
            raise ValueError('Import a nonempty dump up to 1 MiB.')
        import tempfile
        with tempfile.TemporaryFile() as source:
            source.write(content)
            source.seek(0)
            execute(importer, env, source=source)
        return {'message': 'Database import completed.'}
    raise ValueError('Unsupported SQL transfer.')
