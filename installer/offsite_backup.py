# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Root-only encrypted off-site backup and recovery staging."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import databases, dns
from backend.core import Problem, domain, name
from installer import offsite_database, offsite_dns
from installer.backup_stream import stream

CONFIG = Path('/etc/almapanel/offsite-backup')
STATE = Path('/var/lib/almapanel-offsite')
STATUS = Path('/var/lib/almapanel-backup-status')
REGISTRY = Path('/var/lib/almapanel-agent/registry.json')
ACCOUNTS = Path('/srv/almapanel/accounts')
TAG = 'almapanel-websites'
RESTIC = ('/usr/bin/restic', '/usr/local/bin/restic')
ACCOUNT_NAME = re.compile(r'[a-z][a-z0-9]{2,15}\Z')
HOST = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,127}\Z')
SFTP = re.compile(r'sftp://[a-zA-Z0-9_][a-zA-Z0-9_.-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*'
                  r'(?::[0-9]{1,5})?/[a-zA-Z0-9_./-]+\Z')
SNAPSHOT = re.compile(r'[a-f0-9]{64}\Z')
ARCHIVE_LIMIT = 130 * 1024 * 1024
MANIFEST = 'almapanel-websites.json'
MANIFEST_LIMIT = 8 * 1024 * 1024


def protected(path, owner, *, directory=False):
    info = path.lstat()
    matches = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not matches or info.st_uid != owner or info.st_mode & 0o077:
        raise ValueError(f'{path} must be a private, owner-controlled {"directory" if directory else "file"}.')
    return path


def root_file(path, owner=0):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022
            or not os.access(path, os.X_OK)):
        raise ValueError(f'{path} must be an executable controlled by the administrator.')
    return str(path)


def repository(value, owner=0):
    if not isinstance(value, str) or len(value) > 512 or any(char.isspace() for char in value):
        raise ValueError('Enter an absolute local path, HTTPS S3 repository or SFTP URL.')
    if value.startswith('/'):
        path = Path(value).resolve()
        if (not path.is_dir() or path == Path('/') or path.is_relative_to(STATE) or STATE.is_relative_to(path)
                or path.is_relative_to(ACCOUNTS) or path.is_relative_to(Path('/etc/almapanel'))):
            raise ValueError('Choose an existing repository directory outside the backup workspace.')
        protected(path, owner, directory=True)
        return str(path), 'local'
    if value.startswith('s3:https://'):
        url = urlsplit(value.removeprefix('s3:'))
        if (url.hostname and url.path.strip('/') and url.username is None
                and url.password is None and not url.query and not url.fragment):
            return value, 's3'
    if SFTP.fullmatch(value) and all(part not in ('.', '..') for part in urlsplit(value).path.split('/')):
        return value, 'sftp'
    raise ValueError('Use an absolute local path, s3:https://host/bucket/prefix or sftp://user@host/path.')


