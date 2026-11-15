# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import base64
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from backend import core as c
from backend.app import application
from agent.files import operate
from agent import server as agent
from agent.server import vhost,php_pool,configs
from worker.main import tick

class API(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=c.STATE;c.STATE=Path(self.temp.name)
        c.initialize();self.cookie='';self.csrf=''
        self.admin_cookie='';self.admin_csrf=''
    def tearDown(self):
        c.STATE=self.old;self.temp.cleanup()
    def request(self,path,body=None,cookie=None,csrf=None,origin=None):
        raw=json.dumps(body).encode() if body is not None else b''
        e={'PATH_INFO':path.split('?')[0],'QUERY_STRING':path.partition('?')[2],
           'REQUEST_METHOD':'POST' if body is not None else 'GET','CONTENT_LENGTH':str(len(raw)),
           'CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(raw),'REMOTE_ADDR':'203.0.113.7',
           'HTTP_COOKIE':self.cookie if cookie is None else cookie,'HTTP_X_CSRF_TOKEN':self.csrf if csrf is None else csrf}
        if origin:e['HTTP_ORIGIN']=origin
        result={}
        def start(status,headers):result.update(status=int(status[:3]),headers=dict(headers))
        data=b''.join(application(e,start))
        result['body']=json.loads(data) if result['headers']['Content-Type']=='application/json' else data.decode()
        return result
    def setup_admin(self):
        result=self.request('/api/setup',{'username':'admin','password':'correct horse battery','token':(c.STATE/'setup-token').read_text()})
        self.assertEqual(result['status'],200,result)
        self.login('admin')
        self.admin_cookie,self.admin_csrf=self.cookie,self.csrf
    def login(self,username):
        result=self.request('/api/login',{'username':username,'password':'correct horse battery'})
        self.assertEqual(result['status'],200,result)
        self.cookie=result['headers']['Set-Cookie'].split(';')[0];self.csrf=result['body']['csrf']
    def package(self):
        self.assertEqual(self.request('/api/packages',{'name':'Small','max_domains':2})['status'],200)
        return self.request('/api/packages')['body'][0]['id']
    def seed_account(self,username,owner,package):
        with c.connect() as db:
            uid=db.execute("INSERT INTO users(username,password,role,owner_id,created) VALUES(?,?,'user',?,?)",(username,c.password_hash('correct horse battery'),owner,int(time.time()))).lastrowid
            return db.execute("INSERT INTO accounts(user_id,name,owner_id,package_id,state,created) VALUES(?,?,?,?,'active',?)",(uid,username,owner,package,int(time.time()))).lastrowid
    def test_setup_one_time(self):
        self.setup_admin()
        self.assertFalse((c.STATE/'setup-token').exists())
        self.assertEqual(self.request('/api/setup',{'username':'other','password':'correct horse battery','token':'bad'})['status'],409)
    def test_wrong_setup_token(self):
        self.assertEqual(self.request('/api/setup',{'username':'admin','password':'correct horse battery','token':'wrong'})['status'],403)
    def test_auth_and_cookie_security(self):
        self.assertEqual(self.request('/api/accounts')['status'],401)
        self.setup_admin()
        r=self.request('/api/login',{'username':'admin','password':'correct horse battery'})
        for flag in ['HttpOnly','Secure','SameSite=Strict']:self.assertIn(flag,r['headers']['Set-Cookie'])
        self.assertEqual(self.request('/api/me')['body']['role'],'admin')
    def test_csrf(self):
        self.setup_admin()
        self.assertEqual(self.request('/api/packages',{'name':'Bad','max_domains':1},csrf='wrong')['status'],403)
    def test_origin(self):
        with patch.dict(os.environ,{'ALMA_ORIGIN':'https://localhost:8443'}):
            self.assertEqual(self.request('/api/login',{'username':'admin'},origin='https://evil.test')['status'],403)
    def test_rate_limit(self):
        for _ in range(10):self.request('/api/login',{'username':'admin','password':'bad'})
        self.assertEqual(self.request('/api/login',{'username':'admin','password':'bad'})['status'],429)
    def test_logout_revokes_session(self):
        self.setup_admin();self.request('/api/logout',{})
        self.assertEqual(self.request('/api/me')['status'],401)
    def test_password_revokes_sessions(self):
        self.setup_admin()
        self.assertEqual(self.request('/api/password',{'current':'correct horse battery','password':'new secure password here'})['status'],200)
        self.assertEqual(self.request('/api/me')['status'],401)
    def test_expired_session(self):
        self.setup_admin()
        with c.connect() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.request('/api/me')['status'],401)
    def test_tenant_scope_and_admin_only_routes(self):
        self.setup_admin();p=self.package();a=self.seed_account('alice',1,p);b=self.seed_account('bobby',1,p)
        self.login('alice')
        self.assertEqual([x['id'] for x in self.request('/api/accounts')['body']],[a])
        for suffix in ['stats','files','domains']:
            self.assertEqual(self.request(f'/api/accounts/{b}/{suffix}')['status'],404)
        self.assertEqual(self.request(f'/api/accounts/{b}/files',
                                      {'action': 'upload_start', 'path': 'new.png', 'size': 1})['status'], 404)
        self.assertEqual(self.request('/api/audit')['status'],403)
        self.assertEqual(self.request('/api/system')['status'],403)
        self.assertEqual(self.request('/api/accounts',{})['status'],403)
    def test_account_provisioning_queues_not_fake_success(self):
        self.setup_admin();p=self.package()
        r=self.request('/api/accounts',{'username':'alice','password':'correct horse battery','package_id':p})
        self.assertEqual(r['body']['state'],'queued')
        self.assertEqual(self.request('/api/accounts')['body'][0]['state'],'provisioning')
        with c.connect() as db:self.assertEqual(db.execute("SELECT enabled FROM users WHERE username='alice'").fetchone()[0],0)
        with patch('backend.core.rpc',side_effect=c.Problem('Agent unavailable')):self.assertTrue(tick())
        self.assertEqual(self.request('/api/accounts')['body'][0]['state'],'failed')
        self.assertEqual(self.request('/api/jobs')['body'][0]['state'],'failed')
    def test_worker_success_updates_account(self):
        self.setup_admin();p=self.package()
        self.request('/api/accounts',{'username':'alice','password':'correct horse battery','package_id':p})
        with patch('backend.core.rpc',return_value={'message':'test adapter'}):self.assertTrue(tick())
        self.assertEqual(self.request('/api/accounts')['body'][0]['state'],'active')
        self.assertFalse(tick())
    def test_retry_failed_account_preserves_identity_and_queues_once(self):
        self.setup_admin()
        package = self.package()
        self.request('/api/accounts', {'username': 'alice', 'password': 'correct horse battery', 'package_id': package})
        with patch('backend.core.rpc', side_effect=c.Problem('Agent unavailable')):
            self.assertTrue(tick())
        failed = self.request('/api/accounts')['body'][0]
        path = f"/api/accounts/{failed['id']}/retry-create"
        self.assertTrue(failed['can_retry'])
        self.assertEqual(self.request(path, {}, csrf='wrong')['status'], 403)
        self.assertEqual(self.request(path, {})['body']['state'], 'queued')
        self.assertEqual(self.request(path, {})['status'], 409)
        with patch('backend.core.rpc', return_value={'message': 'test adapter'}) as rpc:
            self.assertTrue(tick())
            rpc.assert_called_once_with('account.create', name='alice', retry=True)
        active = self.request('/api/accounts')['body'][0]
        self.assertEqual((active['state'], active['id'], active['user_id'], active['can_retry']),
                         ('active', failed['id'], failed['user_id'], 0))
        self.assertEqual(self.request(path, {})['status'], 409)
        self.login('alice')
        self.assertEqual(self.request(path, {})['status'], 403)
    def test_domain_count_enforced(self):
        self.setup_admin();p=self.package();a=self.seed_account('alice',1,p)
        for host in ['one.example.com','two.example.com']:
            self.assertEqual(self.request(f'/api/accounts/{a}/domains',{'domain':host})['status'],200)
        self.assertEqual(self.request(f'/api/accounts/{a}/domains',{'domain':'three.example.com'})['status'],409)
    def test_duplicate_domains_and_injection(self):
        self.setup_admin();p=self.package();a=self.seed_account('alice',1,p)
        for bad in ['x; id','example.com\ninclude /etc/passwd;','../example.com','a b.com']:
            self.assertEqual(self.request(f'/api/accounts/{a}/domains',{'domain':bad})['status'],400)
        self.request(f'/api/accounts/{a}/domains',{'domain':'example.com'})
        self.assertEqual(self.request(f'/api/accounts/{a}/domains',{'domain':'example.com'})['status'],409)
    def test_reseller_allocation_and_scope(self):
        self.setup_admin();p=self.package()
        self.assertEqual(self.request('/api/resellers',{'username':'resell','password':'correct horse battery','max_accounts':1})['status'],200)
        self.seed_account('other',1,p)
        self.login('resell')
        self.assertEqual(self.request('/api/accounts')['body'],[])
        self.assertEqual(self.request('/api/accounts',{'username':'alice','password':'correct horse battery','package_id':p})['status'],200)
        self.assertEqual(self.request('/api/accounts',{'username':'bobby','password':'correct horse battery','package_id':p})['status'],409)
    def test_suspended_user_cannot_sign_in(self):
        self.setup_admin();p=self.package();a=self.seed_account('alice',1,p)
        self.request(f'/api/accounts/{a}/state',{'state':'suspended'})
        with patch('backend.core.rpc',return_value={'message':'test adapter'}):tick()
        self.assertEqual(self.request('/api/login',{'username':'alice','password':'correct horse battery'})['status'],401)
    def test_no_static_traversal(self):
        for p in ['/../LICENSE','/backend/app.py','/.env','/frontend/../LICENSE']:
            self.assertEqual(self.request(p)['status'],404)
    def test_security_headers(self):
        r=self.request('/')
        self.assertEqual(r['status'],200)
        self.assertIn("frame-ancestors 'none'",r['headers']['Content-Security-Policy'])
    def test_invalid_json_object(self):
        self.assertEqual(self.request('/api/login',[])['status'],400)

