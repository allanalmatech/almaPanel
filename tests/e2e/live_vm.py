#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Actual HTTPS -> API -> worker -> Linux services acceptance. Never run on production.
No mock adapter. Test credentials are random and never printed. Leaves test resources
on the disposable VM for forensic inspection. Missing services FAIL, never skip.
"""
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import time
import urllib.error
import urllib.request
if os.environ.get('ALMA_DISPOSABLE_VM')!='YES' or os.geteuid()!=0:
    raise SystemExit('Requires root and ALMA_DISPOSABLE_VM=YES on a disposable VM.')
base='https://localhost:8443'
ctx=ssl.create_default_context(cafile='/etc/almapanel/panel.crt')
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),urllib.request.HTTPSHandler(context=ctx))
csrf=''
def call(path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    headers={'Content-Type':'application/json','Origin':base,'X-CSRF-Token':csrf}
    with client.open(urllib.request.Request(base+'/api'+path,data=data,headers=headers),timeout=180) as f:return json.load(f)
def job(body):
    jid=body['job_id']
    for _ in range(75):
        row=next(x for x in call('/jobs') if x['id']==jid)
        if row['state']=='succeeded':return
        if row['state'] in ('failed','interrupted'):raise AssertionError(row)
        time.sleep(2)
    raise AssertionError('Job timed out')
password=secrets.token_urlsafe(32)
call('/setup',{'username':'vmadmin','password':password,'token':Path('/var/lib/almapanel/setup-token').read_text()})
csrf=call('/login',{'username':'vmadmin','password':password})['csrf']
call('/packages',{'name':'VM test','max_domains':2})
pid=call('/packages')[0]['id']
job(call('/accounts',{'username':'vmtenant','password':password,'package_id':pid}))
aid=call('/accounts')[0]['id']
job(call(f'/accounts/{aid}/domains',{'domain':'acceptance.example.com'}))
call(f'/accounts/{aid}/files',{'action':'write','path':'index.php','content':base64.b64encode(b'<?php echo "alma-php-working";').decode()})
req=urllib.request.Request('http://127.0.0.1/',headers={'Host':'acceptance.example.com'})
assert urllib.request.urlopen(req).read()==b'alma-php-working'
subprocess.run(['runuser','-u','ap_vmtenant','--','test','!','-r','/var/lib/almapanel/panel.sqlite3'],check=True)
job(call(f'/accounts/{aid}/state',{'state':'suspended'}))
try:urllib.request.urlopen(req)
except urllib.error.HTTPError as e:assert e.code==503
else:raise AssertionError('Suspended site still reachable')
job(call(f'/accounts/{aid}/state',{'state':'active'}))
assert urllib.request.urlopen(req).read()==b'alma-php-working'
print('Live VM core acceptance passed: TLS, setup, login, package, Linux user, FPM, domain, file upload, PHP, suspension.')

# Website recovery and tenant isolation use all production boundaries.
account_url = f'/accounts/{aid}'
call(account_url + '/files', {'action':'mkdir','path':'next'})
call(account_url + '/files', {'action':'write','path':'next/index.php',
                             'content':base64.b64encode(b'<?php echo "new-root";').decode()})
job(call(account_url + '/domains', {'action':'edit','domain':'acceptance.example.com','root':'next'}))
assert urllib.request.urlopen(req).read()==b'new-root'
snapshot = call(account_url + '/files', {'action':'backup_create'})['name']
call(account_url + '/files', {'action':'backup_restore','path':snapshot,'destination':'restore'})
content = call(account_url + '/files', {'action':'read','path':'restore/next/index.php'})['content']
assert base64.b64decode(content)==b'<?php echo "new-root";'
call(account_url + '/backup-schedule', {'interval_hours':24,'retain':2})
assert call(account_url + '/backup-schedule')['interval_hours']==24
job(call('/accounts', {'username':'vmsecond','password':password,'package_id':pid}))
second = next(account['id'] for account in call('/accounts') if account['name']=='vmsecond')
csrf = call('/login', {'username':'vmsecond','password':password})['csrf']
try:
    call(account_url + '/files')
except urllib.error.HTTPError as e:
    assert e.code==404
else:
    raise AssertionError('A different tenant listed another account’s files.')
csrf = call('/login', {'username':'vmadmin','password':password})['csrf']
for engine in call(account_url + '/databases')['engines']:
    fields = {'action':'create','engine':engine,'label':'probe'+engine}
    first_db = call(account_url + '/databases', fields)
    second_db = call(f'/accounts/{second}/databases', fields)
    assert first_db['database'] != second_db['database']
    if engine == 'mariadb':
        command = ['/usr/bin/mariadb','--no-defaults','--protocol=socket','-u',first_db['username'],first_db['database']]
        env = {**os.environ,'MYSQL_PWD':first_db['password']}
        source = b'CREATE TABLE acceptance(id INT PRIMARY KEY); INSERT INTO acceptance VALUES(17);'
    else:
        command = ['/usr/bin/psql','-X','-w','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-U',first_db['username'],'-d',first_db['database']]
        env = {**os.environ,'PGPASSWORD':first_db['password']}
        source = b'CREATE TABLE acceptance(id INT PRIMARY KEY); INSERT INTO acceptance VALUES(17);'
    subprocess.run(command, input=source, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    exported = call(account_url + '/databases', {'action':'export','label':fields['label'],'password':first_db['password']})
    chunk = call(account_url + '/databases', {'action':'download','file':exported['file'],'offset':0})
    assert chunk['content'] and chunk['done']
    call(account_url + '/databases', {'action':'export_delete','file':exported['file']})
print('Live VM hosting checks passed for document roots, website restore, schedules and tenant boundaries.')


if os.environ.get('ALMA_TEST_SFTP') == 'YES':
    import tempfile
    with tempfile.TemporaryDirectory(prefix='alma-sftp-test-') as temp:
        folder = Path(temp)
        private = folder / 'tenant'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(private)], check=True)
        account_endpoint = account_url + '/sftp'
        response = call(account_endpoint, {'action':'add','label':'Disposable VM acceptance',
                                          'public_key':private.with_suffix('.pub').read_text().strip()})
        assert response['message']
        info = call(account_endpoint)
        assert info['available'] and info['listen'] == '127.0.0.1'
        known = folder / 'known_hosts'
        known.write_text(f"[127.0.0.1]:{info['port']} " + Path('/etc/almapanel/sftp/host_ed25519.pub').read_text())
        local = folder / 'probe.txt'
        local.write_text('SFTP upload verification')
        commands = ['/usr/bin/sftp','-b','-','-P',str(info['port']),'-i',str(private),
                    '-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
                    '-o',f'UserKnownHostsFile={known}',info['username'] + '@127.0.0.1']
        transfer = subprocess.run(commands, input=f"pwd\nput {local} probe.txt\n", text=True,
                                  capture_output=True, check=True, timeout=20)
        assert 'Remote working directory: /public_html' in transfer.stdout
        payload = call(account_url + '/files', {'action':'read','path':'probe.txt'})
        assert base64.b64decode(payload['content']) == local.read_bytes()
        outside = subprocess.run(commands, input='ls /etc/passwd\n', text=True,
                                 capture_output=True, timeout=20)
        assert outside.returncode != 0, 'SFTP exposed the host account database'
        fingerprint = info['keys'][0]['fingerprint']
        call(account_endpoint, {'action':'remove','fingerprint':fingerprint})
        revoked = subprocess.run(commands, input='pwd\n', text=True,
                                 capture_output=True, timeout=20)
        assert revoked.returncode != 0, 'The revoked key still authenticated'
    print('Live VM SFTP acceptance passed for login, upload, chroot and key revocation.')
