# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Manage public keys for the dedicated, chrooted almaPanel SFTP service."""
import base64
import hashlib
import json
from pathlib import Path
import re

from backend.core import name

PROFILE = Path('/etc/almapanel/sftp/profile.json')
KEYS = Path('/etc/almapanel-sftp-keys')
MAX_KEYS = 10
ED25519 = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'
KEY_DATA = re.compile(r'[A-Za-z0-9+/]{68}\Z')


def read_profile():
    if not PROFILE.is_file():
        return None
    data = json.loads(PROFILE.read_text())
    if type(data.get('port')) is not int or not 1024 <= data['port'] <= 65535 or data['port'] in (8443, 9080):
        raise ValueError('Invalid SFTP port.')
    # This is validation of the operator's listener profile, not a socket bind.
    if data.get('listen') not in ('127.0.0.1', '0.0.0.0'):  # nosec B104
        raise ValueError('Invalid SFTP listen profile.')
    return data


def parse_key(public_key, label):
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 64 or not label.isprintable():
        raise ValueError('Enter a key label with 1–64 printable characters.')
    if not isinstance(public_key, str) or len(public_key) > 1024 or not public_key.isprintable():
        raise ValueError('Paste a single OpenSSH Ed25519 public key.')
    fields = public_key.split(maxsplit=2)
    if len(fields) < 2 or fields[0] != 'ssh-ed25519' or not KEY_DATA.fullmatch(fields[1]):
        raise ValueError('Paste an OpenSSH Ed25519 public key that starts with ssh-ed25519.')
    blob = base64.b64decode(fields[1], validate=True)
    if not blob.startswith(ED25519) or len(blob) != len(ED25519) + 32:
        raise ValueError('Invalid OpenSSH Ed25519 public key.')
    fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')
    return {'fingerprint': fingerprint, 'key': 'ssh-ed25519 ' + fields[1], 'label': label.strip()}


def sync(account, meta, atomic):
    if not read_profile():
        return
    path = KEYS / ('ap_' + name(account))
    records = meta.get('sftp_keys', [])
    if meta.get('state') != 'active' or not records:
        path.unlink(missing_ok=True)
        return
    # Do not re-emit unvalidated text, comments or options into authorized_keys.
    lines = ['restrict ' + parse_key(row['key'], row['label'])['key'] for row in records]
    atomic(path, '\n'.join(lines) + '\n', mode=0o644)


def view(account, meta):
    config = read_profile()
    return {'available': config is not None, 'port': config['port'] if config else None,
            'listen': config['listen'] if config else None, 'username': 'ap_' + account,
            'keys': [{'fingerprint': row['fingerprint'], 'label': row['label']}
                     for row in meta.get('sftp_keys', [])]}


def manage(operation, account, data, args, atomic, persist):
    meta = data[account]
    if operation == 'sftp.list':
        return view(account, meta)
    if not read_profile():
        raise ValueError('Enable the separate SFTP service on the server first.')
    previous = meta.get('sftp_keys', [])
    if operation == 'sftp.add':
        entry = parse_key(args.get('public_key'), args.get('label'))
        if len(previous) >= MAX_KEYS:
            raise ValueError('An account can have up to 10 SFTP keys.')
        if any(row['fingerprint'] == entry['fingerprint'] for row in previous):
            raise ValueError('This key is already registered.')
        meta['sftp_keys'] = [*previous, entry]
    elif operation == 'sftp.remove':
        fingerprint = args.get('fingerprint')
        remain = [item for item in previous if item['fingerprint'] != fingerprint]
        if len(remain) == len(previous):
            raise ValueError('SFTP key not found on this account.')
        meta['sftp_keys'] = remain
    else:
        raise ValueError('SFTP operation not allowed.')
    try:
        sync(account, meta, atomic)
        persist(data)
    except OSError:
        meta['sftp_keys'] = previous
        sync(account, meta, atomic)
        raise
    return {'message': 'SFTP key added.' if operation == 'sftp.add' else
            'SFTP key removed. Any active transfer session ends when that connection closes.'}
