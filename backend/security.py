# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""TOTP verification, recovery codes and read-only API tokens."""
import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import quote

from backend import core as c

STEP = 30
ISSUER = 'almaPanel'
TOKEN_LIFETIME = 90 * 86400


def setup_tables(db):
    # Additive tables can coexist with schema-v1 alpha.2 during a code rollback.
    db.executescript("""
        CREATE TABLE IF NOT EXISTS user_mfa (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            secret TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            last_used_step INTEGER NOT NULL DEFAULT -1
        );
        CREATE TABLE IF NOT EXISTS recovery_codes (
            user_id INTEGER NOT NULL REFERENCES users(id),
            digest TEXT NOT NULL,
            PRIMARY KEY (user_id,digest)
        );
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            label TEXT NOT NULL,
            digest TEXT NOT NULL UNIQUE,
            created INTEGER NOT NULL,
            expires INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_api_tokens_owner ON api_tokens(user_id);
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            display_name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT ''
        );
    """)


def hash_secret(value):
    return hashlib.sha256(value.encode()).hexdigest()


def toggle_sessions(db, user_id):
    db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
    db.execute('DELETE FROM api_tokens WHERE user_id=?', (user_id,))


def totp(secret, step):
    key = base64.b32decode(secret)
    mac = hmac.new(key, step.to_bytes(8, 'big'), hashlib.sha1).digest()
    offset = mac[-1] & 15
    return f'{(int.from_bytes(mac[offset:offset + 4], "big") & 0x7fffffff) % 1_000_000:06}'


def candidate_step(secret, code, last, now=None):
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
        return None
    step = int(time.time() if now is None else now) // STEP
    for current in (step - 1, step, step + 1):
        if current > last and current >= 0 and hmac.compare_digest(totp(secret, current), code):
            return current
    return None


def login_second_factor(db, user_id, code):
    entry = db.execute('SELECT * FROM user_mfa WHERE user_id=? AND enabled=1', (user_id,)).fetchone()
    if not entry:
        return True
    accepted = candidate_step(entry['secret'], code, entry['last_used_step'])
    if accepted is not None:
        result = db.execute("""UPDATE user_mfa SET last_used_step=?
            WHERE user_id=? AND enabled=1 AND last_used_step<?""", (accepted, user_id, accepted))
        return result.rowcount == 1
    if isinstance(code, str) and re.fullmatch(r'[a-f0-9]{16}', code):
        result = db.execute('DELETE FROM recovery_codes WHERE user_id=? AND digest=?',
                            (user_id, hash_secret(code)))
        return result.rowcount == 1
    return False


def mfa(db, user, method, body, ip):
    user_id = user['id']
    if method == 'GET':
        row = db.execute('SELECT enabled FROM user_mfa WHERE user_id=?', (user_id,)).fetchone()
        count = db.execute('SELECT count(*) FROM recovery_codes WHERE user_id=?', (user_id,)).fetchone()[0]
        return {'enabled': bool(row and row['enabled']), 'recovery_codes_left': count}
    db.execute('BEGIN IMMEDIATE')
    # Re-read after taking the write lock to avoid racing a password change.
    password = db.execute('SELECT password FROM users WHERE id=?', (user_id,)).fetchone()[0]
    if not c.password_ok(body.get('password'), password):
        raise c.Problem('Current password is incorrect.', 403)
    entry = db.execute('SELECT * FROM user_mfa WHERE user_id=?', (user_id,)).fetchone()
    action = body.get('action')
    if action == 'begin':
        if entry and entry['enabled']:
            raise c.Problem('Two-factor authentication is already enabled.', 409)
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        db.execute('''INSERT INTO user_mfa(user_id,secret) VALUES(?,?)
            ON CONFLICT(user_id) DO UPDATE SET secret=excluded.secret,last_used_step=-1''', (user_id, secret))
        uri = f'otpauth://totp/{ISSUER}:{quote(user["username"])}?secret={secret}&issuer={ISSUER}'
        return {'secret': secret, 'uri': uri}
    if action == 'confirm':
        if not entry or entry['enabled']:
            raise c.Problem('Start a new two-factor setup first.', 409)
        step = candidate_step(entry['secret'], body.get('code'), entry['last_used_step'])
        if step is None:
            raise c.Problem('Invalid authenticator code.', 403)
        codes = [secrets.token_hex(8) for _ in range(8)]
        db.executemany('INSERT INTO recovery_codes VALUES(?,?)',
                       [(user_id, hash_secret(code)) for code in codes])
        db.execute('UPDATE user_mfa SET enabled=1,last_used_step=? WHERE user_id=?', (step, user_id))
        toggle_sessions(db, user_id)
        c.audit(db, user_id, 'mfa.enabled', user_id, ip)
        return {'recovery_codes': codes}
    if action == 'disable':
        if not entry or not entry['enabled'] or not login_second_factor(db, user_id, body.get('code')):
            raise c.Problem('Supply a valid authenticator or recovery code.', 403)
        db.execute('DELETE FROM user_mfa WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM recovery_codes WHERE user_id=?', (user_id,))
        toggle_sessions(db, user_id)
        c.audit(db, user_id, 'mfa.disabled', user_id, ip)
        return {'message': 'Two-factor authentication disabled. Sign in again.'}
    raise c.Problem('Choose a two-factor authentication operation.')