def restic_settings(config, owner=0):
    info = json.loads(protected(config / 'repository.json', owner).read_text())
    url, scheme = repository(info.get('repository'), owner)
    host = info.get('host')
    if not isinstance(host, str) or not HOST.fullmatch(host):
        raise ValueError('Give the backup set a unique host name in repository.json.')
    password = protected(config / 'password', owner)
    if not password.read_bytes().strip():
        raise ValueError('Set a nonempty repository password.')
    binary = next((Path(candidate) for candidate in RESTIC if Path(candidate).is_file()), None)
    if binary is None:
        raise ValueError('Install restic and put its executable in /usr/bin or /usr/local/bin.')
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(config),
                   'RESTIC_PASSWORD_FILE': str(password), 'RESTIC_REPOSITORY': url}
    command = [root_file(binary, owner), '--no-cache']
    if scheme == 's3':
        s3 = config / 's3.json'
        if not s3.is_file():
            raise ValueError('Set scoped S3 credentials in s3.json for the backup service.')
        credentials = json.loads(protected(s3, owner).read_text())
        if not isinstance(credentials, dict):
            raise ValueError('S3 credentials must be a JSON object.')
        environment['AWS_EC2_METADATA_DISABLED'] = 'true'
        for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
                    'AWS_DEFAULT_REGION', 'AWS_REGION'):
            if key in credentials:
                value = credentials[key]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f'Invalid value for {key} in the S3 credential file.')
                environment[key] = value
        if not all(environment.get(key) for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')):
            raise ValueError('Set both the S3 access key ID and secret key in s3.json.')
    if scheme == 'sftp':
        key = protected(config / 'sftp-key', owner)
        known = protected(config / 'known_hosts', owner)
        command += ['-o', f'sftp.args=-F /dev/null -i {key} -oUserKnownHostsFile={known} '
                          '-oGlobalKnownHostsFile=/dev/null -oBatchMode=yes -oIdentitiesOnly=yes '
                          '-oStrictHostKeyChecking=yes']
    return command, environment, host


def run_restic(settings, *args, capture=False, timeout=3600):
    command, environment, _ = settings
    result = subprocess.run([*command, *args], env=environment, stdin=subprocess.DEVNULL,
                            check=True, timeout=timeout, stdout=subprocess.PIPE if capture else None, text=True)
    return result.stdout


def capture_site(account, target):
    tenant = pwd.getpwnam('ap_' + account)
    site = ACCOUNTS / account / 'public_html'
    with target.open('xb') as output:
        # The already-open output is the only access the child has to root's workspace.
        # File traversal uses the same descriptor APIs and tenant identity as Website Backups.
        subprocess.run([sys.executable, '-I', str(ROOT / 'agent/files.py'), str(site), '--site-snapshot'],
                       user=tenant.pw_uid, group=tenant.pw_gid, extra_groups=[], stdout=output,
                       stdin=subprocess.DEVNULL, cwd='/', env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                       umask=0o077, check=True, timeout=120)


def hosting_snapshot(settings, state, inventory, capture=capture_site, progress=None, *, database_plan=()):
    stage = state / 'upload'
    if stage.exists() or stage.is_symlink():
        protected(stage, os.geteuid(), directory=True)
        shutil.rmtree(stage)
    stage.mkdir(mode=0o700)
    try:
        sites = sorted(account for account, meta in inventory.items()
                       if meta.get('state') in ('active', 'suspended'))
        if not sites:
            raise ValueError('There are no provisioned hosting accounts to back up.')
        if len(sites) > 100:
            raise ValueError('This backup workflow supports up to 100 hosting accounts per server.')
        for count, account in enumerate(sites):
            if progress:
                progress('running', 'Preparing website archives.', completed=count, total=len(sites))
            if not ACCOUNT_NAME.fullmatch(account):
                raise ValueError('The hosting registry contains an invalid account name.')
            if shutil.disk_usage(state).free < 256 * 1024 * 1024:
                raise ValueError('Keep at least 256 MiB free for website backup staging.')
            print(f'Preparing the website archive for {account}.', flush=True)
            capture(account, stage / f'{account}.zip')
        database_total = len(database_plan)
        entries = []
        for count, (db, password) in enumerate(database_plan):
            if progress:
                progress('running', 'Preparing enrolled database dumps.', completed=count, total=database_total)
            if shutil.disk_usage(state).free < 256 * 1024 * 1024:
                raise ValueError('Keep at least 256 MiB free for database backup staging.')
            print(f'Preparing the database dump for {db["account"]}/{db["label"]}.', flush=True)
            entries.append(offsite_database.dump(db, password, stage / offsite_database.archive_path(db)))
        zones = offsite_dns.capture(stage, inventory, sites, progress)
        metadata = {'format': 3, 'host': settings[2], 'scope': 'managed-hosting',
                    'accounts': sites, 'databases': entries, 'zones': zones}
        payload = json.dumps(metadata, indent=2) + '\n'
        if len(payload.encode()) > MANIFEST_LIMIT:
            raise ValueError('The snapshot inventory exceeds its size limit.')
        (stage / MANIFEST).write_text(payload)
        if progress:
            progress('running', 'Uploading the encrypted snapshot.')
        run_restic(settings, 'backup', '--host', settings[2], '--tag', TAG, '--', str(stage))
        return {'websites': len(sites), 'databases': database_total, 'zones': len(zones)}
    finally:
        shutil.rmtree(stage)


def report_snapshot(status, label, *, completed=0, total=0):
    item = {'state': status, 'message': label, 'completed': completed, 'total': total,
            'updated_at': int(time.time())}
    info = STATUS.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Backup status directory must be controlled by root.')
    with tempfile.NamedTemporaryFile(mode='w', dir=STATUS, prefix='.status-', delete=False) as output:
        saved = Path(output.name)
        try:
            json.dump(item, output)
            output.flush()
            os.fchmod(output.fileno(), 0o644)
            saved.replace(STATUS / 'status.json')
        finally:
            saved.unlink(missing_ok=True)


def record_failure():
    if os.environ.get('SERVICE_RESULT') not in (None, 'success'):
        with locked_state():
            report_snapshot('failed', 'Off-site backup failed. Review the backup service journal.')


def snapshots(settings, state):
    output = run_restic(settings, 'snapshots', '--host', settings[2], '--tag', TAG, '--json', capture=True,
                        timeout=180)
    return [item for item in json.loads(output or '[]') if item['paths'] == [str(state / 'upload')]]


def download_member(settings, state, identifier, member, output, limit):
    command, environment, _ = settings
    data_path = str(state / 'upload' / member)
    return stream([*command, 'dump', identifier, data_path], output, limit=limit, timeout=600,
                  failure='Unable to read the requested file from the snapshot.', env=environment)


def require_snapshot(settings, state, identifier):
    if not SNAPSHOT.fullmatch(identifier):
        raise ValueError('Provide the full snapshot ID. List snapshot IDs with the list command.')
    if not any(item['id'] == identifier for item in snapshots(settings, state)):
        raise ValueError('Snapshot is outside this host’s backup set.')


def stage_member(settings, state, identifier, member, limit):
    if shutil.disk_usage(state).free < 256 * 1024 * 1024:
        raise ValueError('Keep at least 256 MiB free for off-site recovery staging.')
    target = Path(tempfile.mkdtemp(prefix='restore-', dir=state))
    try:
        archive = target / member.name
        with archive.open('xb') as output:
            download_member(settings, state, identifier, member, output, limit)
    except BaseException:
        shutil.rmtree(target)
        raise
    return archive


def restore(settings, state, identifier, account):
    name(account)
    require_snapshot(settings, state, identifier)
    return stage_member(settings, state, identifier, Path(f'{account}.zip'), ARCHIVE_LIMIT)


def read_manifest(settings, state, identifier):
    require_snapshot(settings, state, identifier)
    with tempfile.TemporaryFile() as output:
        download_member(settings, state, identifier, Path(MANIFEST), output, MANIFEST_LIMIT)
        output.seek(0)
        manifest = json.load(output)
    if (not isinstance(manifest, dict) or manifest.get('host') != settings[2]
            or type(manifest.get('format')) is not int or manifest['format'] not in (1, 2, 3)):
        raise ValueError('This snapshot has an incompatible backup manifest.')
    return manifest


def manifest_file(entry, limit):
    return (isinstance(entry, dict) and type(entry.get('size')) is int and 1 <= entry['size'] <= limit
            and isinstance(entry.get('sha256'), str) and SNAPSHOT.fullmatch(entry['sha256']) is not None)


def snapshot_databases(settings, state, identifier):
    manifest = read_manifest(settings, state, identifier)
    if manifest['format'] == 1:
        return []
    entries = manifest.get('databases')
    if not isinstance(entries, list) or len(entries) > 100 * databases.MAX_DATABASES:
        raise ValueError('This snapshot has an invalid database manifest.')
    for item in entries:
        if (not manifest_file(item, offsite_database.DB_LIMIT) or not isinstance(item.get('engine'), str)
                or item['engine'] not in offsite_database.DB_SUFFIX):
            raise ValueError('This snapshot has an invalid database manifest entry.')
        name(item.get('account'))
        databases.label(item.get('label'))
    return entries


def snapshot_zones(settings, state, identifier):
    manifest = read_manifest(settings, state, identifier)
    if manifest['format'] < 3:
        return []
    zones = manifest.get('zones')
    if not isinstance(zones, list) or len(zones) > 10_000:
        raise ValueError('This snapshot has an invalid DNS manifest.')
    for item in zones:
        if not manifest_file(item, offsite_dns.LIMIT):
            raise ValueError('This snapshot has an invalid DNS manifest entry.')
        name(item.get('account'))
        domain(item.get('domain'))
        dns.integer(item.get('serial'), 1, 2**32 - 1)
        dns.integer(item.get('records'), 0, dns.LIMIT)
    return zones


def verified_member(settings, state, identifier, entry, member, limit):
    archive = stage_member(settings, state, identifier, member, limit)
    if archive.stat().st_size != entry['size'] or offsite_database.file_digest(archive) != entry['sha256']:
        shutil.rmtree(archive.parent)
        raise ValueError('The downloaded file failed its manifest size or checksum check.')
    return archive


def restore_database(settings, state, identifier, account, label):
    name(account)
    databases.label(label)
    matches = [item for item in snapshot_databases(settings, state, identifier)
               if item.get('account') == account and item.get('label') == label]
    if len(matches) != 1:
        raise ValueError('That database is unavailable in this snapshot.')
    entry = matches[0]
    archive = verified_member(settings, state, identifier, entry, offsite_database.archive_path(entry),
                              offsite_database.DB_LIMIT)
    return archive, entry['engine']


def restore_dns(settings, state, identifier, account, host):
    name(account)
    domain(host)
    matches = [item for item in snapshot_zones(settings, state, identifier)
               if item['account'] == account and item['domain'] == host]
    if len(matches) != 1:
        raise ValueError('That managed DNS zone is unavailable in this snapshot.')
    entry = matches[0]
    archive = verified_member(settings, state, identifier, entry, offsite_dns.zone_path(entry), offsite_dns.LIMIT)
    try:
        offsite_dns.verify_export(archive, entry)
    except (OSError, ValueError, Problem):
        shutil.rmtree(archive.parent)
        raise
    return archive


def retention(settings, state, count, apply=False):
    if not 1 <= count <= 100:
        raise ValueError('Choose 1–100 snapshots to keep.')
    mode = [] if apply else ['--dry-run']
    run_restic(settings, 'forget', '--host', settings[2], '--tag', TAG, '--path', str(state / 'upload'),
               '--keep-last', str(count), *mode)


def import_website(account, archive, inventory):
    if not ACCOUNT_NAME.fullmatch(account) or inventory.get(account, {}).get('state') != 'active':
        raise ValueError('Choose an existing active destination account.')
    sys.path.insert(0, str(ROOT))
    from agent.server import ensure_account_private

    tenant = pwd.getpwnam('ap_' + account)
    home = ACCOUNTS / account
    if home.is_symlink() or not home.is_dir() or home.stat().st_uid != 0:
        raise ValueError('The destination account’s Linux home is unavailable.')
    private = ensure_account_private(home, tenant)
    with archive.open('rb') as source:
        child = subprocess.run([sys.executable, '-I', str(ROOT / 'agent/files.py'), str(private), '--import-backup'],
                               user=tenant.pw_uid, group=tenant.pw_gid, extra_groups=[], stdin=source,
                               cwd='/', env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                               umask=0o077, timeout=120, capture_output=True, text=True)
    if child.returncode:
        raise ValueError(child.stderr.strip() or 'Import failed. The staged website ZIP is available to inspect.')
    return child.stdout.strip()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('init', 'snapshot', 'list', 'record-failure'):
        commands.add_parser(command)
    commands.add_parser('check').add_argument('--read-data', action='store_true')
    recover = commands.add_parser('restore')
    recover.add_argument('snapshot_id')
    recover.add_argument('account')
    recover.add_argument('--import-to', metavar='ACCOUNT')
    enroll = commands.add_parser('database-include', help='Enroll a managed database in scheduled off-site backups.')
    exclude = commands.add_parser('database-exclude', help='Stop including a database in new snapshots.')
    for command in (enroll, exclude):
        command.add_argument('account')
        command.add_argument('label')
    enroll.add_argument('--password-stdin', action='store_true')
    commands.add_parser('database-list', help='Show databases in a snapshot.').add_argument('snapshot_id')
    sql = commands.add_parser('restore-db', help='Stage a dump, optionally importing into a separate empty database.')
    sql.add_argument('snapshot_id')
    sql.add_argument('account')
    sql.add_argument('label')
    sql.add_argument('--import-to', metavar='LABEL')
    sql.add_argument('--password-stdin', action='store_true')
    commands.add_parser('dns-list', help='Show the managed DNS zones in a snapshot.').add_argument('snapshot_id')
    zone = commands.add_parser('restore-dns', help='Stage managed DNS records for import in Zone Editor.')
    zone.add_argument('snapshot_id')
    zone.add_argument('account')
    zone.add_argument('domain')
    policy = commands.add_parser('retention')
    policy.add_argument('--keep-last', type=int, required=True)
    policy.add_argument('--apply', action='store_true')
    return parser.parse_args(argv)


@contextmanager
def locked_state():
    STATE.mkdir(mode=0o700, exist_ok=True)
    protected(STATE, 0, directory=True)
    with (STATE / 'lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Another almaPanel backup operation is running.') from error
        yield STATE


def main(args):
    if os.geteuid() != 0:
        raise ValueError('Run this command as the server administrator.')
    os.umask(0o077)
    if args.command == 'record-failure':
        record_failure()
        return
    with locked_state() as state:
        if args.command == 'snapshot':
            report_snapshot('running', 'Starting off-site backup.')
        try:
            perform(args, state)
        except (OSError, ValueError, KeyError, Problem, subprocess.SubprocessError):
            if args.command == 'snapshot':
                report_snapshot('failed', 'Off-site backup failed. Review the backup service journal.')
            raise


def perform(args, state):
    if args.command in ('snapshot', 'restore', 'restore-db', 'database-include'):
        inventory = json.loads(REGISTRY.read_text()) if REGISTRY.is_file() else {}
    if args.command == 'database-include':
        database = offsite_database.managed_database(inventory, args.account, args.label)
        password = offsite_database.login_password('Current database password: ', args.password_stdin)
        offsite_database.enroll(state, database, password)
        print(f'{args.account}/{args.label} will be included in new off-site backups.')
        return
    if args.command == 'database-exclude':
        offsite_database.exclude(state, args.account, args.label)
        print(f'{args.account}/{args.label} was removed from new off-site backups.')
        return
    protected(CONFIG, 0, directory=True)
    settings = restic_settings(CONFIG)
    if args.command == 'snapshot':
        selected = offsite_database.plan(state, inventory)
        counts = hosting_snapshot(settings, state, inventory, progress=report_snapshot, database_plan=selected)
        message = (f'Encrypted snapshot saved with {counts["websites"]} websites, '
                   f'{counts["databases"]} databases and {counts["zones"]} DNS zones.')
        report_snapshot('succeeded', message)
    elif args.command == 'init':
        run_restic(settings, 'init')
    elif args.command == 'list':
        print(json.dumps([{'id': item['id'], 'time': item['time']} for item in snapshots(settings, state)], indent=2))
    elif args.command == 'check':
        run_restic(settings, 'check', *(['--read-data'] if args.read_data else []))
    elif args.command == 'restore':
        if args.import_to and inventory.get(args.import_to, {}).get('state') != 'active':
            raise ValueError('Choose an existing active destination account.')
        archive = restore(settings, state, args.snapshot_id, args.account)
        print(f'Restored website ZIP to {archive}', flush=True)
        if args.import_to:
            imported = import_website(args.import_to, archive, inventory)
            print(f'Imported {imported} into Website Backups for {args.import_to}.')
    elif args.command == 'database-list':
        print(json.dumps(snapshot_databases(settings, state, args.snapshot_id), indent=2))
    elif args.command == 'dns-list':
        print(json.dumps(snapshot_zones(settings, state, args.snapshot_id), indent=2))
    elif args.command == 'restore-dns':
        restored = restore_dns(settings, state, args.snapshot_id, args.account, args.domain)
        print(f'Restored DNS records to {restored}')
    elif args.command == 'restore-db':
        destination = None
        if args.import_to:
            if args.import_to == args.label:
                raise ValueError('Use a different database label for recovery.')
            destination = offsite_database.managed_database(inventory, args.account, args.import_to, active_only=True)
        archive, engine = restore_database(settings, state, args.snapshot_id, args.account, args.label)
        print(f'Restored {engine} dump to {archive}', flush=True)
        if destination:
            if destination['engine'] != engine:
                raise ValueError('Create the destination database with the same SQL engine as the backup.')
            password = offsite_database.login_password('Destination database password: ', args.password_stdin)
            offsite_database.import_dump(destination, password, archive)
            print(f'Imported the dump into {args.account}/{args.import_to}.')
    elif args.command == 'retention':
        retention(settings, state, args.keep_last, args.apply)


if __name__ == '__main__':
    try:
        main(parse_args())
    except (OSError, ValueError, KeyError, Problem, subprocess.SubprocessError) as error:
        sys.exit(f'Off-site backup failed. {error}')
