# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Email tools: default addresses, Sieve autoresponders and filters, mailbox usage,
delivery tracking and deliverability checks.

Sieve scripts are generated from structured, validated rules. Tenants never supply
raw Sieve, so every action, folder, address and string is checked here first.
"""
from datetime import date
import os
from pathlib import Path
import re
import stat

from backend.core import domain

VMAIL = Path('/var/vmail')
SCRIPT_NAME = '.dovecot.sieve'
SIEVEC = Path('/usr/bin/sievec')
MAX_RULES = 25
MAX_FORWARD_RULES = 5
FIELDS = ('from', 'to', 'subject', 'any')
MATCHES = ('contains', 'is', 'begins', 'ends')
ACTIONS = ('move', 'discard', 'forward')
FOLDER = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,39}\Z')
NO_DIR_FOLLOW = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def text(value, label, limit, multiline=False):
    if not isinstance(value, str):
        raise ValueError(f'Enter {label}.')
    value = value.replace('\r\n', '\n').strip()
    allowed = '\n\t' if multiline else '\t'
    if not value or len(value) > limit or any(ord(char) < 32 and char not in allowed for char in value):
        raise ValueError(f'Enter {label} of up to {limit} characters without control characters.')
    return value


def quote(value):
    """A Sieve quoted string (RFC 5228): only backslash and double quote are escaped."""
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def wildcard(value):
    """Escape a literal for a Sieve :matches pattern before quoting."""
    return value.replace('\\', '\\\\').replace('*', '\\*').replace('?', '\\?')


def default_target(value, local_address):
    """None rejects unknown addresses; otherwise a full address to receive them."""
    if value in (None, ''):
        return None
    return local_address(value)


def rule(value, local_address):
    if not isinstance(value, dict):
        raise ValueError('Invalid filter rule.')
    field, match, action = value.get('field'), value.get('match'), value.get('action')
    if field not in FIELDS or match not in MATCHES or action not in ACTIONS:
        raise ValueError('Choose a field, a comparison and an action for each filter.')
    result = {'name': text(value.get('name'), 'a filter name', 60), 'field': field, 'match': match,
              'value': text(value.get('value'), 'the text to look for', 200), 'action': action}
    if action == 'move':
        folder = value.get('target')
        if not isinstance(folder, str) or not FOLDER.fullmatch(folder.strip()):
            raise ValueError('Use a folder name of up to 40 letters, digits, spaces, hyphens or underscores.')
        result['target'] = folder.strip()
    elif action == 'forward':
        result['target'] = local_address(value.get('target'))
    return result


def rules(values, local_address):
    if not isinstance(values, list) or len(values) > MAX_RULES:
        raise ValueError(f'Use up to {MAX_RULES} filters.')
    result = [rule(item, local_address) for item in values]
    if sum(item['action'] == 'forward' for item in result) > MAX_FORWARD_RULES:
        raise ValueError(f'Use up to {MAX_FORWARD_RULES} forwarding filters.')
    return result


def autoresponder(value, email):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('Invalid autoresponder settings.')
    interval = value.get('interval_days', 1)
    if type(interval) is not int or not 1 <= interval <= 30:
        raise ValueError('Reply to each sender at most once every 1 to 30 days.')
    start, end = value.get('start') or '', value.get('end') or ''
    for label, item in (('start', start), ('end', end)):
        if item:
            try:
                date.fromisoformat(item)
            except (TypeError, ValueError):
                raise ValueError(f'Use YYYY-MM-DD for the {label} date.') from None
    if start and end and end < start:
        raise ValueError('The end date must be on or after the start date.')
    return {'subject': text(value.get('subject'), 'a subject', 120),
            'body': text(value.get('body'), 'a message', 4000, multiline=True),
            'interval_days': interval, 'start': start, 'end': end, 'address': email}


def condition(item):
    value = item['value']
    if item['match'] in ('contains', 'is'):
        comparator, pattern = ':' + item['match'], value
    else:
        comparator = ':matches'
        pattern = wildcard(value) + '*' if item['match'] == 'begins' else '*' + wildcard(value)
    pattern = quote(pattern)
    if item['field'] == 'subject':
        return f'header {comparator} "subject" {pattern}'
    if item['field'] == 'any':
        return f'header {comparator} ["from", "to", "cc", "subject"] {pattern}'
    return f'address {comparator} "{item["field"]}" {pattern}'


def script(global_rules, mailbox_rules, responder):
    """Return the Sieve script for one mailbox, or None when it needs none."""
    items = [*global_rules, *mailbox_rules]
    if not items and not responder:
        return None
    lines = ['# Generated by almaPanel. Changes made here are replaced.',
             'require ["fileinto", "mailbox", "copy", "vacation", "date", "relational"];']
    for item in items:
        lines.append(f'# {item["name"].replace(chr(10), " ")}')
        if item['action'] == 'move':
            action = f'fileinto :create {quote(item["target"])}; stop;'
        elif item['action'] == 'discard':
            action = 'discard; stop;'
        else:
            action = f'redirect :copy {quote(item["target"])};'
        lines.append(f'if {condition(item)} {{ {action} }}')
    if responder:
        reply = (f'vacation :days {responder["interval_days"]} :subject {quote(responder["subject"])} '
                 f':addresses [{quote(responder["address"])}] {quote(responder["body"])};')
        dates = []
        if responder['start']:
            dates.append(f'currentdate :value "ge" "date" {quote(responder["start"])}')
        if responder['end']:
            dates.append(f'currentdate :value "le" "date" {quote(responder["end"])}')
        lines.append(f'if allof({", ".join(dates)}) {{ {reply} }}' if dates else reply)
    return '\n'.join(lines) + '\n'


def mailbox_home(account, email):
    user, host = email.split('@')
    return VMAIL / account / host / user


def write_script(account, email, content, uid, gid):
    """Write or remove a mailbox's Sieve script without following links in the mail tree."""
    user, host = email.split('@')
    fd = os.open(VMAIL, NO_DIR_FOLLOW)
    try:
        for part in (account, host, user):
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
                os.chown(part, uid, gid, dir_fd=fd, follow_symlinks=False)
            except FileExistsError:
                pass
            next_fd = os.open(part, NO_DIR_FOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if os.fstat(fd).st_uid not in (uid, 0):
                raise ValueError('Unexpected ownership in the mail store.')
        if content is None:
            for name in (SCRIPT_NAME, SCRIPT_NAME.replace('.sieve', '.svbin')):
                try:
                    os.unlink(name, dir_fd=fd)
                except FileNotFoundError:
                    pass
            return
        temp = '.almapanel-sieve.tmp'
        try:
            os.unlink(temp, dir_fd=fd)
        except FileNotFoundError:
            pass
        handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
        try:
            os.write(handle, content.encode())
            os.fchown(handle, uid, gid)
            os.fsync(handle)
        finally:
            os.close(handle)
        os.rename(temp, SCRIPT_NAME, src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        os.close(fd)


def directory_bytes(path):
    """Total size of regular files below path, never following links."""
    total = 0
    try:
        top = os.open(path, NO_DIR_FOLLOW)
    except (FileNotFoundError, NotADirectoryError):
        return 0
    stack = [top]
    while stack:
        fd = stack.pop()
        try:
            for entry in os.scandir(fd):
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
                elif stat.S_ISDIR(info.st_mode):
                    try:
                        stack.append(os.open(entry.name, NO_DIR_FOLLOW, dir_fd=fd))
                    except OSError:
                        continue
        finally:
            os.close(fd)
    return total


# Track Delivery: Postfix log lines, correlated by queue ID.
LOG_LINE = re.compile(r'(?P<time>\S+) \S+ postfix/(?P<service>[a-z/-]+)\[\d+\]: (?P<queue>[0-9A-F]{8,12}|(?=[0-9A-Za-z]*[0-9])[0-9A-Za-z]{13,20}): (?P<rest>.*)\Z')
FIELD = re.compile(r'(\w+)=<?([^,<>]*)>?(?:,|\Z)')
STATUS = re.compile(r'status=(\w+)(?: \((?P<reason>.*)\))?')


def track(log_text, domains, query='', limit=200):
    """Messages to or from the given domains, newest first."""
    owned = {domain(host) for host in domains}
    query = query.strip().lower()
    messages = {}
    for line in log_text.splitlines():
        match = LOG_LINE.match(line)
        if not match:
            continue
        item = messages.setdefault(match['queue'], {'id': match['queue'], 'time': match['time'], 'from': '',
                                                    'deliveries': []})
        rest = match['rest']
        fields = dict(FIELD.findall(rest))
        if rest.startswith('from='):
            item['from'] = fields.get('from', '').lower()
        elif rest.startswith('to='):
            status = STATUS.search(rest)
            item['deliveries'].append({'to': fields.get('to', '').lower(), 'time': match['time'],
                                       'relay': fields.get('relay', ''),
                                       'status': status.group(1) if status else 'unknown',
                                       'detail': (status['reason'] or '')[:300] if status else ''})
    result = []
    for item in messages.values():
        for delivery in item['deliveries']:
            hosts = {item['from'].rpartition('@')[2], delivery['to'].rpartition('@')[2]}
            if not hosts & owned:
                continue
            if query and query not in item['from'] and query not in delivery['to']:
                continue
            result.append({'id': item['id'], 'from': item['from'], **delivery})
    result.sort(key=lambda entry: entry['time'], reverse=True)
    return result[:limit]


def deliverability(host, mail_hostname, answers):
    """Evaluate MX, SPF and DMARC from dig answer lines; suggest records when missing."""
    host = domain(host)

    def values(key, kind=None):
        found = []
        for line in answers.get(key, []):
            parts = line.split(None, 4)
            if len(parts) == 5 and parts[3] == (kind or key):
                found.append(parts[4])
        return found

    def txt(record):
        return ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', record)) or record

    mx = [record.split()[-1].rstrip('.').lower() for record in values('MX')]
    spf = [txt(record) for record in values('TXT') if txt(record).lower().startswith('v=spf1')]
    dmarc = [txt(record) for record in values('DMARC', 'TXT') if txt(record).lower().startswith('v=dmarc1')]
    checks = [
        {'name': 'MX', 'state': 'pass' if mail_hostname in mx else ('warn' if mx else 'fail'),
         'found': mx, 'suggested': f'{host}. MX 10 {mail_hostname}.',
         'detail': 'Mail for the domain should be delivered to this server.'},
        {'name': 'SPF', 'state': 'fail' if not spf else ('warn' if len(spf) > 1 else 'pass'),
         'found': spf, 'suggested': f'{host}. TXT "v=spf1 mx a:{mail_hostname} ~all"',
         'detail': 'Lists the servers allowed to send mail for the domain. Publish exactly one SPF record.'},
        {'name': 'DMARC', 'state': 'pass' if len(dmarc) == 1 else ('warn' if dmarc else 'fail'),
         'found': dmarc, 'suggested': f'_dmarc.{host}. TXT "v=DMARC1; p=none; rua=mailto:postmaster@{host}"',
         'detail': 'Tells receivers how to treat mail that fails SPF or DKIM. Start with p=none.'},
        {'name': 'DKIM', 'state': 'info', 'found': [], 'suggested': '',
         'detail': 'DKIM signing is planned for a later release.'},
    ]
    return {'domain': host, 'checks': checks}