def tokens(db, user, method, body, ip):
    user_id = user['id']
    if method == 'GET':
        return [dict(row) for row in db.execute(
            'SELECT id,label,created,expires FROM api_tokens WHERE user_id=? AND expires>? ORDER BY id',
            (user_id, int(time.time())))]
    db.execute('BEGIN IMMEDIATE')
    if body.get('action') == 'revoke':
        if type(body.get('id')) is not int:
            raise c.Problem('Choose a token to revoke.')
        if not db.execute('DELETE FROM api_tokens WHERE id=? AND user_id=?',
                          (body['id'], user_id)).rowcount:
            raise c.Problem('Token not found.', 404)
        c.audit(db, user_id, 'token.revoked', body['id'], ip)
        return {'message': 'Token revoked.'}
    if body.get('action') != 'create':
        raise c.Problem('Choose an API token operation.')
    label = body.get('label')
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 60:
        raise c.Problem('Enter a label of 1–60 characters.')
    password = db.execute('SELECT password FROM users WHERE id=?', (user_id,)).fetchone()[0]
    if not c.password_ok(body.get('password'), password) or not login_second_factor(db, user_id, body.get('code')):
        raise c.Problem('Supply the current password and authenticator code if enabled.', 403)
    now = int(time.time())
    db.execute('DELETE FROM api_tokens WHERE expires<=?', (now,))
    if db.execute('SELECT count(*) FROM api_tokens WHERE user_id=?', (user_id,)).fetchone()[0] >= 10:
        raise c.Problem('Revoke a token before creating another one.', 409)
    secret = 'alma_ro_' + secrets.token_urlsafe(32)
    item = db.execute('INSERT INTO api_tokens(user_id,label,digest,created,expires) VALUES(?,?,?,?,?)',
                      (user_id, label.strip(), hash_secret(secret), now, now + TOKEN_LIFETIME))
    c.audit(db, user_id, 'token.created', item.lastrowid, ip)
    return {'token': secret, 'expires': now + TOKEN_LIFETIME}


def authenticate_token(db, value, path, method):
    permitted = path == '/api/accounts' or re.fullmatch(
        r'/api/accounts/[0-9]+/(?:domains|stats|metrics)', path
    )
    if method != 'GET' or not permitted:
        raise c.Problem('This token permits read-only hosting inventory and metrics.', 403)
    if not isinstance(value, str) or not re.fullmatch(r'Bearer alma_ro_[A-Za-z0-9_-]{43}', value):
        raise c.Problem('Invalid API token.', 401)
    user = db.execute("""SELECT u.* FROM api_tokens t JOIN users u ON u.id=t.user_id
        WHERE t.digest=? AND t.expires>? AND u.enabled=1""",
        (hash_secret(value[7:]), int(time.time()))).fetchone()
    if not user:
        raise c.Problem('Invalid or expired API token.', 401)
    return user


def profile(db, user, method, body, ip):
    if method == 'GET':
        result = db.execute('SELECT display_name,email FROM user_profiles WHERE user_id=?', (user['id'],)).fetchone()
        return dict(result) if result else {'display_name': '', 'email': ''}
    display, email = body.get('display_name'), body.get('email')
    if (not isinstance(display, str) or len(display) > 80 or any(ord(char) < 32 for char in display)
            or not isinstance(email, str) or len(email) > 254
            or (email and not re.fullmatch(r'[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', email))):
        raise c.Problem('Enter a display name and valid contact email.')
    db.execute("""INSERT INTO user_profiles VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,email=excluded.email""",
        (user['id'], display.strip(), email))
    c.audit(db, user['id'], 'profile.updated', user['id'], ip)
    return {'message': 'Contact information saved.'}
