# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Session-authorized routes for tenant hosting tools."""
import secrets
import time
from urllib.parse import parse_qs

from backend import core as c

FILE_READS = {'list', 'list_page', 'read', 'search', 'download', 'archive_contents', 'trash_list', 'backups', 'backup_read',
              'backup_contents', 'backup_verify'}
FILE_WRITES = {'write', 'mkdir', 'rename', 'delete', 'copy', 'chmod', 'trash', 'trash_restore',
               'trash_purge', 'archive', 'extract', 'copy_tree',
               'upload_start', 'upload_chunk', 'upload_finish', 'upload_cancel',
               'backup_create', 'backup_restore', 'backup_restore_file', 'backup_delete'}


def allowed(body, names):
    action = body.get('action')
    if not isinstance(action, str) or action not in names:
        raise c.Problem('Choose a supported operation.')
    return action


def files(db, user, account, method, env, body, ip):
    query = parse_qs(env.get('QUERY_STRING', '')) if method == 'GET' else {}
    request = {'action': 'list', 'path': query.get('path', [''])[0]} if method == 'GET' else body
    action = allowed(request, FILE_READS | FILE_WRITES)
    result = c.rpc('files', name=account['name'], request=request)
    if action in FILE_WRITES and action != 'upload_chunk':
        c.audit(db, user['id'], f'files.{action}', account['id'], ip)
    return result


def find_domain(db, account, host):
    if not db.execute("SELECT id FROM domains WHERE name=? AND account_id=? AND state='active'",
                      (host, account['id'])).fetchone():
        raise c.Problem('Active domain not found in this account.', 404)


def domains(db, user, account, method, body, ip):
    if method == 'GET':
        return [dict(row) for row in db.execute(
            """SELECT d.*,COALESCE(p.verified,0) AS dns_verified FROM domains d
               LEFT JOIN domain_proofs p ON p.account_id=d.account_id AND p.host=d.name
               WHERE d.account_id=? ORDER BY d.id""", (account['id'],))]
    action = body.get('action', 'create')
    if action not in ('create', 'edit', 'primary', 'remove', 'challenge', 'verify'):
        raise c.Problem('Choose a supported domain operation.')
    host = c.domain(body.get('domain'))
    if action == 'challenge':
        if db.execute('SELECT 1 FROM domains WHERE name=? AND account_id<>?', (host, account['id'])).fetchone():
            raise c.Problem('This domain is already assigned.', 409)
        # Active, verified websites can keep their proof when the TXT record is removed.
        existing = db.execute('SELECT 1 FROM domains WHERE name=? AND account_id=?', (host, account['id'])).fetchone()
        prior = db.execute('SELECT verified FROM domain_proofs WHERE host=? AND account_id=?', (host, account['id'])).fetchone()
        if existing and prior and prior[0]:
            raise c.Problem('This domain is already verified.', 409)
        return issue_domain_proof(db, account, host)
    if action == 'verify':
        return verify_domain_proof(db, account, host)
    db.execute('BEGIN IMMEDIATE')
    if db.execute("""SELECT 1 FROM jobs WHERE account_id=?
                     AND state IN ('queued', 'running') AND operation IN
                     ('account.state', 'domain.edit', 'domain.primary', 'domain.remove', 'tls.issue')""",
                  (account['id'],)).fetchone():
        raise c.Problem('Wait for the pending account or site operation.', 409)
    if action == 'create':
        require_domain_proof(db, user, account, host, current=True)
        limit = db.execute('SELECT max_domains FROM packages WHERE id=?',
                           (account['package_id'],)).fetchone()[0]
        if db.execute('SELECT count(*) FROM domains WHERE account_id=?', (account['id'],)).fetchone()[0] >= limit:
            raise c.Problem('Package domain limit reached.', 409)
        db.execute("INSERT INTO domains(account_id,name,state,created) VALUES(?,?,'provisioning',?)",
                   (account['id'], host, int(time.time())))
    else:
        entry = db.execute('SELECT state FROM domains WHERE name=? AND account_id=?',
                           (host, account['id'])).fetchone()
        if not entry or entry['state'] not in ('active', 'failed'):
            raise c.Problem('Domain not found or still provisioning.', 404)
        if action == 'remove' and body.get('confirm') != host:
            raise c.Problem('Type the domain name to confirm removal.')
        if action == 'remove' and entry['state'] == 'failed':
            # The agent still checks its own inventory in case provisioning completed
            # before the worker could record the result.
            payload = {'name': account['name'], 'domain': host, 'missing_ok': True}
            return c.enqueue(db, user, account['id'], 'domain.remove', payload, ip)
    payload = {'name': account['name'], 'domain': host}
    if action in ('create', 'edit'):
        payload.update(kind=body.get('kind', 'site'), root=body.get('root', ''), target=body.get('target', ''))
    return c.enqueue(db, user, account['id'], f'domain.{action}', payload, ip)


