# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Persisted, account-scoped schedules for website snapshots."""
import json
import time

from backend import core as c


def setup_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS backup_schedules (
        account_id INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
        interval_hours INTEGER NOT NULL CHECK(interval_hours IN (24,168)),
        retain INTEGER NOT NULL CHECK(retain BETWEEN 1 AND 10),
        next_run INTEGER NOT NULL
    )""")
    cron_table(db)


def settings(db, user, account, method, body, ip):
    account_id = account['id']
    if method == 'GET':
        row = db.execute('SELECT interval_hours,retain,next_run FROM backup_schedules WHERE account_id=?',
                         (account_id,)).fetchone()
        return dict(row) if row else {'interval_hours': 0, 'retain': 3, 'next_run': None}
    interval, retain = body.get('interval_hours'), body.get('retain')
    if type(interval) is not int or interval not in (0, 24, 168) or type(retain) is not int or not 1 <= retain <= 10:
        raise c.Problem('Choose off, daily or weekly, and retain 1–10 scheduled snapshots.')
    if interval:
        db.execute("""INSERT INTO backup_schedules VALUES(?,?,?,?)
            ON CONFLICT(account_id) DO UPDATE SET interval_hours=excluded.interval_hours,
            retain=excluded.retain,next_run=excluded.next_run""",
            (account_id, interval, retain, int(time.time()) + interval * 3600))
    else:
        db.execute('DELETE FROM backup_schedules WHERE account_id=?', (account_id,))
    c.audit(db, user['id'], 'backup.schedule', account_id, ip)
    return {'message': 'Website backup schedule saved.'}


def queue_due(now):
    with c.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        schedules = db.execute("""SELECT s.*,a.name,a.user_id FROM backup_schedules s
            JOIN accounts a ON a.id=s.account_id WHERE a.state='active' AND s.next_run<=?
            AND NOT EXISTS(SELECT 1 FROM jobs WHERE account_id=a.id AND state IN ('queued','running'))
            ORDER BY s.next_run LIMIT 10""", (now,)).fetchall()
        for schedule in schedules:
            payload = {'name': schedule['name'], 'retain': schedule['retain']}
            db.execute("""INSERT INTO jobs(actor_id,account_id,operation,payload,created)
                VALUES(?,?,'backup.scheduled',?,?)""",
                (schedule['user_id'], schedule['account_id'], json.dumps(payload), now))
            db.execute('UPDATE backup_schedules SET next_run=? WHERE account_id=?',
                       (now + schedule['interval_hours'] * 3600, schedule['account_id']))
            c.audit(db, schedule['user_id'], 'backup.scheduled.queued', schedule['account_id'], 'worker')
        queue_php(db, now)
    return len(schedules)


def cron_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS php_schedules (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        actor_id INTEGER NOT NULL REFERENCES users(id),
        path TEXT NOT NULL,
        interval_minutes INTEGER NOT NULL CHECK(interval_minutes IN (15,30,60,360,1440)),
        next_run INTEGER NOT NULL,
        UNIQUE(account_id,path)
    )""")


def php_jobs(db, user, account, method, body, ip):
    account_id = account['id']
    if method == 'GET':
        return [dict(row) for row in db.execute(
            'SELECT id,path,interval_minutes,next_run FROM php_schedules WHERE account_id=? ORDER BY id',
            (account_id,))]
    action = body.get('action')
    if action == 'delete':
        item = body.get('id')
        if type(item) is not int:
            raise c.Problem('Choose a cron job.')
        if not db.execute('DELETE FROM php_schedules WHERE id=? AND account_id=?',
                          (item, account_id)).rowcount:
            raise c.Problem('Cron job not found.', 404)
        c.audit(db, user['id'], 'cron.delete', item, ip)
        return {'message': 'Scheduled PHP job removed.'}
    interval = body.get('interval_minutes')
    if action != 'save' or type(interval) is not int or interval not in (15, 30, 60, 360, 1440):
        raise c.Problem('Choose a supported PHP job interval.')
    path = c.rpc('cron.validate', name=account['name'], path=body.get('path'))['path']
    db.execute('BEGIN IMMEDIATE')
    if db.execute('SELECT count(*) FROM php_schedules WHERE account_id=?', (account_id,)).fetchone()[0] >= 10:
        raise c.Problem('An account can schedule up to 10 PHP jobs.', 409)
    db.execute('INSERT INTO php_schedules(account_id,actor_id,path,interval_minutes,next_run) VALUES(?,?,?,?,?)',
               (account_id, user['id'], path, interval, int(time.time()) + interval * 60))
    c.audit(db, user['id'], 'cron.save', account_id, ip)
    return {'message': 'PHP job scheduled.'}


def queue_php(db, now):
    due = db.execute("""SELECT s.*,a.name FROM php_schedules s JOIN accounts a ON a.id=s.account_id
        JOIN users u ON u.id=s.actor_id
        WHERE a.state='active' AND u.enabled=1 AND s.next_run<=?
        AND NOT EXISTS(SELECT 1 FROM jobs WHERE account_id=a.id AND state IN ('queued','running'))
        AND (u.role='admin' OR u.id=a.user_id OR (u.role='reseller' AND a.owner_id=u.id))
        ORDER BY s.next_run LIMIT 10""", (now,)).fetchall()
    for item in due:
        if db.execute("SELECT 1 FROM jobs WHERE account_id=? AND state IN ('queued','running')",
                      (item['account_id'],)).fetchone():
            continue
        payload = json.dumps({'name': item['name'], 'path': item['path'], 'schedule_id': item['id']})
        db.execute("""INSERT INTO jobs(actor_id,account_id,operation,payload,created)
            VALUES(?,?,'cron.run',?,?)""", (item['actor_id'], item['account_id'], payload, now))
        db.execute('UPDATE php_schedules SET next_run=? WHERE id=?',
                   (now + item['interval_minutes'] * 60, item['id']))
        c.audit(db, item['actor_id'], 'cron.queued', item['id'], 'worker')
