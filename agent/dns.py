# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Authoritative forward zones rendered from typed DNS records."""
import ipaddress
import json
from pathlib import Path
import re
import time

from backend.core import domain

CONFIG = Path('/etc/almapanel/dns-profile.json')
RECORD_TYPES = ('A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SRV', 'CAA')
LABEL = re.compile(r'[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\Z')
LIMIT = 100


def profile():
    if not CONFIG.is_file():
        return None
    settings = json.loads(CONFIG.read_text())
    layout = settings['layout']
    if layout == 'ubuntu':
        directory, service = Path('/etc/bind'), 'named'
    elif layout == 'amazon':
        directory, service = Path('/var/named'), 'named'
    else:
        raise ValueError('Unknown DNS server configuration.')
    nameservers = settings['nameservers']
    if not isinstance(nameservers, list) or not 1 <= len(set(nameservers)) <= 4:
        raise ValueError('Configure one to four authoritative nameservers.')
    return {'directory': directory, 'service': service, 'nameservers': [domain(x) for x in nameservers]}


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'Expected a number from {minimum} to {maximum}.')
    return value


def owner(value, zone):
    if value == '@':
        return value
    if not isinstance(value, str) or not value or len(value) + len(zone) + 1 > 253:
        raise ValueError('Invalid DNS record name.')
    parts = value.lower().split('.')
    if not all(LABEL.fullmatch(part) or (i == 0 and part == '*') for i, part in enumerate(parts)):
        raise ValueError('Enter a record name relative to this zone, such as www or _dmarc.')
    return '.'.join(parts)


def target(value, *, dot_allowed=False):
    if dot_allowed and value == '.':
        return value
    return domain(value.rstrip('.') if isinstance(value, str) else value) + '.'


def records(raw, zone):
    if not isinstance(raw, list) or len(raw) > LIMIT:
        raise ValueError('Enter at most 100 DNS records.')
    result = []
    names = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError('Each DNS record must be an object.')
        kind = entry.get('type')
        record = {'name': owner(entry.get('name'), zone), 'type': kind,
                  'ttl': integer(entry.get('ttl', 3600), 60, 604800)}
        value = entry.get('value')
        if not isinstance(value, str) or not 1 <= len(value) <= 255:
            raise ValueError('Invalid DNS record value.')
        if kind in ('A', 'AAAA'):
            # IPv6 zone suffixes are local to an interface and not valid DNS rdata.
            ip = ipaddress.ip_address(value)
            if ip.version != (4 if kind == 'A' else 6) or '%' in value:
                raise ValueError('Address does not match the record type.')
            record['value'] = str(ip)
        elif kind in ('CNAME', 'MX', 'SRV'):
            record['value'] = target(value, dot_allowed=kind in ('MX', 'SRV'))
            if kind in ('MX', 'SRV'):
                record['priority'] = integer(entry.get('priority'), 0, 65535)
            if kind == 'SRV':
                record['weight'] = integer(entry.get('weight'), 0, 65535)
                record['port'] = integer(entry.get('port'), 0, 65535)
        elif kind in ('TXT', 'CAA'):
            if not value.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError('DNS text must use printable ASCII characters.')
            record['value'] = value
            if kind == 'CAA':
                record['flag'] = integer(entry.get('flag', 0), 0, 255)
                record['tag'] = entry.get('tag')
                if record['tag'] not in ('issue', 'issuewild', 'iodef'):
                    raise ValueError('CAA tag must be issue, issuewild or iodef.')
        else:
            raise ValueError('Unsupported DNS record type.')
        siblings = names.setdefault(record['name'], [])
        if ((kind == 'CNAME' and (record['name'] == '@' or siblings)) or
                any(previous['type'] == 'CNAME' for previous in siblings)):
            raise ValueError('A CNAME cannot coexist with other records or be used at the zone apex.')
        if any(previous['type'] == kind and previous['ttl'] != record['ttl'] for previous in siblings):
            raise ValueError('Records of the same name and type must use one TTL.')
        if record in siblings:
            raise ValueError('Duplicate DNS record.')
        siblings.append(record)
        result.append(record)
    aliases = {item['name'] + '.' + zone + '.' for item in result if item['type'] == 'CNAME'}
    if any(item['type'] in ('MX', 'SRV') and item['value'] in aliases for item in result):
        raise ValueError('MX and SRV targets cannot be CNAME records in this zone.')
    return result