def tls(db, user, account, method, body, ip):
    if method == 'GET':
        return c.rpc('domain.list', name=account['name'])
    action = allowed(body, {'issue', 'upload', 'redirect'})
    host = c.domain(body.get('domain'))
    find_domain(db, account, host)
    require_domain_proof(db, user, account, host)
    fields = {'name': account['name'], 'domain': host}
    if action == 'issue':
        if body.get('agree') is not True:
            raise c.Problem('Accept the Let’s Encrypt Subscriber Agreement to continue.')
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM jobs WHERE account_id=? AND state IN ('queued','running')",
                      (account['id'],)).fetchone():
            raise c.Problem('Wait for the pending account or site operation.', 409)
        return c.enqueue(db, user, account['id'], 'tls.issue', {**fields, 'email': body.get('email')}, ip)
    # Private key material is passed directly over the Unix socket. Jobs and audit
    # events record the hostname and operation only.
    if action == 'upload':
        fields.update(certificate=body.get('certificate'), key=body.get('key'))
    else:
        fields.update(enabled=body.get('enabled'))
    result = c.rpc(f'tls.{action}', **fields)
    c.audit(db, user['id'], f'tls.{action}', host, ip)
    return result


def databases(db, user, account, method, body, ip):
    if method == 'GET':
        return c.rpc('database.list', name=account['name'])
    action = allowed(body, {'create', 'password', 'delete', 'usage', 'import', 'export', 'download', 'export_delete'})
    result = c.rpc(f'database.{action}', name=account['name'], label=body.get('label'),
                   engine=body.get('engine'), password=body.get('password'), confirm=body.get('confirm'),
                   content=body.get('content'), file=body.get('file'), offset=body.get('offset'),
                   revision=body.get('revision'))
    if action not in ('usage', 'download'):
        c.audit(db, user['id'], f'database.{action}', account['id'], ip)
    return result


def dns(db, user, account, method, env, body, ip):
    if user['role'] != 'admin':
        raise c.Problem('Administrator required.', 403)
    if method == 'GET':
        query = parse_qs(env.get('QUERY_STRING', ''))
        host = c.domain(query.get('domain', [''])[0])
        find_domain(db, account, host)
        return c.rpc('dns.get', name=account['name'], domain=host)
    action = allowed(body, {'save', 'remove'})
    host = c.domain(body.get('domain'))
    find_domain(db, account, host)
    result = c.rpc(f'dns.{action}', name=account['name'], domain=host, records=body.get('records'),
                   confirm=body.get('confirm'))
    c.audit(db, user['id'], f'dns.{action}', host, ip)
    return result

def git_release(db, user, account, body, ip):
    db.execute('BEGIN IMMEDIATE')
    if db.execute("SELECT 1 FROM jobs WHERE account_id=? AND state IN ('queued','running')",
                  (account['id'],)).fetchone():
        raise c.Problem('Wait for the pending account operation.', 409)
    fields = {'name': account['name']}
    for key in ('repository', 'branch', 'destination'):
        value = body.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= 350:
            raise c.Problem('Enter a repository URL, branch and new destination folder.')
        fields[key] = value
    # The queued payload is readable in operational records. Validate the public
    # URL here as well so credentials cannot enter job storage.
    from agent.deployments import source_repository, branch_name
    fields['repository'] = source_repository(fields['repository'])
    fields['branch'] = branch_name(fields['branch'])
    return c.enqueue(db, user, account['id'], 'git.release', fields, ip)

