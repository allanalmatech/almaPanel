# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Unacknowledged job outcomes in the caller's hosting scope."""
from backend import core as c


def setup_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS notification_receipts (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        PRIMARY KEY(user_id,job_id)
    )''')


def inbox(db, user, method, body, ip):
    role = user['role']
    user_id = user['id']
    if method == 'POST':
        item = body.get('id')
        if type(item) is not int:
            raise c.Problem('Choose a notification to dismiss.')
        exists = db.execute('''SELECT 1 FROM jobs j LEFT JOIN accounts a ON a.id=j.account_id
            WHERE (?='admin' OR j.actor_id=? OR a.user_id=? OR (?='reseller' AND a.owner_id=?))
              AND j.id=? AND j.state IN ('failed','interrupted','succeeded')''',
            (role, user_id, user_id, role, user_id, item)).fetchone()
        if not exists:
            raise c.Problem('Notification not found.', 404)
        db.execute('INSERT OR IGNORE INTO notification_receipts VALUES(?,?)', (user_id, item))
        return {'message': 'Notification dismissed.'}
    rows = db.execute('''SELECT j.id,j.operation,j.state,j.created,j.finished,a.name AS account
        FROM jobs j LEFT JOIN accounts a ON a.id=j.account_id
        WHERE (?='admin' OR j.actor_id=? OR a.user_id=? OR (?='reseller' AND a.owner_id=?))
          AND j.state IN ('failed','interrupted','succeeded')
        AND NOT EXISTS(SELECT 1 FROM notification_receipts r WHERE r.user_id=? AND r.job_id=j.id)
        ORDER BY j.id DESC LIMIT 40''', (role,user_id,user_id,role,user_id,user_id))
    return [dict(row) for row in rows]
