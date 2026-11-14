# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import json
import logging
import signal
import time
from backend import core as c

def tick():
    with c.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
        if row is None: return False
        db.execute("UPDATE jobs SET state='running' WHERE id=?",(row['id'],))
    payload=json.loads(row['payload'])
    try:
        result=c.rpc(row['operation'],**payload)
        state='succeeded'
    except Exception as e:
        result={'error':str(e)};state='failed'
    with c.connect() as db:
        db.execute('UPDATE jobs SET state=?,result=?,finished=? WHERE id=?',(state,json.dumps(result),int(time.time()),row['id']))
        if row['operation']=='account.create':
            db.execute('UPDATE accounts SET state=? WHERE id=?',('active' if state=='succeeded' else 'failed',row['account_id']))
            if state=='succeeded':
                db.execute('UPDATE users SET enabled=1 WHERE id=(SELECT user_id FROM accounts WHERE id=?)',(row['account_id'],))
        elif row['operation']=='account.state' and state=='succeeded':
            db.execute('UPDATE accounts SET state=? WHERE id=?',(payload['state'],row['account_id']))
            db.execute('UPDATE users SET enabled=? WHERE id=(SELECT user_id FROM accounts WHERE id=?)',(payload['state']=='active',row['account_id']))
            db.execute('DELETE FROM sessions WHERE user_id=(SELECT user_id FROM accounts WHERE id=?)',(row['account_id'],))
        elif row['operation']=='domain.create':
            db.execute('UPDATE domains SET state=? WHERE name=?',('active' if state=='succeeded' else 'failed',payload['domain']))
        c.audit(db,row['actor_id'],row['operation']+'.'+state,row['account_id'],'worker')
    return True

def main():
    logging.basicConfig(level=logging.INFO)
    # Never blindly replay non-idempotent operations after an unexpected crash.
    with c.connect() as db:
        db.execute("UPDATE jobs SET state='interrupted',result=? WHERE state='running'",(json.dumps({'error':'Worker restarted. Reconcile agent registry before recovery.'}),))
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        try:
            if not tick(): time.sleep(2)
        except Exception:
            logging.exception('Worker error');time.sleep(5)

if __name__=='__main__': main()
