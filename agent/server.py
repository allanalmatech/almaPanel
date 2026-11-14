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
from backend.core import name,domain,Problem

BASE=Path('/srv/almapanel/accounts')
REGISTRY=Path('/var/lib/almapanel-agent/registry.json')
ROOT=Path(__file__).resolve().parents[1]
SERVICES={'nginx','php8.3-fpm'}

def run(argv,**kw):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=120,
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
    name(account);domain(host)
    root=f'{BASE}/{account}/public_html'
    if suspended:
        return f'server {{ listen 80; server_name {host}; return 503; }}\n'
    return fr"""server {{
 listen 80;
 server_name {host};
 root {root};
 index index.php index.html;
 client_max_body_size 8m;
 disable_symlinks on;
 location / {{ try_files $uri $uri/ =404; }}
 location ~ /\. {{ deny all; }}
 location ~ \.php$ {{
  try_files $uri =404;
  include fastcgi_params;
  fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
  fastcgi_pass unix:/run/php/alma-{account}.sock;
 }}
}}
"""

def php_pool(account):
    name(account)
    return f"""[alma-{account}]
user = ap_{account}
group = ap_{account}
listen = /run/php/alma-{account}.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0600
pm = ondemand
pm.max_children = 2
pm.process_idle_timeout = 10s
pm.max_requests = 300
clear_env = yes
chdir = {BASE}/{account}/public_html
php_admin_value[memory_limit] = 96M
php_admin_value[upload_max_filesize] = 8M
php_admin_value[post_max_size] = 8M
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
        for p,content in changes.items(): atomic(p,content,0o644)
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
        run(['/usr/bin/setfacl','-m','u:www-data:--x',str(home)])
        run(['/usr/bin/setfacl','-m','u:www-data:r-x,d:u:www-data:r-x',str(home/'public_html')])
        configs({Path(f'/etc/php/8.3/fpm/pool.d/alma-{account}.conf'):php_pool(account)},'php8.3-fpm',['/usr/sbin/php-fpm8.3','-t'])
        data[account]['state']='active';save(data)
        return {'message':'Linux account and PHP-FPM pool provisioned.'}
    except Exception:
        data[account]['state']='failed';save(data);raise

def dispatch(operation,args):
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
        run(['/usr/sbin/nginx','-t'] if service=='nginx' else ['/usr/sbin/php-fpm8.3','-t'])
        run(['/usr/bin/systemctl','restart',service]);return {'message':'Service restarted.'}
    account=name(args.get('name'))
    if operation=='account.create': return account_create(account)
    data=registry()
    if account not in data or data[account]['state'] not in ('active','suspended'):
        raise ValueError('Account not provisioned.')
    if operation=='account.state':
        state=args.get('state')
        if state not in ('active','suspended'): raise ValueError('Invalid state.')
        changes={Path(f'/etc/nginx/conf.d/alma-{host}.conf'):vhost(account,host,state=='suspended') for host in data[account]['domains']}
        configs(changes,'nginx',['/usr/sbin/nginx','-t'])
        data[account]['state']=state;save(data)
        return {'message':'Web access state changed. Existing PHP requests may finish.'}
    if data[account]['state']!='active': raise ValueError('Account suspended.')
    if operation=='domain.create':
        host=domain(args.get('domain'))
        owners=[a for a,meta in data.items() if host in meta['domains']]
        if owners:
            if owners==[account]: return {'message':'Domain already configured.'}
            raise ValueError('Domain belongs to another account.')
        path=Path(f'/etc/nginx/conf.d/alma-{host}.conf')
        if path.exists(): raise ValueError('Unmanaged configuration exists; manual recovery required.')
        configs({path:vhost(account,host)},'nginx',['/usr/sbin/nginx','-t'])
        data[account]['domains'].append(host);save(data)
        return {'message':'HTTP virtual host created. Configure external DNS; HTTPS is not yet provisioned.'}
    p=pwd.getpwnam('ap_'+account)
    home=BASE/account/'public_html'
    if operation=='files':
        request=args.get('request',{})
        child=subprocess.run(['/usr/bin/python3','-I',str(ROOT/'agent/files.py'),str(home)],
               input=json.dumps(request),capture_output=True,text=True,timeout=30,
               user=p.pw_uid,group=p.pw_gid,extra_groups=[],umask=0o027,cwd=home,
               env={'PATH':'/usr/bin:/bin','HOME':str(BASE/account),'LANG':'C.UTF-8'})
        result=json.loads(child.stdout)
        if not result['ok']: raise ValueError(result['error'])
        return result['data']
    if operation=='account.stats':
        output=run(['/usr/bin/du','-sb',str(BASE/account)],user=p.pw_uid,group=p.pw_gid,extra_groups=[])
        return {'home':str(BASE/account),'disk_bytes':int(output.split()[0]),'domains':len(data[account]['domains']),
                'disk_quota_bytes':None,'cpu_percent':None,'memory_bytes':None,'bandwidth_bytes':None,
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
            logging.exception('Agent operation failed')
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
