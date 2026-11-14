# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Account-scoped virtual mailbox and forwarder provisioning."""
from copy import deepcopy
import fcntl
import grp
import json
from pathlib import Path
import re

from agent.site_security import password_hash
from backend.core import domain, name

PROFILE = Path('/etc/almapanel/mail/profile.json')
MAP_DIR = Path('/etc/postfix/almapanel')
PASSWD = Path('/etc/dovecot/almapanel/passwd')
LOCAL = re.compile(r'[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)*\Z')
CRYPT_HASH = re.compile(r'\$6\$[A-Za-z0-9./]+\$[A-Za-z0-9./]{86}\Z')
MAX_MAILBOXES = 20
MAX_FORWARDERS = 30


def address(value):
    if not isinstance(value, str) or len(value) > 254 or value.count('@') != 1:
        raise ValueError('Enter a full mailbox address.')
    user, host = value.split('@')
    if len(user) > 64 or not LOCAL.fullmatch(user):
        raise ValueError('Use a lowercase address with letters, numbers, periods, underscores or hyphens.')
    return f'{user}@{domain(host)}'


def profile():
    if not PROFILE.is_file():
        return None
    item = json.loads(PROFILE.read_text())
    uid, gid = int(item['uid']), int(item['gid'])
    if not (1 <= uid < 2**31 and 1 <= gid < 2**31):
        raise ValueError('Invalid managed mail service identity.')
    listen = item['listen']
    if listen not in ('loopback', 'public'):
        raise ValueError('Invalid mail listener setting.')
    return {'hostname': domain(item['hostname']), 'uid': uid, 'gid': gid, 'listen': listen}


def inventory(meta, settings):
    state = meta.get('mail', {})
    return {
        'available': settings is not None,
        'hostname': settings['hostname'] if settings else None,
        'listen': settings['listen'] if settings else None,
        'domains': sorted(state.get('domains', [])),
        'mailboxes': [
            {'address': email, 'quota_mib': item['quota_mib'], 'enabled': item['enabled'],
             'retired': item.get('retired', False)}
            for email, item in sorted(state.get('mailboxes', {}).items())
        ],
        'forwarders': [{'source': source, 'target': target}
                       for source, target in sorted(state.get('forwarders', {}).items())],
    }


def quota(value):
    if type(value) is not int or not 1 <= value <= 512:
        raise ValueError('Choose a mailbox quota between 1 and 512 MiB.')
    return value


def configuration(data, settings):
    domains, recipients, aliases, senders = {}, {}, {}, {}
    password_lines = []
    for account, meta in data.items():
        name(account)
        state = meta.get('mail', {})
        owned = {domain(host) for host in state.get('domains', [])}
        if owned.difference(meta['domains']) or owned.intersection(domains):
            raise ValueError('A mail domain is assigned to the wrong hosting account.')
        domains.update(dict.fromkeys(owned, '1'))
        if meta['state'] != 'active':
            continue
        for raw, item in state.get('mailboxes', {}).items():
            if not item['enabled'] or item.get('retired'):
                continue
            email = address(raw)
            user, host = email.split('@')
            digest = item['hash']
            if host not in owned or not CRYPT_HASH.fullmatch(digest):
                raise ValueError('The root mail registry contains an invalid mailbox.')
            home = f'/var/vmail/{account}/{host}/{user}'
            password_lines.append(f"{email}:{{SHA512-CRYPT}}{digest}:{settings['uid']}:{settings['gid']}::"
                                  f"{home}::userdb_quota_rule=*:bytes={quota(item['quota_mib'])}M\n")
            recipients[email] = '1'
            senders[email] = email
        for raw, target in state.get('forwarders', {}).items():
            email = address(raw)
            if email.split('@')[1] not in owned or email in recipients:
                raise ValueError('The root mail registry contains an invalid forwarder.')
            aliases[email] = address(target)
    paths = {PASSWD: ''.join(sorted(password_lines))}
    for filename, records in zip(('domains', 'recipients', 'aliases', 'senders'),
                                 (domains, recipients, aliases, senders)):
        paths[MAP_DIR / filename] = ''.join(f'{key} {value}\n' for key, value in sorted(records.items()))
    return paths