def metrics(db, account, env):
    query = parse_qs(env.get('QUERY_STRING', ''))
    value = query.get('domain', [''])[0]
    if not value:
        return c.rpc('metrics.processes', name=account['name'])
    host = c.domain(value)
    find_domain(db, account, host)
    return c.rpc('metrics.web', name=account['name'], domain=host)

def wordpress(db, user, account, body, ip):
    host = c.domain(body.get('domain'))
    find_domain(db, account, host)
    require_domain_proof(db, user, account, host)
    keys = ('label', 'destination', 'title', 'username', 'email', 'password', 'db_password')
    values = {key: body.get(key) for key in keys}
    result = c.rpc('wordpress.install', name=account['name'], domain=host, **values)
    c.audit(db, user['id'], 'wordpress.install', host, ip)
    return result

def php(db, user, account, method, env, body, ip):
    if method == 'GET':
        query = parse_qs(env.get('QUERY_STRING', ''))
        return c.rpc('php.log' if query.get('view') == ['log'] else 'php.get', name=account['name'])
    fields = {key: body.get(key) for key in ('memory_mib', 'upload_mib', 'execution_seconds', 'show_errors')}
    result = c.rpc('php.settings', name=account['name'], settings=fields)
    c.audit(db, user['id'], 'php.settings', account['id'], ip)
    return result


