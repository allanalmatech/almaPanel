# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import hashlib
import hmac
from http.cookies import SimpleCookie
import json
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import parse_qs
from backend import core as c
from backend import hosting, notifications, schedules, security

MAX_BODY = 1_500_000
DUMMY_HASH = c.password_hash('dummy-password-for-timing-only')

def rows(cursor):
    return [dict(r) for r in cursor.fetchall()]

def privileged(user):
    if user['role'] not in ('admin', 'reseller'):
        raise c.Problem('Administrator or reseller required.', 403)

def admin(user):
    if user['role'] != 'admin':
        raise c.Problem('Administrator required.', 403)

def throttle(db, key, *, limit=10, window=900):
    now = int(time.time())
    db.execute('DELETE FROM attempts WHERE reset<?', (now,))
    row = db.execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
    if row and row['count'] >= limit:
        raise c.Problem('Too many requests. Try again after the rate limit resets.', 429)
    db.execute('INSERT INTO attempts(key,count,reset) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, now+window))
    db.commit()

def api(env, body, db, headers):
    path, method = env['PATH_INFO'], env['REQUEST_METHOD']
    ip = env.get('REMOTE_ADDR', 'unknown')  # Nginx passes verified peer via WSGI proxy configuration.
    if method not in ('GET', 'POST'):
        raise c.Problem('Method not allowed.', 405)
    if path == '/api/health' and method == 'GET':
        db.execute('SELECT 1')
        return {'status': 'ok', 'version': (c.ROOT/'VERSION').read_text().strip()}
    if method == 'POST' and path in ('/api/setup', '/api/login'):
        throttle(db, 'login:' + ip)
        username = c.name(body.get('username'))
        if path == '/api/setup':
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM users').fetchone():
                raise c.Problem('Setup is already complete.', 409)
            token = c.STATE / 'setup-token'
            supplied = body.get('token', '')
            if not isinstance(supplied, str) or not token.exists() or not hmac.compare_digest(token.read_text(), supplied):
                raise c.Problem('Invalid setup token.', 403)
            hashed = c.password_hash(body.get('password'))
            db.execute("INSERT INTO users(username,password,role,created) VALUES(?,?,'admin',?)", (username, hashed, int(time.time())))
            audit_id = db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()[0]
            c.audit(db,audit_id,'setup','admin',ip)
            db.commit()
            token.unlink(missing_ok=True)
            return {'message': 'Administrator created. Sign in.'}
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        valid = c.password_ok(body.get('password'), row['password'] if row else DUMMY_HASH)
        if not valid or not row or not row['enabled']:
            c.audit(db, None, 'login.failed', username, ip)
            db.commit()
            raise c.Problem('Invalid credentials.', 401)
        if not security.login_second_factor(db, row['id'], body.get('code')):
            c.audit(db, row['id'], 'login.mfa_failed', row['id'], ip)
            db.commit()
            raise c.Problem('Enter a fresh authenticator or recovery code.', 401)
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?', (int(time.time()),))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                   (hashlib.sha256(raw.encode()).hexdigest(), row['id'], csrf, int(time.time())+3600))
        db.execute('UPDATE users SET last_ip=? WHERE id=?', (ip,row['id']))
        c.audit(db, row['id'], 'login', row['id'], ip)
        headers.append(('Set-Cookie', 'alma_session='+raw+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=3600'))
        return {'csrf': csrf}
    authorization = env.get('HTTP_AUTHORIZATION')
    if authorization:
        user = security.authenticate_token(db, authorization, path, method)
        session = None
        token_hash = None
    else:
        cookie = SimpleCookie()
        cookie.load(env.get('HTTP_COOKIE', ''))
        raw = cookie['alma_session'].value if 'alma_session' in cookie else ''
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        session = db.execute('SELECT * FROM sessions WHERE token=? AND expires>?',
                             (token_hash, int(time.time()))).fetchone()
        user = db.execute('SELECT * FROM users WHERE id=? AND enabled=1',
                          (session['user_id'],)).fetchone() if session else None
        if not user:
            raise c.Problem('Please sign in.', 401)
        if method == 'POST' and not hmac.compare_digest(env.get('HTTP_X_CSRF_TOKEN', ''), session['csrf']):
            raise c.Problem('Invalid CSRF token.', 403)
    if path == '/api/mfa':
        if method == 'POST':
            throttle(db, 'mfa:' + str(user['id']))
        return security.mfa(db, user, method, body, ip)
    if path == '/api/tokens':
        if method == 'POST' and body.get('action') == 'create':
            throttle(db, 'token:' + str(user['id']))
        return security.tokens(db, user, method, body, ip)
    if path == '/api/profile':
        return security.profile(db, user, method, body, ip)
    if path == '/api/me' and method == 'GET':
        return {'username': user['username'], 'id': user['id'], 'role': user['role'], 'csrf': session['csrf'], 'last_ip': user['last_ip']}
    if path == '/api/logout' and method == 'POST':
        db.execute('DELETE FROM sessions WHERE token=?',(token_hash,))
        headers.append(('Set-Cookie','alma_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'))
        return {'message': 'Signed out.'}
    if path == '/api/password' and method == 'POST':
        db.execute('BEGIN IMMEDIATE')
        current_hash = db.execute('SELECT password FROM users WHERE id=?', (user['id'],)).fetchone()[0]
        if not c.password_ok(body.get('current'), current_hash):
            raise c.Problem('Current password is incorrect.',403)
        db.execute('UPDATE users SET password=? WHERE id=?',(c.password_hash(body.get('password')),user['id']))
        security.toggle_sessions(db, user['id'])
        c.audit(db,user['id'],'password.changed',user['id'],ip)
        return {'message':'Password changed. Sign in again.'}
    if path == '/api/packages':
        if method == 'GET':
            return rows(db.execute('SELECT * FROM packages WHERE owner_id=? OR owner_id IS NULL' if user['role']!='admin' else 'SELECT * FROM packages', (user['id'],) if user['role']!='admin' else ()))
        privileged(user)
        label = body.get('name','')
        limit = body.get('max_domains')
        if not isinstance(label,str) or not 1<=len(label)<=64 or type(limit)!=int or not 1<=limit<=100:
            raise c.Problem('Provide a package name and domain limit between 1 and 100.')
        db.execute('INSERT INTO packages(name,owner_id,max_domains) VALUES(?,?,?)',(label,None if user['role']=='admin' else user['id'],limit))
        c.audit(db,user['id'],'package.created',label,ip)
        return {'message':'Package created. Only domain-count limits are enforced in this release.'}
    if path == '/api/resellers':
        admin(user)
        if method == 'GET':
            return rows(db.execute("SELECT id,username,max_accounts,enabled FROM users WHERE role='reseller'"))
        limit = body.get('max_accounts')
        if type(limit)!=int or not 1<=limit<=100:
            raise c.Problem('Account limit must be 1–100.')
        db.execute("INSERT INTO users(username,password,role,owner_id,created,max_accounts) VALUES(?,?,'reseller',?,?,?)",(c.name(body.get('username')),c.password_hash(body.get('password')),user['id'],int(time.time()),limit))
        c.audit(db,user['id'],'reseller.created',body['username'],ip)
        return {'message':'Reseller created.'}
    if path == '/api/accounts':
        if method == 'GET':
            return rows(db.execute("SELECT a.*,p.name AS package FROM accounts a JOIN packages p ON a.package_id=p.id WHERE ?='admin' OR a.user_id=? OR (?='reseller' AND a.owner_id=?)",(user['role'],user['id'],user['role'],user['id'])))
        privileged(user)
        db.execute('BEGIN IMMEDIATE')
        if user['role']=='reseller' and db.execute('SELECT count(*) FROM accounts WHERE owner_id=?',(user['id'],)).fetchone()[0]>=user['max_accounts']:
            raise c.Problem('Reseller account allocation exhausted.',409)
        package = db.execute('SELECT * FROM packages WHERE id=?',(body.get('package_id'),)).fetchone()
        if not package or (user['role']!='admin' and package['owner_id'] not in (None,user['id'])):
            raise c.Problem('Package not found.',404)
        username = c.name(body.get('username'))
        uid = db.execute("INSERT INTO users(username,password,role,owner_id,enabled,created) VALUES(?,?,'user',?,0,?)",(username,c.password_hash(body.get('password')),user['id'],int(time.time()))).lastrowid
        aid = db.execute("INSERT INTO accounts(user_id,name,owner_id,package_id,state,created) VALUES(?,?,?,?,'provisioning',?)",(uid,username,user['id'],package['id'],int(time.time()))).lastrowid
        return c.enqueue(db,user,aid,'account.create',{'name':username},ip)
    if path == '/api/dns-lookup' and method == 'GET':
        fields = parse_qs(env.get('QUERY_STRING', ''))
        throttle(db, 'dns-lookup:' + str(user['id']), limit=20, window=60)
        return c.rpc('dns.lookup', domain=c.domain(fields.get('domain', [''])[0]),
                     kind=fields.get('type', ['A'])[0])
    if path == '/api/notifications':
        return notifications.inbox(db, user, method, body, ip)
    if path == '/api/jobs' and method == 'GET':
        return rows(db.execute("SELECT id,account_id,operation,state,result,created,finished FROM jobs WHERE ?='admin' OR actor_id=? ORDER BY id DESC LIMIT 100",(user['role'],user['id'])))
    if path == '/api/audit' and method == 'GET':
        admin(user)
        return rows(db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200'))
    if path == '/api/system' and method == 'GET':
        admin(user)
        return c.rpc('system.stats')
    if path == '/api/offsite-backups':
        admin(user)
        if method == 'POST':
            result = c.rpc('backup.offsite.trigger')
            c.audit(db, user['id'], 'backup.offsite.trigger', 'website backups', ip)
            return result
        try:
            return json.loads(Path('/var/lib/almapanel-backup-status/status.json').read_text())
        except (OSError, ValueError):
            return {'state': 'unavailable', 'message': 'Set up the off-site repository or run the first snapshot.'}
    if path == '/api/updates':
        admin(user)
        if method == 'POST':
            result = c.rpc('update.trigger')
            c.audit(db, user['id'], 'update.trigger', 'release channel', ip)
            return result
        try:
            status = json.loads(Path('/var/lib/almapanel-update-status/status.json').read_text())
        except (OSError, ValueError):
            status = {'state': 'unconfigured', 'message': 'See docs/UPDATES.md to configure the signed release channel.'}
        return {**status, 'version': (c.ROOT / 'VERSION').read_text().strip()}
    if path == '/api/services' and method == 'POST':
        admin(user)
        if body.get('confirm') != 'RESTART':
            raise c.Problem('Type RESTART to confirm.')
        return c.enqueue(db,user,None,'service.restart',{'service':body.get('service')},ip)
    parts = path.strip('/').split('/')
    if len(parts)==4 and parts[:2]==['api','accounts'] and parts[2].isdigit():
        account = c.scoped_account(db,user,int(parts[2]))
        action = parts[3]
        if action=='state' and method=='POST':
            privileged(user)
            if account['state'] not in ('active','suspended'):
                raise c.Problem('Account has a pending or failed operation.',409)
            state = body.get('state')
            if state not in ('active','suspended'):
                raise c.Problem('Invalid state.')
            if db.execute("SELECT 1 FROM jobs WHERE account_id=? AND state IN ('queued','running')",(account['id'],)).fetchone():
                raise c.Problem('Wait for existing jobs.',409)
            return c.enqueue(db,user,account['id'],'account.state',{'name':account['name'],'state':state},ip)
        if account['state']!='active':
            raise c.Problem('Account is not active.',409)
        if action == 'domains':
            return hosting.domains(db, user, account, method, body, ip)
        if action == 'cron':
            return schedules.php_jobs(db, user, account, method, body, ip)
        if action == 'backup-schedule':
            return schedules.settings(db, user, account, method, body, ip)
        if action == 'stats' and method == 'GET':
            return c.rpc('account.stats', name=account['name'])
        if action == 'files':
            return hosting.files(db, user, account, method, env, body, ip)
        if action == 'mail':
            return hosting.mail(db, user, account, method, body, ip)
        if action == 'sftp':
            return hosting.sftp(db, user, account, method, body, ip)
        if action == 'site-security':
            return hosting.site_security(db, user, account, method, env, body, ip)
        if action == 'php':
            return hosting.php(db, user, account, method, env, body, ip)
        if action == 'tls':
            return hosting.tls(db, user, account, method, body, ip)
        if action == 'databases':
            return hosting.databases(db, user, account, method, body, ip)
        if action == 'wordpress' and method == 'POST':
            return hosting.wordpress(db, user, account, body, ip)
        if action == 'git' and method == 'POST':
            return hosting.git_release(db, user, account, body, ip)
        if action == 'metrics' and method == 'GET':
            return hosting.metrics(db, account, env)
        if action == 'dns':
            return hosting.dns(db, user, account, method, env, body, ip)
    raise c.Problem('Endpoint not found.',404)

def application(env, start_response):
    headers=[('Content-Type','application/json'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),
             ('Content-Security-Policy',"default-src 'self'; style-src 'self'; img-src 'self' blob:; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
             ('Referrer-Policy','no-referrer')]
    status=200
    try:
        path=env.get('PATH_INFO','/')
        if not path.startswith('/api/'):
            static={'/':'index.html','/app.js':'app.js','/hosting.js':'hosting.js','/style.css':'style.css','/logo.svg':'logo.svg'}
            if path not in static or env['REQUEST_METHOD']!='GET':
                raise c.Problem('Not found.',404)
            file=c.ROOT/'frontend'/static[path]
            types={'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml'}
            headers[0]=('Content-Type',types[file.suffix])
            output=file.read_bytes()
        else:
            length=int(env.get('CONTENT_LENGTH') or 0)
            if length<0 or length>MAX_BODY:
                raise c.Problem('Request too large (1 MB file limit).',413)
            body=json.loads(env['wsgi.input'].read(length)) if length else {}
            if not isinstance(body,dict):
                raise c.Problem('Expected a JSON object.')
            if env['REQUEST_METHOD']=='POST':
                expected=os.environ.get('ALMA_ORIGIN')
                if expected and env.get('HTTP_ORIGIN') != expected:
                    raise c.Problem('Origin rejected.',403)
                if env.get('CONTENT_TYPE','').split(';')[0]!='application/json':
                    raise c.Problem('JSON content type required.',415)
            with c.connect() as db:
                result=api(env,body,db,headers)
            output=json.dumps(result).encode()
    except c.Problem as e:
        status=e.status;output=json.dumps({'error':str(e)}).encode()
    except sqlite3.IntegrityError:
        status=409;output=b'{"error":"Name already exists or invalid reference."}'
    except (ValueError,TypeError,KeyError):
        status=400;output=b'{"error":"Invalid request."}'
    except Exception:
        logging.exception('API failure')
        status=500;output=b'{"error":"Internal error. Inspect service logs."}'
    headers.append(('Content-Length',str(len(output))))
    from http import HTTPStatus
    start_response(f'{status} {HTTPStatus(status).phrase}',headers)
    return [output]

if __name__=='__main__':
    from waitress import serve
    c.initialize()
    serve(application,unix_socket='/run/almapanel-api/http.sock',unix_socket_perms='660',threads=2,max_request_body_size=MAX_BODY,
          trusted_proxy='*',trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'},clear_untrusted_proxy_headers=True)