def render(zone, nameservers, serial, entries):
    domain(zone)
    nameservers = [domain(name) + '.' for name in nameservers]
    lines = [f'$ORIGIN {zone}.', '$TTL 3600',
             f'@ IN SOA {nameservers[0]} hostmaster.{zone}. ({serial} 3600 600 604800 300)']
    lines.extend(f'@ IN NS {server}' for server in nameservers)
    for item in entries:
        value = item['value']
        kind = item['type']
        if kind in ('TXT', 'CAA'):
            value = '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
        if kind == 'MX':
            value = f"{item['priority']} {value}"
        if kind == 'SRV':
            value = f"{item['priority']} {item['weight']} {item['port']} {value}"
        if kind == 'CAA':
            value = f"{item['flag']} {item['tag']} {value}"
        lines.append(f"{item['name']} {item['ttl']} IN {kind} {value}")
    return '\n'.join(lines) + '\n'


def inventory(settings, data):
    path = settings['directory']
    clauses = []
    for meta in data.values():
        for host in sorted(meta.get('zones', {})):
            domain(host)
            clauses.append(f'zone "{host}" {{ type primary; file "{path}/alma-{host}.zone"; '
                           'allow-update { none; }; allow-transfer { none; }; };')
    return '\n'.join(clauses) + '\n'


def replace(operation, account, data, args, run, configs, persist):
    settings = profile()
    meta = data[account]
    zones = meta.setdefault('zones', {})
    host = domain(args.get('domain'))
    if host not in meta['domains']:
        raise ValueError('Domain does not belong to this account.')
    current = zones.get(host)
    if operation == 'dns.get':
        return {'available': bool(settings), 'nameservers': settings['nameservers'] if settings else [],
                'active': current is not None, 'records': current['records'] if current else []}
    if not settings:
        raise ValueError('Configure managed DNS on the server first.')
    zonefile = settings['directory'] / f'alma-{host}.zone'
    if operation == 'dns.remove':
        if not current:
            return {'message': 'No managed zone exists.'}
        if args.get('confirm') != host:
            raise ValueError('Type the domain name to delete the managed DNS zone.')
        del zones[host]
        content = None
    elif operation == 'dns.save':
        saved = records(args.get('records'), host)
        serial = max(int(time.time()), (current['serial'] + 1) if current else 1)
        content = render(host, settings['nameservers'], serial, saved)
        zones[host] = {'serial': serial, 'records': saved}
    else:
        raise ValueError('DNS operation not allowed.')
    include = settings['directory'] / 'almapanel-zones.conf'
    previous = {path: path.read_text() if path.is_file() else None for path in (zonefile, include)}
    executable = next((path for path in ('/usr/bin/named-checkconf', '/usr/sbin/named-checkconf')
                       if Path(path).is_file()), None)
    if not executable:
        raise ValueError('named-checkconf is unavailable.')
    validator = [executable, '-z']
    configs({zonefile: content, include: inventory(settings, data)}, settings['service'], validator)
    try:
        persist()
    except OSError:
        configs(previous, settings['service'], validator)
        raise
    return {'message': 'Managed DNS configuration applied.'}


def verify_txt(host, token, run):
    host = domain(host)
    if not isinstance(token, str) or not re.fullmatch(r'almapanel-[A-Za-z0-9_-]{32}', token):
        raise ValueError('Invalid DNS verification token.')
    executable = Path('/usr/bin/dig')
    if not executable.is_file():
        raise ValueError('The server administrator needs to install dig for domain verification.')
    output = run([str(executable), '-r', '+time=3', '+tries=1', '+short', 'TXT', '_almapanel.' + host],
                 timeout=8)
    if '"' + token + '"' not in output.splitlines():
        raise ValueError('The required DNS TXT record is not visible yet.')
    return {'verified': True}
