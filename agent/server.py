# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Serialized root broker. Only a dedicated local UID can call fixed operations.
Registry and generated service configs are root-owned. Never executes a shell.
"""
import fcntl
import grp
import json
import logging
import os
from pathlib import Path
import pwd
import socket
import socketserver
import struct
import subprocess
import tempfile
import sys
from backend.core import name,domain,Problem
from agent import databases, dns, metrics, php_settings, site_security, sites

BASE=Path('/srv/almapanel/accounts')
REGISTRY=Path('/var/lib/almapanel-agent/registry.json')
ROOT=Path(__file__).resolve().parents[1]
PHP_UNIT = os.environ.get('ALMA_PHP_UNIT', 'php8.3-fpm')
PHP_BIN = os.environ.get('ALMA_PHP_BIN', '/usr/sbin/php-fpm8.3')
PHP_POOL = Path(os.environ.get('ALMA_PHP_POOL', '/etc/php/8.3/fpm/pool.d'))
PHP_RUN = os.environ.get('ALMA_PHP_RUN', '/run/php')
WEB_USER = os.environ.get('ALMA_WEB_USER', 'www-data')
SERVICES = {'nginx', PHP_UNIT}

def run(argv, *, timeout=120, **kw):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=timeout,
                          env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'},**kw).stdout

def atomic(path,content,mode=0o600):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.alma-')
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'w') as f: f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def registry():
    return json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}

def save(data): atomic(REGISTRY,json.dumps(data,indent=2))

def vhost(account,host,suspended=False):
    return sites.render(BASE, PHP_RUN, account, host, {}, suspended)

def php_pool(account, settings=None):
    name(account)
    values = php_settings.settings(settings) if settings else php_settings.DEFAULTS
    return f"""[alma-{account}]