def domain_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS domain_proofs (
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        host TEXT NOT NULL,
        token TEXT NOT NULL,
        expires INTEGER NOT NULL,
        verified INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(account_id,host)
    )""")


def issue_domain_proof(db, account, host):
    token = 'almapanel-' + secrets.token_urlsafe(24)
    expires = int(time.time()) + 86400
    db.execute("""DELETE FROM domain_proofs WHERE expires<=? AND NOT EXISTS(
        SELECT 1 FROM domains WHERE account_id=domain_proofs.account_id AND name=domain_proofs.host)""", (int(time.time()),))
    pending = db.execute('SELECT count(*) FROM domain_proofs WHERE account_id=? AND verified=0',
                         (account['id'],)).fetchone()[0]
    old = db.execute('SELECT 1 FROM domain_proofs WHERE account_id=? AND host=?', (account['id'], host)).fetchone()
    if pending >= 20 and not old:
        raise c.Problem('Finish or let an existing verification expire before generating another record.', 409)
    db.execute('''INSERT INTO domain_proofs(account_id,host,token,expires) VALUES(?,?,?,?)
        ON CONFLICT(account_id,host) DO UPDATE SET token=excluded.token,expires=excluded.expires,verified=0''',
        (account['id'], host, token, expires))
    return {'name': '_almapanel.' + host, 'type': 'TXT', 'value': token, 'expires': expires}


def verify_domain_proof(db, account, host):
    now = int(time.time())
    proof = db.execute('SELECT * FROM domain_proofs WHERE account_id=? AND host=? AND expires>?',
                       (account['id'], host, now)).fetchone()
    if not proof:
        raise c.Problem('Generate a fresh DNS verification record first.', 409)
    c.rpc('dns.verify', domain=host, token=proof['token'])
    result = db.execute('UPDATE domain_proofs SET verified=? WHERE account_id=? AND host=? AND token=?',
                        (now, account['id'], host, proof['token']))
    if result.rowcount != 1:
        raise c.Problem('The verification record changed. Verify the current record.', 409)
    return {'message': 'Domain ownership verified. You can save this domain now.'}


def require_domain_proof(db, user, account, host, *, current=False):
    if user['role'] == 'admin':
        return
    proof = db.execute('SELECT verified,expires FROM domain_proofs WHERE account_id=? AND host=?',
                       (account['id'], host)).fetchone()
    if not proof or not proof['verified'] or (current and proof['expires'] <= time.time()):
        raise c.Problem('Verify the domain’s DNS TXT record before continuing.', 409)

def site_security(db, user, account, method, env, body, ip):
    query = parse_qs(env.get('QUERY_STRING', ''))
    host = c.domain(query.get('domain', [''])[0] if method == 'GET' else body.get('domain'))
    find_domain(db, account, host)
    if method == 'GET':
        return c.rpc('site_security.get', name=account['name'], domain=host)
    action = allowed(body, {'set', 'remove', 'blocklist'})
    result = c.rpc(f'site_security.{action}', name=account['name'], domain=host,
                   path=body.get('path'), username=body.get('username'), password=body.get('password'),
                   addresses=body.get('addresses'))
    c.audit(db, user['id'], f'site_security.{action}', host, ip)
    return result


def site_options(db, user, account, method, env, body, ip):
    query = parse_qs(env.get('QUERY_STRING', ''))
    host = c.domain(query.get('domain', [''])[0] if method == 'GET' else body.get('domain'))
    find_domain(db, account, host)
    if method == 'GET':
        return c.rpc('site_options.get', name=account['name'], domain=host)
    allowed(body, {'set'})
    section = body.get('section')
    if section not in ('indexes', 'error_pages', 'hotlink', 'mime', 'optimize'):
        raise c.Problem('Choose indexes, error pages, hotlink protection or MIME types.')
    result = c.rpc('site_options.set', name=account['name'], domain=host, section=section, values=body.get('values'))
    c.audit(db, user['id'], f'site_options.{section}', host, ip)
    return result


def sftp(db, user, account, method, body, ip):
    if method == 'GET':
        return c.rpc('sftp.list', name=account['name'])
    action = allowed(body, {'add', 'remove'})
    result = c.rpc(f'sftp.{action}', name=account['name'], public_key=body.get('public_key'),
                   label=body.get('label'), fingerprint=body.get('fingerprint'))
    c.audit(db, user['id'], f'sftp.{action}', account['id'], ip)
    return result


MAIL_VIEWS = {'rules', 'usage', 'track', 'deliverability'}


def mail(db, user, account, method, body, ip, env=None):
    if method == 'GET':
        query = parse_qs((env or {}).get('QUERY_STRING', ''))
        tool = query.get('tool', [''])[0]
        if not tool:
            return c.rpc('mail.list', name=account['name'])
        if tool not in MAIL_VIEWS:
            raise c.Problem('Choose a supported mail view.')
        return c.rpc(f'mail.{tool}', name=account['name'], domain=query.get('domain', [None])[0],
                     query=query.get('query', [''])[0])
    action = allowed(body, {'domain', 'create', 'password', 'quota', 'state', 'retire', 'restore',
                            'forward', 'unforward', 'default', 'autoresponder', 'filters'})
    if action in ('default', 'autoresponder', 'filters'):
        if action == 'default':
            host = c.domain(body.get('domain'))
            find_domain(db, account, host)
        result = c.rpc(f'mail.{action}', name=account['name'], domain=body.get('domain'), address=body.get('address'),
                       target=body.get('target'), settings=body.get('settings'), scope=body.get('scope'),
                       rules=body.get('rules'))
        c.audit(db, user['id'], f'mail.{action}', account['id'], ip)
        return result
    if action == 'domain':
        host = c.domain(body.get('domain'))
        find_domain(db, account, host)
        if body.get('enabled') is True:
            require_domain_proof(db, user, account, host)
    fields = {key: body.get(key) for key in ('domain', 'address', 'target', 'password', 'quota_mib',
                                            'enabled', 'confirm')}
    result = c.rpc(f'mail.{action}', name=account['name'], **fields)
    c.audit(db, user['id'], f'mail.{action}', account['id'], ip)
    return result
