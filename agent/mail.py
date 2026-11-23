# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Account-scoped virtual mailbox and forwarder provisioning."""
from copy import deepcopy
import fcntl
import grp
import json
from pathlib import Path
import re

from agent import mail_rules
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
    return {'hostname': domain(item['hostname']), 'uid': uid, 'gid': gid, 'listen': listen,
            'sieve': item.get('sieve') is True}


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
        for host, target in state.get('defaults', {}).items():
            if domain(host) not in owned:
                raise ValueError('The root mail registry contains an invalid default address.')
            # A domain catch-all also matches real mailboxes, so each keeps an identity entry.
            for email in recipients:
                if email.endswith('@' + host):
                    aliases.setdefault(email, email)
            aliases['@' + host] = address(target)
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


def validate_default(state, host, target):
    if target is None:
        return
    if target.split('@')[1] in state['domains']:
        live = {email for email, item in state['mailboxes'].items() if not item.get('retired') and item['enabled']}
        if target not in live and target not in state['forwarders']:
            raise ValueError('Send unknown addresses to an active mailbox or forwarder in this account, or to an outside address.')


def mail_filters(state):
    return state.get('global_filters', []), state.get('filters', {}), state.get('autoresponders', {})


def scripts(account, state):
    """Sieve script text for every mailbox (None removes it)."""
    global_rules, filters, responders = mail_filters(state)
    result = {}
    for email, item in state.get('mailboxes', {}).items():
        active = not item.get('retired')
        result[email] = mail_rules.script(global_rules, filters.get(email, []), responders.get(email)) if active else None
    return result


def compile_check(contents, run):
    import tempfile
    with tempfile.TemporaryDirectory(prefix='alma-sieve-') as folder:
        for index, content in enumerate(item for item in contents if item):
            source = Path(folder) / f'{index}.sieve'
            source.write_text(content)
            run([str(mail_rules.SIEVEC), str(source), str(source.with_suffix('.svbin'))], timeout=15)


def prepare_scripts(account, state, settings, run, only=None):
    """Generate and compile the affected scripts; raise before anything is saved."""
    planned = scripts(account, state)
    if only is not None:
        planned = {email: content for email, content in planned.items() if email in only}
    if not settings.get('sieve'):
        if any(planned.values()):
            raise ValueError('Autoresponders and filters need the mail filter plugin. Ask the server administrator to re-run installer/enable-mail.sh.')
        return {}
    compile_check(planned.values(), run)
    return planned


def write_scripts(account, planned, settings):
    for email, content in planned.items():
        mail_rules.write_script(account, email, content, settings['uid'], settings['gid'])


def tool_state(meta, settings):
    state = meta.get('mail', {})
    global_rules, filters, responders = mail_filters(state)
    return {'available': settings is not None, 'filters_available': bool(settings and settings.get('sieve')),
            'hostname': settings['hostname'] if settings else None,
            'domains': sorted(state.get('domains', [])), 'defaults': state.get('defaults', {}),
            'mailboxes': sorted(email for email, item in state.get('mailboxes', {}).items() if not item.get('retired')),
            'forwarders': sorted(state.get('forwarders', {})), 'global_filters': global_rules,
            'filters': filters, 'autoresponders': responders}


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
        state.get('defaults', {}).pop(host, None)
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
    if operation == 'mail.rules':
        return tool_state(data[account], settings)
    if not settings:
        raise ValueError('The server administrator needs to enable managed mail.')
    meta = deepcopy(data[account])
    state = meta.setdefault('mail', {'domains': [], 'mailboxes': {}, 'forwarders': {}})
    updated = {**data, account: meta}
    action = operation.removeprefix('mail.')
    local = lambda value: address(value)
    if action == 'usage':
        return {'mailboxes': [{'address': email, 'quota_mib': item['quota_mib'], 'enabled': item['enabled'],
                               'bytes': mail_rules.directory_bytes(mail_rules.mailbox_home(account, email) / 'Maildir')}
                              for email, item in sorted(state['mailboxes'].items()) if not item.get('retired')]}
    if action == 'track':
        query = args.get('query') or ''
        if not isinstance(query, str) or len(query) > 254:
            raise ValueError('Search for part of an address of up to 254 characters.')
        identifiers = [item for service in ('smtpd', 'submission/smtpd', 'cleanup', 'qmgr', 'smtp', 'lmtp',
                                            'error', 'bounce', 'pickup') for item in ('-t', 'postfix/' + service)]
        output = run(['/usr/bin/journalctl', '--no-pager', '-o', 'short-iso', '--since', '72 hours ago',
                      '-n', '20000', *identifiers], timeout=20)
        return {'messages': mail_rules.track(output, state['domains'], query), 'hours': 72}
    if action == 'deliverability':
        host = domain(args.get('domain'))
        if host not in state['domains']:
            raise ValueError('Choose one of this account’s mail domains.')
        from agent import dns
        answers = {'MX': dns.lookup(host, 'MX', run)['answer'], 'TXT': dns.lookup(host, 'TXT', run)['answer'],
                   'DMARC': dns.lookup('_dmarc.' + host, 'TXT', run)['answer']}
        return mail_rules.deliverability(host, settings['hostname'], answers)
    if action in ('autoresponder', 'filters'):
        if action == 'autoresponder':
            email = address(args.get('address'))
            if email not in state['mailboxes'] or state['mailboxes'][email].get('retired'):
                raise ValueError('Choose an active mailbox in this account.')
            responders = state.setdefault('autoresponders', {})
            value = mail_rules.autoresponder(args.get('settings'), email)
            if value is None:
                responders.pop(email, None)
            else:
                responders[email] = value
            affected = {email}
        else:
            scope = args.get('scope')
            value = mail_rules.rules(args.get('rules'), local)
            if scope == 'account':
                state['global_filters'] = value
                affected = None
            else:
                email = address(scope)
                if email not in state['mailboxes'] or state['mailboxes'][email].get('retired'):
                    raise ValueError('Choose an active mailbox in this account.')
                state.setdefault('filters', {})[email] = value
                affected = {email}
        # Compile before saving, so an invalid script never replaces a working one.
        planned = prepare_scripts(account, state, settings, run, only=affected)
        persist(updated)
        write_scripts(account, planned, settings)
        return {'message': 'Autoresponder saved.' if action == 'autoresponder' else 'Email filters saved.'}
    if action == 'default':
        host = domain(args.get('domain'))
        if host not in state['domains']:
            raise ValueError('Choose one of this account’s mail domains.')
        target = mail_rules.default_target(args.get('target'), local)
        validate_default(state, host, target)
        defaults = state.setdefault('defaults', {})
        if target is None:
            defaults.pop(host, None)
        else:
            defaults[host] = target
        apply(updated, settings, run, atomic, persist)
        return {'message': 'Default address saved.'}
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
    for host, target in list(state.get('defaults', {}).items()):
        validate_default(state, host, target)
    apply(updated, settings, run, atomic, persist)
    if settings.get('sieve') and action in ('retire', 'restore', 'create'):
        write_scripts(account, prepare_scripts(account, state, settings, run, only={address(args.get('address'))}), settings)
    return {'message': 'Mail configuration saved.'}