user = ap_{account}
group = ap_{account}
listen = {PHP_RUN}/alma-{account}.sock
listen.owner = {WEB_USER}
listen.group = {WEB_USER}
listen.mode = 0600
pm = ondemand
pm.max_children = 2
pm.process_idle_timeout = 10s
pm.max_requests = 300
clear_env = yes
chdir = {BASE}/{account}/public_html
php_admin_value[memory_limit] = {values['memory_mib']}M
php_admin_value[upload_max_filesize] = {values['upload_mib']}M
php_admin_value[post_max_size] = {values['upload_mib'] + 1}M
php_admin_value[max_execution_time] = {values['execution_seconds']}
request_terminate_timeout = {values['execution_seconds'] + 5}s
php_admin_flag[display_errors] = {'on' if values['show_errors'] else 'off'}
php_admin_value[session.save_path] = {BASE}/{account}/runtime
php_admin_value[upload_tmp_dir] = {BASE}/{account}/runtime
php_admin_value[open_basedir] = {BASE}/{account}:/usr/share/php
php_admin_flag[log_errors] = on
php_admin_value[error_log] = {BASE}/{account}/runtime/php-error.log
security.limit_extensions = .php
"""

def configs(changes,service,validator):
    originals={p:p.read_text() if p.exists() else None for p in changes}
    try:
        for p,content in changes.items():
            if content is None:
                p.unlink(missing_ok=True)
            else:
                atomic(p,content,0o644)
        run(validator)
        run(['/usr/bin/systemctl','reload',service])
    except BaseException:
        for p,content in originals.items():
            if content is None: p.unlink(missing_ok=True)
            else: atomic(p,content,0o644)
        try: run(validator);run(['/usr/bin/systemctl','reload',service])
        except Exception: logging.exception('Configuration rollback reload failed')
        raise

def account_create(account):
    name(account)
    data=registry()
    if account in data:
        if data[account]['state']=='active': return {'message':'Account already provisioned.'}
        raise ValueError('Account requires administrator recovery; inspect root registry.')
    username='ap_'+account
    try: pwd.getpwnam(username)
    except KeyError: pass
    else: raise ValueError('Linux identity already exists; refusing adoption.')
    home=BASE/account
    if home.exists() or home.is_symlink(): raise ValueError('Home already exists; refusing adoption.')
    data[account]={'state':'provisioning','domains':[]};save(data)
    # Failures deliberately retain customer state; recovery is explicit, never recursive userdel.
    try:
        run(['/usr/sbin/useradd','--user-group','--no-create-home','--home-dir',str(home),'--shell','/usr/sbin/nologin',username])
        p=pwd.getpwnam(username)
        home.mkdir(mode=0o750);os.chown(home,0,p.pw_gid)
        for child in ('public_html','runtime'):
            path=home/child;path.mkdir(mode=0o750);os.chown(path,p.pw_uid,p.pw_gid)
        # Grant only the web-server read/traverse ACL; other tenants have no access.
        run(['/usr/bin/setfacl','-m',f'u:{WEB_USER}:--x',str(home)])
        run(['/usr/bin/setfacl','-m',f'u:{WEB_USER}:r-x,d:u:{WEB_USER}:r-x',str(home/'public_html')])
        configs({PHP_POOL / f'alma-{account}.conf':php_pool(account)},PHP_UNIT,[PHP_BIN,'-t'])
        data[account]['state']='active';save(data)
        return {'message':'Linux account and PHP-FPM pool provisioned.'}
    except Exception:
        data[account]['state']='failed';save(data);raise

def files_argv(account, home, request):
    argv = [sys.executable, '-I', str(ROOT / 'agent/files.py'), str(home)]
    if request.get('action') in {
        'backup_create', 'backup_scheduled', 'backups', 'backup_read', 'backup_restore', 'backup_delete',
        'trash', 'trash_list', 'trash_restore', 'trash_purge', 'sql_import', 'sql_export', 'sql_download', 'sql_delete',
    }:
        private = BASE / account / 'panel-files'
        tenant = pwd.getpwnam('ap_' + account)
        # Only root can create or replace a direct child of the account home.
        try:
            private.mkdir(mode=0o700)
        except FileExistsError:
            if private.is_symlink() or not private.is_dir() or private.stat().st_uid != tenant.pw_uid:
                raise ValueError('Invalid account storage. Ask the server administrator to inspect it.')
        else:
            os.chown(private, tenant.pw_uid, tenant.pw_gid)
        argv.append(str(private))
    return argv


def tenant_files(account, tenant, home, request):
    child = subprocess.run(
        files_argv(account, home, request), input=json.dumps(request), capture_output=True,
        text=True, timeout=90, user=tenant.pw_uid, group=tenant.pw_gid, extra_groups=[],
        umask=0o027, cwd=home, env={'PATH': '/usr/bin:/bin', 'HOME': str(home.parent), 'LANG': 'C.UTF-8'},
    )
    result = json.loads(child.stdout)
    if not result['ok']:
        raise ValueError(result['error'])
    return result['data']


def site_configs(account, meta, suspended=False):
    metrics.LOG_DIR.mkdir(exist_ok=True, mode=0o750)
    return {sites.site_path(host): sites.render(BASE, PHP_RUN, account, host, meta, suspended)
            for host in meta['domains']}


def apply_sites(account, data, before):
    changes = site_configs(account, data[account])
    for removed in set(before['domains']) - set(data[account]['domains']):
        changes[sites.site_path(removed)] = None
    configs(changes, 'nginx', ['/usr/sbin/nginx', '-t'])
    try:
        save(data)
    except OSError:
        restore = site_configs(account, before)
        for added in set(data[account]['domains']) - set(before['domains']):
            restore[sites.site_path(added)] = None
        configs(restore, 'nginx', ['/usr/sbin/nginx', '-t'])
        raise


def validate_site_root(account, settings):
    if settings['kind'] != 'site' or not settings['root']:
        return
    tenant = pwd.getpwnam('ap_' + account)
    home = BASE / account / 'public_html'
    tenant_files(account, tenant, home, {'action': 'folder_check', 'path': settings['root']})


def manage_site(operation, account, data, args):
    from copy import deepcopy

    meta = data[account]
    if operation == 'domain.list':
        return {'primary': sites.primary(meta), 'acme_available': sites.CERTBOT.is_file(),
                'sites': [{'name': host, **sites.site_for(meta, host),
                           'certificate': sites.certificate_status(host, meta, run)}
                          for host in meta['domains']]}
    host = domain(args.get('domain'))
    before = deepcopy(meta)
    site = meta.setdefault('sites', {}).setdefault(host, {})
    if operation == 'domain.create':
        if host in meta['domains']:
            return {'message': 'Domain already configured.'}
        if (sites.LE_DIR / host / 'fullchain.pem').exists():
            raise ValueError('A previous certificate for this name remains. Ask the server administrator to clear the old lineage.')
        if any(host in other['domains'] for other in data.values()):
            raise ValueError('Domain belongs to another account.')
        path = sites.site_path(host)
        if path.exists() or path.is_symlink():
            raise ValueError('Unmanaged configuration exists; manual recovery required.')
        meta['sites'][host] = sites.settings(meta, host, args)
        validate_site_root(account, meta['sites'][host])
        meta['domains'].append(host)
    else:
        if host not in meta['domains']:
            if operation == 'domain.remove' and args.get('missing_ok') is True:
                return {'message': 'Unprovisioned domain reservation released.'}
            raise ValueError('Domain does not belong to this account.')
        if operation == 'domain.edit':
            meta['sites'][host] = sites.settings(meta, host, args)
            validate_site_root(account, meta['sites'][host])
        elif operation == 'domain.primary':
            if site.get('kind', 'site') != 'site':
                raise ValueError('Choose a website as the primary domain.')
            meta['primary'] = host
        elif operation == 'domain.remove':
            if any(sites.site_for(meta, other).get('kind') == 'alias' and
                   sites.site_for(meta, other).get('target') == host for other in meta['domains']):
                raise ValueError('Remove the aliases for this website first.')
            if host in meta.get('zones', {}):
                raise ValueError('Remove its managed DNS zone before removing the domain.')
            meta['domains'].remove(host)
            del meta['sites'][host]
        elif operation == 'tls.issue':
            if not sites.CERTBOT.is_file():
                raise ValueError('Install Certbot through the server administration guide first.')
            challenge_dir = sites.ACME_ROOT / host / '.well-known' / 'acme-challenge'
            challenge_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            for path in (sites.ACME_ROOT, sites.ACME_ROOT / host, challenge_dir.parent, challenge_dir):
                path.chmod(0o755)
            run(sites.acme_argv(host, args.get('email')), timeout=105)
            site['tls'] = 'acme'
        elif operation == 'tls.upload':
            return install_site_certificate(account, host, data, before, args)
        elif operation == 'tls.redirect':
            if not site.get('tls') or type(args.get('enabled')) is not bool:
                raise ValueError('Install a site certificate before enabling an HTTPS redirect.')
            site['force_https'] = args['enabled']
        else:
            raise ValueError('Domain operation not allowed.')
    meta['primary'] = sites.primary(meta)
    apply_sites(account, data, before)
    if operation == 'domain.remove':
        for rule in site.get('privacy', {}).values():
            (site_security.AUTH_ROOT / host / (rule['id'] + '.passwd')).unlink(missing_ok=True)
    return {'message': 'Website configuration applied.'}


def install_site_certificate(account, host, data, before, args):
    certificate, key = args.get('certificate'), args.get('key')
    sites.validate_certificate(host, certificate, key, run)
    path = sites.TLS_DIR / host
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    files = {path / 'chain.pem': certificate, path / 'key.pem': key}
    previous = {file: file.read_text() if file.exists() else None for file in files}
    try:
        for file, contents in files.items():
            atomic(file, contents)
        data[account]['sites'][host]['tls'] = 'custom'
        apply_sites(account, data, before)
    except Exception:
        for file, contents in previous.items():
            if contents is None:
                file.unlink(missing_ok=True)
            else:
                atomic(file, contents)
        try:
            configs(site_configs(account, before), 'nginx', ['/usr/sbin/nginx', '-t'])
        except Exception:
            logging.exception('Site TLS rollback reload failed')
        raise
    return {'message': 'Site certificate installed.'}


def protect_site(operation, account, data, args):
    from copy import deepcopy
    from hashlib import sha256

    host = domain(args.get('domain'))
    meta = data[account]
    if host not in meta['domains']:
        raise ValueError('Domain does not belong to this account.')
    site = meta.setdefault('sites', {}).setdefault(host, {})
    if site.get('kind', 'site') != 'site':
        raise ValueError('Choose a website instead of an alias or redirect.')
    if operation == 'site_security.get':
        return {'blocked': site.get('blocked', []), 'tls': bool(site.get('tls')),
                'privacy': [{**entry, 'path': path} for path, entry in sorted(site.get('privacy', {}).items())]}
    before = deepcopy(meta)
    if operation == 'site_security.blocklist':
        site['blocked'] = site_security.networks(args.get('addresses'))
        apply_sites(account, data, before)
        return {'message': 'Website IP blocklist saved.'}
    path = site_security.rules_path(args.get('path'))
    rules = site.setdefault('privacy', {})
    if operation == 'site_security.remove':
        if path not in rules:
            raise ValueError('Directory privacy rule not found.')
        old = rules.pop(path)
        apply_sites(account, data, before)
        (site_security.AUTH_ROOT / host / (old['id'] + '.passwd')).unlink(missing_ok=True)
        return {'message': 'Directory privacy rule removed.'}
    if operation != 'site_security.set':
        raise ValueError('Website security operation not allowed.')
    if not site.get('tls'):
        raise ValueError('Install a site certificate before adding directory privacy.')
    if any(sites.site_for(meta, alias).get('target') == host and
           sites.site_for(meta, alias).get('kind') == 'alias' for alias in meta['domains']):
        raise ValueError('Remove aliases pointing to this website before adding directory privacy.')
    # Alternative roots in this account can expose the same content at another
    # hostname. Full-site authentication is the supported isolated arrangement.
    root = site.get('root', '')
    for other in data[account]['domains']:
        if other == host:
            continue
        peer = sites.site_for(meta, other)
        if peer.get('kind', 'site') != 'site':
            continue
        other_root = peer.get('root', '')
        if sites.overlaps(root, other_root):
            raise ValueError('Directory privacy requires a document root that does not overlap another website.')
    if path not in rules and len(rules) >= site_security.MAX_RULES:
        raise ValueError('This website can have up to 10 directory privacy rules.')
    record = site_security.password_line(args.get('username'), args.get('password'), run)
    scope = site_security.AUTH_ROOT / host
    scope.mkdir(parents=True, exist_ok=True, mode=0o750)
    web_gid = grp.getgrnam(WEB_USER).gr_gid
    for folder in (scope, site_security.AUTH_ROOT):
        os.chown(folder, 0, web_gid)
        folder.chmod(0o750)
    hash_id = sha256((host + path).encode()).hexdigest()[:24]
    credential = scope / (hash_id + '.passwd')
    prior = credential.read_text() if credential.is_file() else None
    try:
        atomic(credential, record, 0o640)
        os.chown(credential, 0, web_gid)
        rules[path] = {'id': hash_id, 'username': args['username']}
        apply_sites(account, data, before)
    except Exception:
        if prior is None:
            credential.unlink(missing_ok=True)
        else:
            atomic(credential, prior, 0o640)
            os.chown(credential, 0, web_gid)
        raise
    return {'message': 'Directory password protection saved.'}


def install_wordpress(account, data, args):
    from copy import deepcopy
    from agent.wordpress import VERSION
    import re

    host = domain(args.get('domain'))
    meta = data[account]
    setting = sites.site_for(meta, host)
    if host not in meta['domains'] or setting.get('kind', 'site') != 'site':
        raise ValueError('Select a website you own.')
    if setting.get('privacy'):
        raise ValueError('Remove directory privacy rules before switching this document root.')
    if not setting.get('tls'):
        raise ValueError('Install a valid TLS certificate before configuring WordPress.')
    root = sites.docroot(args.get('destination'))
    if not root:
        raise ValueError('Choose a new folder within public_html.')
    sites.settings(meta, host, {'kind': 'site', 'root': root})
    slug = databases.label(args.get('label'))
    item = meta.get('databases', {}).get(slug)
    if not item or item['engine'] != 'mariadb':
        raise ValueError('Select a MariaDB database owned by this account.')
    db = databases.identifier(account, slug)
    if databases.mariadb(run, f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{db}';").strip() != '0':
        raise ValueError('WordPress needs an empty, dedicated database.')
    password = args.get('db_password')
    if not password:
        raise ValueError('Supply the current database password.')
    password = databases.new_password(password)
    title = args.get('title')
    username = args.get('username')
    email = args.get('email')
    secret = args.get('password')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError('Enter a site title of 1–120 characters.')
    if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_.@-]{3,40}', username):
        raise ValueError('Enter a WordPress administrator username of 3–40 characters.')
    if (not isinstance(email, str) or len(email) > 254 or
            not re.fullmatch(r'[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', email)):
        raise ValueError('Enter a valid WordPress administrator email address.')
    if not isinstance(secret, str) or not 16 <= len(secret) <= 128:
        raise ValueError('Use 16–128 characters for the WordPress password.')
    tenant = pwd.getpwnam('ap_' + account)
    home = BASE / account / 'public_html'
    tenant_files(account, tenant, home, {
        'action': 'wordpress_install', 'destination': root,
        'database': db, 'db_password': password, 'url': 'https://' + host,
        'admin': {'title': title, 'username': username, 'email': email, 'password': secret},
    })
    before = deepcopy(meta)
    meta.setdefault('sites', {})[host] = {**setting, 'root': root, 'force_https': True,
                                        'application': {'type': 'wordpress', 'version': VERSION}}
    try:
        apply_sites(account, data, before)
    except Exception:
        raise ValueError('WordPress files and database were created. The domain could not be switched. Review the Nginx log and set the root manually.') from None
    return {'message': f'WordPress {VERSION} installed.', 'url': 'https://' + host + '/wp-admin/'}


def dispatch(operation,args):
    if operation == 'dns.verify':
        return dns.verify_txt(args.get('domain'), args.get('token'), run)
    if operation == 'update.trigger':
        if not Path('/etc/almapanel/update-public.pem').is_file():
            raise ValueError('Enroll a release verification key on the server first.')
        run(['/usr/bin/systemctl', '--no-block', 'start', 'almapanel-update.service'])
        return {'message': 'Update check requested. Refresh status shortly.'}
    if operation=='system.stats':
        import shutil
        mem={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
        disk=shutil.disk_usage(BASE)
        states={}
        for service in sorted(SERVICES):
            try: states[service]=run(['/usr/bin/systemctl','is-active',service]).strip()
            except subprocess.CalledProcessError: states[service]='inactive or failed'
        return {'load_average':os.getloadavg(),'memory_total':mem['MemTotal'],'memory_available':mem['MemAvailable'],
                'disk_total':disk.total,'disk_used':disk.used,'services':states,'hostname':socket.gethostname()}
    if operation=='service.restart':
        if args.get('service') not in SERVICES: raise ValueError('Service not allowed.')
        service=args['service']
        run(['/usr/sbin/nginx','-t'] if service=='nginx' else [PHP_BIN,'-t'])
        run(['/usr/bin/systemctl','restart',service]);return {'message':'Service restarted.'}
    account=name(args.get('name'))
    if operation=='account.create': return account_create(account)
    data=registry()
    if account not in data or data[account]['state'] not in ('active','suspended'):
        raise ValueError('Account not provisioned.')
    if operation=='account.state':
        state=args.get('state')
        if state not in ('active','suspended'): raise ValueError('Invalid state.')
        changes = site_configs(account, data[account], suspended=state == 'suspended')
        configs(changes,'nginx',['/usr/sbin/nginx','-t'])
        data[account]['state']=state;save(data)
        return {'message':'Web access state changed. Existing PHP requests may finish.'}
    if data[account]['state']!='active': raise ValueError('Account suspended.')
    if operation in ('php.get', 'php.settings', 'php.log'):
        meta = data[account]
        if operation == 'php.get':
            return {'settings': meta.get('php', php_settings.DEFAULTS), 'version': '8.3'}
        if operation == 'php.log':
            tenant = pwd.getpwnam('ap_' + account)
            return php_settings.error_tail(BASE / account, tenant.pw_uid)
        values = php_settings.settings(args.get('settings'))
        original = meta.get('php')
        pool = PHP_POOL / f'alma-{account}.conf'
        configs({pool: php_pool(account, values)}, PHP_UNIT, [PHP_BIN, '-t'])
        meta['php'] = values
        try:
            apply_sites(account, data, {**meta, 'php': original})
        except Exception:
            configs({pool: php_pool(account, original)}, PHP_UNIT, [PHP_BIN, '-t'])
            raise
        return {'message': 'PHP settings applied.'}
    if operation.startswith('site_security.'):
        return protect_site(operation, account, data, args)
    if operation == 'metrics.web':
        host = domain(args.get('domain'))
        if host not in data[account]['domains']:
            raise ValueError('Domain does not belong to this account.')
        return metrics.web_requests(account, host)
    if operation.startswith('dns.'):
        return dns.replace(operation, account, data, args, run, configs, lambda: save(data))
    if operation == 'wordpress.install':
        return install_wordpress(account, data, args)
    if operation in ('database.export', 'database.import', 'database.download', 'database.export_delete'):
        tenant = pwd.getpwnam('ap_' + account)
        home = BASE / account / 'public_html'
        if operation in ('database.download', 'database.export_delete'):
            return tenant_files(account, tenant, home, {
                'action': 'sql_download' if operation == 'database.download' else 'sql_delete',
                'path': args.get('file'), 'offset': args.get('offset'), 'revision': args.get('revision'),
            })
        slug = databases.label(args.get('label'))
        item = data[account].get('databases', {}).get(slug)
        if not item:
            raise ValueError('Database does not belong to this account.')
        password = args.get('password')
        if not password:
            raise ValueError('Supply the current database password.')
        password = databases.new_password(password)
        if operation == 'database.import' and args.get('confirm') != slug:
            raise ValueError('Confirm which database should receive the import.')
        return tenant_files(account, tenant, home, {
            'action': 'sql_export' if operation == 'database.export' else 'sql_import',
            'engine': item['engine'], 'database': databases.identifier(account, slug),
            'password': password, 'content': args.get('content', ''),
        })
    if operation.startswith('database.'):
        return databases.manage(operation, account, data[account], args, run, lambda: save(data))
    if operation.startswith('domain.') or operation.startswith('tls.'):
        return manage_site(operation, account, data, args)
    p = pwd.getpwnam('ap_' + account)
    home = BASE / account / 'public_html'
    if operation in ('cron.validate', 'cron.run'):
        return tenant_files(account, p, home, {
            'action': 'cron_validate' if operation == 'cron.validate' else 'cron_execute',
            'path': args.get('path'),
        })
    if operation == 'backup.scheduled':
        return tenant_files(account, p, home, {'action': 'backup_scheduled', 'retain': args.get('retain')})
    if operation == 'git.release':
        request = {key: args.get(key) for key in ('repository', 'branch', 'destination')}
        request['action'] = 'git_release'
        return tenant_files(account, p, home, request)
    if operation == 'files':
        return tenant_files(account, p, home, args.get('request', {}))
    if operation == 'metrics.processes':
        return metrics.processes(p.pw_uid)
    if operation=='account.stats':
        output=run(['/usr/bin/du','-sb',str(BASE/account)],user=p.pw_uid,group=p.pw_gid,extra_groups=[])
        inodes = run(['/usr/bin/du', '--inodes', '-s', str(BASE / account)],
                     user=p.pw_uid, group=p.pw_gid, extra_groups=[])
        details = metrics.processes(p.pw_uid)
        return {'home':str(BASE/account),'disk_bytes':int(output.split()[0]),'domains':len(data[account]['domains']),
                'disk_quota_bytes':None, 'cpu_percent':None, 'memory_bytes':details['process_rss'],
                'bandwidth_bytes':None, 'inodes':int(inodes.split()[0]), 'processes':details['process_count'],
                'primary_domain':sites.primary(data[account]), 'databases':len(data[account].get('databases',{})),
                'quota_note':'Disk/CPU/RAM quotas are not enforced in this alpha.'}
    raise ValueError('Operation not allowlisted.')

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        uid=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
        if uid!=pwd.getpwnam('almapanel').pw_uid: return
        self.request.settimeout(10)
        try:
            raw=self.rfile.readline(1_600_001)
            if len(raw)>1_600_000 or not raw.endswith(b'\n'): raise ValueError('Request too large.')
            obj=json.loads(raw)
            result=dispatch(obj['operation'],obj['args'])
            reply={'ok':True,'data':result}
            logging.info('operation=%s success',obj['operation'])
        except (ValueError,TypeError,KeyError,Problem) as e:
            reply={'ok':False,'error':str(e)}
        except Exception:
            # Client subprocess failures can include SQL or tenant input.
            logging.error('Agent operation failed (%s)', type(e).__name__)
            reply={'ok':False,'error':'System operation failed. Review almapanel-agent journal and registry.'}
        self.wfile.write(json.dumps(reply).encode()+b'\n')

def main():
    if os.geteuid()!=0: raise SystemExit('Agent must run as root.')
    logging.basicConfig(level=logging.INFO)
    REGISTRY.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    lock=open(REGISTRY.parent/'lock','w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    BASE.mkdir(mode=0o711,parents=True,exist_ok=True)
    path=Path('/run/almapanel/agent.sock');path.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(path),Handler) as server:
        os.chown(path,0,grp.getgrnam('almapanel').gr_gid)
        # Dedicated broker group; SO_PEERCRED also validates the caller UID.
        os.chmod(path,0o660)  # nosec B103
        server.serve_forever()

if __name__=='__main__': main()
