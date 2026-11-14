# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Small dependency-free control-plane primitives; no privileged commands here."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('ALMA_STATE', '/var/lib/almapanel'))
SOCKET = os.environ.get('ALMA_SOCKET', '/run/almapanel/agent.sock')
USERNAME = re.compile(r'[a-z][a-z0-9]{2,15}\Z')
DOMAIN = re.compile(r'(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z')

class Problem(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)

def name(value):
    if not isinstance(value, str) or not USERNAME.fullmatch(value):
        raise Problem('Use 3–16 lowercase letters or numbers, starting with a letter.')
    return value

def domain(value):
    if not isinstance(value, str) or not DOMAIN.fullmatch(value):
        raise Problem('Use a lowercase fully qualified DNS name, without a scheme or path.')
    return value

def password_hash(password):
    if not isinstance(password, str) or not 14 <= len(password) <= 128:
        raise Problem('Password must contain 14–128 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ':' + digest.hex()

def password_ok(password, encoded):
    try:
        salt, expected = encoded.split(':')
        if not isinstance(password, str) or len(password) > 128:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

def connect():
    db = sqlite3.connect(STATE / 'panel.sqlite3', timeout=10, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT / 'database/migrations/001_initial.sql').read_text())
        from backend import hosting, notifications, schedules, security
        security.setup_tables(db)
        schedules.setup_tables(db)
        hosting.domain_table(db)
        notifications.setup_tables(db)
        if not db.execute('SELECT 1 FROM users').fetchone():
            token = STATE / 'setup-token'
            if not token.exists():
                fd = os.open(token, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'w') as f:
                    f.write(secrets.token_urlsafe(32))

def audit(db, actor, action, target, ip):
    db.execute('INSERT INTO audit(actor_id,action,target,ip,created) VALUES(?,?,?,?,?)',
               (actor, action, str(target), ip, int(time.time())))

def rpc(operation, **args):
    request = json.dumps({'operation': operation, 'args': args}, ensure_ascii=False,
                         separators=(',', ':')).encode() + b'\n'
    if len(request) > 1_600_000:
        raise Problem('Operation exceeds the agent request limit.', 413)
    try:
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(150)
            s.connect(SOCKET)
            s.sendall(request)
            data = s.makefile('rb').readline(3_000_001)
        if len(data) > 3_000_000:
            raise Problem('Agent response exceeded limit.', 502)
        result = json.loads(data)
        if not result['ok']:
            raise Problem(result['error'], 502)
        return result['data']
    except (OSError, ValueError, KeyError) as exc:
        raise Problem('Privileged agent unavailable; inspect service logs.', 503) from exc

def scoped_account(db, user, account_id):
    row = db.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()
    if not row or not (user['role'] == 'admin' or row['user_id'] == user['id'] or
                      (user['role'] == 'reseller' and row['owner_id'] == user['id'])):
        raise Problem('Account not found.', 404)
    return row

def enqueue(db, user, account, operation, payload, ip):
    cur = db.execute('INSERT INTO jobs(actor_id,account_id,operation,payload,created) VALUES(?,?,?,?,?)',
                     (user['id'], account, operation, json.dumps(payload), int(time.time())))
    audit(db, user['id'], operation, account, ip)
    return {'job_id': cur.lastrowid, 'state': 'queued'}
