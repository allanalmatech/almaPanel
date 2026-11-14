# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""HTTPS basic authentication and deny rules for managed website paths."""
import ipaddress
from pathlib import Path
import re

from backend.core import domain
from agent import sites

AUTH_ROOT = Path('/var/lib/almapanel-site-auth')
BASIC_USER = re.compile(r'[a-zA-Z][a-zA-Z0-9_-]{2,31}\Z')
MAP_ID = re.compile(r'[a-f0-9]{24}\Z')
MAX_RULES = 10


def rules_path(value):
    if value == '/':
        return value
    if not isinstance(value, str) or not value.startswith('/'):
        raise ValueError('Use / for the whole website or a path such as /private.')
    result = sites.docroot(value.strip('/'))
    if not result:
        raise ValueError('Choose a directory path.')
    return '/' + result


def render(host, site, identifier):
    domain(host)
    if not MAP_ID.fullmatch(identifier):
        raise ValueError('Invalid website security identifier.')
    blocked = site.get('blocked', [])
    access = ''.join(f' deny {ipaddress.ip_network(source, strict=True)};\n' for source in blocked)
    items = site.get('privacy', {})
    if not items:
        return '', access
    realm = f'alma_realm_{identifier}'
    file = f'alma_auth_{identifier}'
    lines = [f'map $uri ${realm} {{', ' default off;']
    filenames = [f'map $uri ${file} {{', ' default /dev/null;']
    # Match the longest directory first. Nginx normalizes the URI before this,
    # and volatile recomputes after internal rewrites to a different location.
    for path, details in sorted(items.items(), key=lambda item: (-len(item[0]), item[0])):
        path = rules_path(path)
        encoded = details['id']
        if not MAP_ID.fullmatch(encoded):
            raise ValueError('Invalid directory credential file reference.')
        directory = re.escape(path).replace(r'\/', '/')
        match = '^/' if path == '/' else '^' + directory + '(/|$)'
        lines.append(f' "~{match}" "Restricted website";')
        filenames.append(f' "~{match}" {AUTH_ROOT}/{host}/{encoded}.passwd;')
    maps = '\n'.join([*lines, ' volatile;', '}', *filenames, ' volatile;', '}']) + '\n'
    return maps, access + f' auth_basic ${realm};\n auth_basic_user_file ${file};\n'


def password_line(username, password, run):
    if not isinstance(username, str) or not BASIC_USER.fullmatch(username):
        raise ValueError('Use a site username of 3–32 letters, digits, underscores or hyphens.')
    if (not isinstance(password, str) or len(password.encode()) > 128 or len(password) < 16
            or any(ord(char) < 32 for char in password)):
        raise ValueError('Use a 16–128 byte password without control characters.')
    # Feed the password through stdin. OpenSSL's SHA512-crypt is accepted by
    # Nginx's crypt() password-file implementation on the supported systems.
    digest = run(['/usr/bin/openssl', 'passwd', '-6', '-stdin'], input=password + '\n').strip()
    if not digest.startswith('$6$') or '\n' in digest:
        raise ValueError('Could not prepare the directory password.')
    return username + ':' + digest + '\n'


def networks(values):
    if not isinstance(values, list) or len(values) > 50:
        raise ValueError('Use up to 50 IP addresses or CIDR networks.')
    unique = set()
    for value in values:
        if not isinstance(value, str) or len(value) > 50 or '%' in value:
            raise ValueError('Use valid IPv4 or IPv6 addresses and CIDRs.')
        network = ipaddress.ip_network(value, strict=True)
        if network.prefixlen == 0:
            raise ValueError('Use account suspension to block every visitor.')
        unique.add(str(network))
    return sorted(unique)