class Files(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
    def tearDown(self):os.close(self.fd);self.temp.cleanup()
    def op(self,action,path='',**kw):return operate(self.fd,{'action':action,'path':path,**kw})
    def write(self,path,data=b'hello'):return self.op('write',path,content=base64.b64encode(data).decode())
    def test_full_file_lifecycle(self):
        self.op('mkdir','folder');self.write('folder/hello.txt')
        self.assertEqual(self.op('list','folder')[0]['name'],'hello.txt')
        self.assertEqual(base64.b64decode(self.op('read','folder/hello.txt')['content']),b'hello')
        self.op('rename','folder/hello.txt',destination='folder/moved.txt')
        self.op('delete','folder/moved.txt');self.op('delete','folder');self.assertEqual(self.op('list'),[])
    def test_permissions_and_link_rejection(self):
        self.write('file')
        self.op('chmod', 'file', mode='600')
        self.assertEqual((self.root/'file').stat().st_mode & 0o777, 0o600)
        self.op('chmod', 'file', mode='000')
        self.op('chmod', 'file', mode='664')
        self.assertEqual((self.root/'file').stat().st_mode & 0o777, 0o664)
        with self.assertRaises(ValueError):
            self.op('chmod', 'file', mode='4777')
        (self.root/'link').symlink_to(self.root/'file')
        with self.assertRaises(ValueError):
            self.op('chmod', 'link', mode='644')
        os.link(self.root/'file', self.root/'hardlink')
        with self.assertRaises(ValueError):
            self.op('chmod', 'hardlink', mode='644')

    def test_atomic_overwrite(self):
        self.write('a');self.write('a',b'updated');self.assertEqual((self.root/'a').read_bytes(),b'updated')
    def test_traversal(self):
        for p in ['../secret','/etc/passwd','a/../../secret','./x','a/../x']:
            with self.assertRaises((ValueError,OSError)):self.op('read',p)
    def test_symlink_escape(self):
        (self.root/'escape').symlink_to('/etc')
        for action in ['list','read','write']:
            with self.assertRaises((ValueError,OSError)):self.op(action,'escape/passwd',content='')
    def test_leaf_symlink(self):
        (self.root/'link').symlink_to('/etc/passwd')
        with self.assertRaises((ValueError,OSError)):self.op('read','link')
        with self.assertRaises((ValueError,OSError)):self.write('link')
    def test_hardlink_rejected(self):
        self.write('a');os.link(self.root/'a',self.root/'b')
        with self.assertRaises(ValueError):self.op('read','b')
        with self.assertRaises(ValueError):self.write('b')
    def test_fifo_rejected_without_block(self):
        os.mkfifo(self.root/'pipe')
        with self.assertRaises(ValueError):self.op('read','pipe')
    def test_size_limit(self):
        with self.assertRaises(ValueError):self.write('large',b'x'*1048577)
    def test_rename_no_overwrite(self):
        self.write('a');self.write('b')
        with self.assertRaises(OSError):self.op('rename','a',destination='b')
    def test_nonempty_folder_not_recursively_deleted(self):
        self.op('mkdir','folder');self.write('folder/a')
        with self.assertRaises(OSError):self.op('delete','folder')

class Provisioning(unittest.TestCase):
    def test_broker_sends_structured_failure_after_dispatch_error(self):
        client, broker = socket.socketpair()
        with client, broker, patch('agent.server.pwd.getpwnam', return_value=SimpleNamespace(pw_uid=os.getuid())), \
                patch('agent.server.dispatch', side_effect=subprocess.CalledProcessError(1, '/usr/sbin/useradd')), \
                self.assertLogs(level='ERROR'):
            client.sendall(b'{"operation":"account.create","args":{"name":"sample"}}\n')
            agent.Handler(broker, '', None)
            with client.makefile('rb') as reader:
                reply = json.loads(reader.readline())
        self.assertFalse(reply['ok'])
        self.assertIn('System operation failed', reply['error'])

    def test_retry_refuses_partial_linux_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'sample').mkdir()
            state = {'sample': {'state': 'failed', 'domains': []}}
            with patch.multiple(agent, BASE=base, PHP_POOL=base, PHP_RUN=temp), \
                    patch('agent.server.registry', return_value=state), \
                    patch('agent.server.pwd.getpwnam', side_effect=KeyError), \
                    patch('agent.server.grp.getgrnam', side_effect=KeyError), patch('agent.server.run') as run:
                with self.assertRaisesRegex(ValueError, 'home or PHP pool already exists'):
                    agent.account_create('sample', retry=True)
                run.assert_not_called()

    def test_retry_clean_account_sets_home_mode_under_service_umask(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            state = {'sample': {'state': 'failed', 'domains': []}}
            user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            with patch.multiple(agent, BASE=base, PHP_POOL=base, PHP_RUN=temp), \
                    patch('agent.server.registry', return_value=state), patch('agent.server.save'), \
                    patch('agent.server.pwd.getpwnam', side_effect=[KeyError, user]), \
                    patch('agent.server.grp.getgrnam', side_effect=KeyError), patch('agent.server.os.chown'), \
                    patch('agent.server.run'), patch('agent.server.configs'), \
                    patch('agent.server.account_files_writable', return_value=True):
                previous_umask = os.umask(0o077)
                try:
                    agent.account_create('sample', retry=True)
                finally:
                    os.umask(previous_umask)
            self.assertEqual((base / 'sample').stat().st_mode & 0o777, 0o750)
            self.assertTrue((base / 'sample' / 'public_html').is_dir())
            self.assertEqual(state['sample']['state'], 'active')


class Validation(unittest.TestCase):
    def test_account_name_injection(self):
        for value in ['root','ap_name','a;id','../foo','a\nb',None]:
            if value=='root':continue  # Prefix ap_ prevents root collision.
            with self.assertRaises(c.Problem):c.name(value)
    def test_password_hash(self):
        a=c.password_hash('a sufficiently long password');b=c.password_hash('a sufficiently long password')
        self.assertNotEqual(a,b);self.assertTrue(c.password_ok('a sufficiently long password',a));self.assertFalse(c.password_ok('wrong',a))
    def test_template_validation(self):
        with self.assertRaises(c.Problem):vhost('alice','x;return 200;')
        self.assertIn('ap_alice',php_pool('alice'))
        self.assertIn('return 503',vhost('alice','example.com',True))
    def test_configuration_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config';path.write_text('original')
            with patch('agent.server.run',side_effect=[RuntimeError('validation rejected'),'', '']):
                with self.assertRaises(RuntimeError):configs({path:'invalid'},'nginx',['nginx','-t'])
            self.assertEqual(path.read_text(),'original')
    def test_new_configuration_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'new'
            with patch('agent.server.run',side_effect=[RuntimeError('bad'),'', '']):
                with self.assertRaises(RuntimeError):configs({path:'invalid'},'nginx',['nginx','-t'])
            self.assertFalse(path.exists())

if __name__=='__main__':unittest.main()