def apply(data, settings, run, atomic, persist=None):
    paths = configuration(data, settings)
    with PROFILE.with_name('lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Mail maintenance is in progress. Try again shortly.') from error
        original = {path: path.read_text() for path in paths}
        dovecot_group = grp.getgrnam('dovecot').gr_gid

        def write(contents):
            for path, value in contents.items():
                if path == PASSWD:
                    atomic(path, value, mode=0o640, group=dovecot_group)
                else:
                    atomic(path, value, mode=0o644)

        def reload():
            run(['/usr/bin/systemctl', 'reload', 'dovecot.service', 'postfix.service'], timeout=20)

        try:
            write(paths)
            run(['/usr/bin/doveconf', '-n'], timeout=10)
            # The generated text maps are validated by configuration(). The
            # packaged Postfix process handles reload outside the broker sandbox.
            reload()
            if persist:
                persist(data)
        except Exception:
            write(original)
            reload()
            raise


def validate_forwarders(data):
    forwarders = {source: target for meta in data.values()
                  for source, target in meta.get('mail', {}).get('forwarders', {}).items()}
    for start in forwarders:
        cursor = start
        seen = set()
        while cursor in forwarders:
            if cursor in seen or len(seen) >= 10:
                raise ValueError('The forwarder would create a loop or exceed ten forwarding hops.')
            seen.add(cursor)
            cursor = forwarders[cursor]


def configure_domain(meta, state, settings, args):
    host = domain(args.get('domain'))
    enabled = args.get('enabled')
    if host not in meta['domains'] or host == settings['hostname'] or type(enabled) is not bool:
        raise ValueError('Choose a website domain and whether it should accept local mail.')
    existing = host in state['domains']
    if existing == enabled:
        return False
    if enabled:
        state['domains'].append(host)
    else:
        active = [email for email, item in state['mailboxes'].items() if not item.get('retired')]
        if any(email.endswith('@' + host) for email in [*active, *state['forwarders']]):
            raise ValueError('Archive the mailboxes and remove the forwarders for this domain first.')
        state['domains'].remove(host)
    return True


def configure_mailbox(state, email, action, args, run):
    mailboxes = state['mailboxes']
    item = mailboxes.get(email)
    if action == 'create':
        if item or email in state['forwarders'] or len(mailboxes) >= MAX_MAILBOXES:
            raise ValueError('This address is reserved or the account mailbox limit was reached.')
        limit = quota(args.get('quota_mib'))
        mailboxes[email] = {'hash': password_hash(args.get('password'), run), 'quota_mib': limit, 'enabled': True}
        return
    if not item or bool(item.get('retired')) != (action == 'restore'):
        raise ValueError('Mailbox unavailable for this action.')
    if action in ('password', 'restore'):
        item['hash'] = password_hash(args.get('password'), run)
        if action == 'restore':
            item.update(retired=False, enabled=True)
    elif action == 'quota':
        item['quota_mib'] = quota(args.get('quota_mib'))
    elif action == 'state':
        if type(args.get('enabled')) is not bool:
            raise ValueError('Choose whether the mailbox should be enabled.')
        item['enabled'] = args['enabled']
    elif action == 'retire':
        if args.get('confirm') != email:
            raise ValueError('Confirm the mailbox address to archive it.')
        del item['hash']
        item.update(retired=True, enabled=False)
    else:
        raise ValueError('Mail operation not allowed.')


def manage(operation, account, data, args, run, atomic, persist):
    settings = profile()
    if operation == 'mail.list':
        return inventory(data[account], settings)
    if not settings:
        raise ValueError('The server administrator needs to enable managed mail.')
    meta = deepcopy(data[account])
    state = meta.setdefault('mail', {'domains': [], 'mailboxes': {}, 'forwarders': {}})
    updated = {**data, account: meta}
    action = operation.removeprefix('mail.')
    if action == 'domain':
        if not configure_domain(meta, state, settings, args):
            return {'message': 'Mail routing is already configured as requested.'}
    else:
        email = address(args.get('address'))
        if email.split('@')[1] not in state['domains']:
            raise ValueError('Use an address in one of this account’s enabled mail domains.')
        forwarders = state['forwarders']
        if action == 'forward':
            if email in state['mailboxes'] or (email not in forwarders and len(forwarders) >= MAX_FORWARDERS):
                raise ValueError('This address is reserved or the account forwarder limit was reached.')
            forwarders[email] = address(args.get('target'))
            validate_forwarders(updated)
        elif action == 'unforward':
            if email not in forwarders:
                raise ValueError('Forwarder not found.')
            del forwarders[email]
        else:
            configure_mailbox(state, email, action, args, run)
    apply(updated, settings, run, atomic, persist)
    return {'message': 'Mail configuration saved.'}
