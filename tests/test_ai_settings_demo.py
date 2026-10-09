"""Shared/private API separation, real workers, persistent budget and HTTP guards."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import app
from archloop.ai_settings import AISettings, SettingsError
from archloop import ai_transport as ai

SCHEMA={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
KEY='SYNTHETIC-API-SETTINGS-NOT-A-REAL-KEY'


def config(base='https://api.openai.com/v1', *, mode='shared', limit=50000):
    return {'baseUrl':base,'apiKey':KEY,'model':'fixture-model','protocol':'chat_completions',
            'tokenLimit':limit,'outputLimit':128,'mode':mode}


def current(settings):
    with ai.settings_context(settings):
        return ai.ai_config()


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'private'/'ai.sqlite3';self.settings=AISettings(self.path)

    def save(self,settings=None,**kwargs):
        settings=settings or self.settings
        body=config(**kwargs);body.pop('mode');settings.save(body,current(settings))

    def test_private_file_and_key_never_returned(self):
        self.save()
        result=self.settings.public(current(self.settings),can_edit=True)
        self.assertNotIn(KEY,json.dumps(result));self.assertTrue(result['hasKey'])
        if os.name=='posix':self.assertEqual(self.path.stat().st_mode&0o777,0o600)
        root=Path(self.temp.name)/'git';root.mkdir();(root/'.git').mkdir()
        with self.assertRaises(SettingsError):AISettings(root/'ai.sqlite3')

    def test_saved_config_reloads_and_not_reset_by_save(self):
        self.save();ticket=self.settings.reserve(1500);self.settings.settle(ticket,200)
        self.save();new=AISettings(self.path)
        self.assertEqual(current(new)['key'],KEY);self.assertEqual(new.budget()['chargedTokens'],200)

    def test_url_change_requires_fresh_key_and_rejects_plain_http(self):
        self.save()
        body=config('https://another.invalid/v1');body.pop('mode');body['apiKey']=''
        with self.assertRaises(SettingsError):self.settings.save(body,current(self.settings))
        body=config('http://remote.invalid/v1');body.pop('mode')
        with self.assertRaises(ai.AIError):self.settings.save(body,current(self.settings))

    def test_profiles_are_separate_and_never_inherit_shared_key(self):
        self.save()
        alice=self.settings.profile('account:alice');bob=self.settings.profile('account:bob')
        self.assertFalse(current(alice)['configured'])
        self.save(alice,base='https://alice.invalid/v1')
        self.assertEqual(current(self.settings)['base'],'https://api.openai.com/v1')
        self.assertFalse(current(bob)['configured'])
        self.settings.choose('account:alice','personal')
        self.assertEqual(self.settings.selected('account:alice'),'personal')
        self.assertEqual(self.settings.selected('account:bob'),'shared')
        self.assertEqual(alice.budget()['scope'],'personal_profile')

    def test_server_managed_key_is_not_saved_or_inherited_by_personal(self):
        self.save()
        managed=AISettings(self.path,shared_from_env=True)
        with patch.dict(os.environ,{'PROJECTMIND_AI_API_KEY':'SYNTHETIC-ENV-NOT-A-REAL-KEY','PROJECTMIND_AI_MODEL':'env-fixture'},clear=True):
            value=current(managed)
            self.assertEqual(value['model'],'env-fixture')
            self.assertEqual(value['key'],'SYNTHETIC-ENV-NOT-A-REAL-KEY')
            self.assertNotIn(value['key'],managed._row()['config'])
            self.assertEqual(managed.public(value,can_edit=False)['managedBy'],'server_environment')
            self.assertFalse(current(managed.profile('account:alice'))['configured'])
            body=config();body.pop('mode')
            with self.assertRaises(SettingsError):managed.save(body,value)

    def test_public_personal_provider_allowlist_blocks_internal_and_unknown_urls(self):
        parent=AISettings(Path(self.temp.name)/'public'/'ai.sqlite3',allowed_hosts={'api.openai.com'})
        personal=parent.profile('account:alice')
        for url in ('http://127.0.0.1:8765/v1','https://127.0.0.1/v1','https://unknown.invalid/v1','https://api.openai.com:444/v1'):
            with self.subTest(url=url),self.assertRaises(SettingsError):self.save(personal,base=url)
        self.save(personal)

    def test_concurrent_reservations_cannot_pass_limit(self):
        self.save(limit=1000)
        def reserve(_):
            try:return self.settings.reserve(600)
            except SettingsError:return None
        with ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(reserve,range(8)))
        self.assertEqual(sum(value is not None for value in values),1)
        self.assertEqual(self.settings.budget()['chargedTokens'],600)

    def test_revoked_saved_provider_stops_before_worker_or_reservation(self):
        parent=AISettings(Path(self.temp.name)/'public'/'ai.sqlite3',allowed_hosts={'api.openai.com'})
        self.save(parent.profile('account:alice'))
        revoked=AISettings(parent.path,allowed_hosts=set()).profile('account:alice')
        with ai.settings_context(revoked),patch.object(ai,'_isolated_call') as worker:
            with self.assertRaises(SettingsError):ai.call_model('test',{},'s',SCHEMA)
        worker.assert_not_called();self.assertEqual(revoked.budget()['chargedTokens'],0)
        # Reading the old address remains possible so the owner can fix it.
        self.assertTrue(current(revoked)['configured'])

    def test_unknown_failed_usage_and_restart_keep_reservation(self):
        self.save(limit=1000)
        ticket=self.settings.reserve(600);new=AISettings(self.path)
        with self.assertRaises(SettingsError):new.reserve(500)
        new.settle(ticket,None);new.settle(ticket,1)
        self.assertEqual(new.budget()['chargedTokens'],600)
        self.assertEqual(new.budget()['estimatedTokens'],600)
        body=config(limit=1000);body.pop('mode');body['tokenLimit']=500
        with self.assertRaises(SettingsError):new.save(body,current(new))

    def test_bool_and_invalid_fields_cannot_be_saved(self):
        for name,value in [('tokenLimit',True),('outputLimit',True),('apiKey','bad\nkey'),('model',[])]:
            body=config();body.pop('mode');body[name]=value
            with self.subTest(name=name),self.assertRaises(SettingsError):self.settings.save(body,current(self.settings))


class RuntimeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.settings=AISettings(Path(self.temp.name)/'private'/'ai.sqlite3')
        self.calls=[]
        outer=self
        class Provider(BaseHTTPRequestHandler):
            missing=False
            def log_message(self,*args):pass
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.calls.append({'request':request,'key':self.headers.get('Authorization')})
                body={'choices':[{'message':{'content':'{"ok":true}'}}]}
                if not self.missing:body['usage']={'prompt_tokens':11,'completion_tokens':4,'total_tokens':15}
                raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.provider_type=Provider
        self.provider=ThreadingHTTPServer(('127.0.0.1',0),Provider)
        threading.Thread(target=self.provider.serve_forever,daemon=True).start()
        self.addCleanup(self.provider.server_close);self.addCleanup(self.provider.shutdown)
        self.base=f'http://127.0.0.1:{self.provider.server_port}/v1'
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.make_handler(app.ROOT,None,ai_settings=self.settings))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.port=self.server.server_port;self.cookie='';self.csrf=''
        self.session()

    def request(self,method,path,body=None,*,csrf=True,origin=None,mode=None,cookie=None):
        headers={'Origin':origin or f'http://127.0.0.1:{self.port}','Cookie':self.cookie if cookie is None else cookie}
        if csrf:headers['X-CSRF-Token']=self.csrf
        if mode:headers['X-ProjectMind-AI-Mode']=mode
        raw=json.dumps(body).encode() if body is not None else None
        if raw is not None:headers['Content-Type']='application/json'
        connection=HTTPConnection('127.0.0.1',self.port,timeout=20)
        connection.request(method,path,body=raw,headers=headers);response=connection.getresponse()
        data=json.loads(response.read());status=response.status;reply=dict(response.getheaders());connection.close()
        return status,data,reply

    def session(self,operator=''):
        status,body,headers=self.request('GET','/api/archloop/session?operator='+operator)
        jar=SimpleCookie();jar.load(headers['Set-Cookie']);self.cookie='pm_archloop_session='+jar['pm_archloop_session'].value
        self.csrf=body['csrfToken'];self.assertEqual(status,200)

    def test_save_immediate_test_usage_output_limit_and_blank_key_reload(self):
        status,body,_=self.request('POST','/api/ai-settings',config(self.base))
        self.assertEqual(status,200,body);self.assertNotIn(KEY,json.dumps(body))
        status,body,_=self.request('POST','/api/ai-settings/test',{'mode':'shared'})
        self.assertEqual(status,200,body);self.assertTrue(body['connected'])
        self.assertEqual(body['budget']['chargedTokens'],15)
        self.assertEqual(self.calls[-1]['request']['max_tokens'],128)
        status,body,_=self.request('GET','/api/ai-status')
        self.assertTrue(body['configured']);self.assertEqual(body['model'],'fixture-model')
        status,body,_=self.request('GET','/api/ai-settings');self.assertNotIn(KEY,json.dumps(body))
        self.assertTrue(body['hasKey'])

    def test_no_csrf_and_cross_origin_refused_before_save_or_network(self):
        for options in ({'csrf':False},{'origin':'https://elsewhere.invalid'}):
            status,body,_=self.request('POST','/api/ai-settings',config(self.base),**options)
            self.assertEqual(status,403,body)
        self.assertFalse(current(self.settings)['configured']);self.assertEqual(self.calls,[])

    def test_server_managed_shared_key_cannot_be_edited_or_probed_from_page(self):
        self.settings.shared_from_env=True
        with patch.dict(os.environ,{'PROJECTMIND_AI_API_KEY':KEY,'PROJECTMIND_AI_MODEL':'env-fixture'},clear=True):
            status,body,_=self.request('GET','/api/ai-settings')
            self.assertEqual(status,200,body);self.assertFalse(body['canEdit']);self.assertNotIn(KEY,json.dumps(body))
            for path,value in (('/api/ai-settings',config(self.base)),('/api/ai-settings/test',{})):
                status,body,_=self.request('POST',path,value);self.assertEqual(status,403,body)
            status,body,_=self.request('POST','/api/ai-settings',config(self.base,mode='personal'))
            self.assertEqual(status,200,body);self.assertTrue(body['canEdit'])
        self.assertEqual(self.calls,[])

    def test_server_managed_availability_check_is_real_bounded_and_never_returns_key(self):
        self.settings.shared_from_env=True
        with patch.dict(os.environ,{'PROJECTMIND_AI_API_KEY':KEY,'PROJECTMIND_AI_MODEL':'env-fixture','PROJECTMIND_AI_BASE_URL':self.base},clear=True):
            status,body,_=self.request('POST','/api/ai-settings/check',{'mode':'shared'},csrf=False)
            self.assertEqual(status,403,body)
            status,body,_=self.request('POST','/api/ai-settings/check',{'mode':'shared','baseUrl':self.base})
            self.assertEqual(status,400,body);self.assertEqual(self.calls,[])
            status,body,_=self.request('POST','/api/ai-settings/check',{'mode':'shared'})
            self.assertEqual(status,200,body);self.assertTrue(body['connected'])
            self.assertNotIn(KEY,json.dumps(body));self.assertEqual(len(self.calls),1)
            self.assertEqual(self.calls[0]['request']['max_tokens'],2048)
            self.assertEqual(self.settings.budget()['chargedTokens'],15)
        self.assertEqual(self.settings._row()['config'],'{}','environment key is never persisted')

    def test_personal_mode_does_not_replace_shared_and_survives_operator_session_reissue(self):
        self.request('POST','/api/ai-settings',config(self.base))
        self.request('POST','/api/ai-settings/select',{'mode':'personal'})
        status,body,_=self.request('GET','/api/ai-settings')
        self.assertFalse(body['configured']);self.assertEqual(body['mode'],'personal')
        personal=config(self.base,mode='personal');personal['model']='personal-model'
        status,body,_=self.request('POST','/api/ai-settings',personal);self.assertEqual(status,200,body)
        self.session('different-declared-operator')
        status,body,_=self.request('GET','/api/ai-status')
        self.assertEqual(body['model'],'personal-model')
        status,body,_=self.request('GET','/api/ai-status',mode='shared')
        self.assertEqual(body['model'],'fixture-model')
        self.assertEqual(current(self.settings)['model'],'fixture-model')

    def test_other_browser_does_not_read_personal_profile(self):
        personal=config(self.base,mode='personal');personal['model']='alice-only'
        self.request('POST','/api/ai-settings',personal)
        status,body,_=self.request('GET','/api/ai-settings?mode=personal',cookie='')
        self.assertEqual(status,403,body)
        self.cookie='';self.session()
        status,body,_=self.request('GET','/api/ai-settings?mode=personal')
        self.assertFalse(body['configured']);self.assertNotEqual(body['model'],'alice-only')

    def test_short_budget_stops_before_starting_worker(self):
        self.request('POST','/api/ai-settings',config(self.base,limit=1000))
        status,body,_=self.request('POST','/api/ai-settings/test',{})
        self.assertEqual(status,429,body);self.assertEqual(body['error']['code'],'AI_DEMO_LIMIT')
        self.assertEqual(self.calls,[])

    def test_missing_personal_session_never_falls_back_to_shared(self):
        self.request('POST','/api/ai-settings',config(self.base))
        status,body,_=self.request('GET','/api/ai-status',mode='personal',cookie='')
        self.assertEqual(status,403,body);self.assertNotIn(KEY,json.dumps(body))

    def test_private_storage_failure_is_controlled_and_does_not_fall_back(self):
        import sqlite3
        with patch.object(self.settings,'selected',side_effect=sqlite3.DatabaseError('sensitive-path')):
            status,body,_=self.request('GET','/api/ai-status')
        self.assertEqual(status,503,body);self.assertNotIn('sensitive-path',json.dumps(body));self.assertEqual(self.calls,[])

    def test_missing_usage_is_marked_as_estimated(self):
        self.provider_type.missing=True
        self.request('POST','/api/ai-settings',config(self.base))
        status,body,_=self.request('POST','/api/ai-settings/test',{})
        self.assertEqual(status,200,body);self.assertGreater(body['budget']['estimatedTokens'],0)
        self.assertEqual(body['budget']['reportedTokens'],0)

    def test_responses_output_limit_and_usage(self):
        body=config(self.base);body['protocol']='responses'
        self.request('POST','/api/ai-settings',body)
        configured=current(self.settings)
        request=ai._request_body(configured,'fixture',{},'s',SCHEMA)
        self.assertEqual(request['max_output_tokens'],128)



@unittest.skipUnless(os.name=='posix','Public mode requires POSIX private files')
class PublicModeTests(unittest.TestCase):
    def setUp(self):
        import io
        from deployment.access import PublicAccess,create_account_file,add_account
        from deployment.wsgi import Application
        from archloop.service import WorkbenchService
        from archloop.adapters import AdapterRegistry
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.origin='https://demo.example.invalid'
        self.password='SYNTHETIC-password-for-policy-tests'
        accounts=root/'accounts.json';create_account_file(accounts,'owner',self.password)
        add_account(accounts,'teacher',self.password)
        self.access=PublicAccess(self.origin,accounts)
        self.settings=AISettings(root/'private'/'ai.sqlite3',allowed_hosts={'api.openai.com'})
        service=WorkbenchService(root/'workspaces',AdapterRegistry());service.bind_backend_c()
        handler=app.make_handler(app.ROOT,None,archloop_service=service,public_origin=self.origin,
                                 ai_settings=self.settings,ai_settings_editors=('owner',))
        self.application=Application(handler,self.access,[])
        self.sessions={}
        for actor in ('owner','teacher'):
            sid,session=self.access.login(actor,self.password)
            self.sessions[actor]=(sid,session)

    def request(self,actor,method,path,body=None,*,csrf=True,headers=None):
        import io
        from deployment.access import COOKIE
        sid,session=self.sessions[actor]
        raw=json.dumps(body).encode() if body is not None else b''
        route,_,query=path.partition('?')
        environ={'REQUEST_METHOD':method,'PATH_INFO':route,'QUERY_STRING':query,
                 'REMOTE_ADDR':'127.0.0.1','HTTP_HOST':'demo.example.invalid','HTTP_ORIGIN':self.origin,
                 'HTTP_COOKIE':COOKIE+'='+sid,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),
                 'wsgi.input':io.BytesIO(raw)}
        if csrf:environ['HTTP_X_PROJECTMIND_CSRF']=session.csrf
        if headers:environ.update(headers)
        captured=[]
        def start(status,values):captured.append((int(status.split()[0]),values))
        value=b''.join(self.application(environ,start))
        return captured[0][0],json.loads(value)

    def test_teacher_uses_shared_status_without_key_and_cannot_change_shared(self):
        status,value=self.request('owner','POST','/api/ai-settings',config())
        self.assertEqual(status,200,value)
        status,value=self.request('teacher','GET','/api/ai-settings')
        self.assertEqual(status,200);self.assertTrue(value['configured']);self.assertFalse(value['canEdit'])
        self.assertNotIn('hasKey',value);self.assertNotIn('baseUrl',value);self.assertNotIn(KEY,json.dumps(value))
        body=config();body['actor']='owner'
        status,value=self.request('teacher','POST','/api/ai-settings',body,
                                  headers={'HTTP_X_FORWARDED_USER':'owner','HTTP_X_AI_SETTINGS_EDITOR':'owner'})
        self.assertEqual(status,403,value)
        status,value=self.request('teacher','POST','/api/ai-settings/test',{})
        self.assertEqual(status,403,value)

    def test_account_personal_config_and_budget_are_isolated(self):
        personal=config(mode='personal');personal['model']='teacher-personal'
        status,value=self.request('teacher','POST','/api/ai-settings',personal)
        self.assertEqual(status,200,value);self.assertEqual(value['mode'],'personal')
        status,value=self.request('owner','GET','/api/ai-settings?mode=personal')
        self.assertFalse(value['configured']);self.assertNotEqual(value['model'],'teacher-personal')
        sid,session=self.access.login('teacher',self.password);self.sessions['teacher']=(sid,session)
        status,value=self.request('teacher','GET','/api/ai-settings')
        self.assertEqual(value['model'],'teacher-personal')
        status,value=self.request('teacher','GET','/api/ai-status',headers={'HTTP_X_PROJECTMIND_AI_MODE':'shared'})
        self.assertFalse(value['configured'],'presentation never uses personal key')

    def test_public_csrf_and_provider_registration(self):
        status,value=self.request('owner','POST','/api/ai-settings',config(),csrf=False)
        self.assertEqual(status,403,value)
        for url in ('http://127.0.0.1:8765/v1','https://unregistered.invalid/v1'):
            status,value=self.request('teacher','POST','/api/ai-settings',config(url,mode='personal'))
            self.assertEqual(status,403,value)
        self.assertFalse(current(self.settings)['configured'])

    def test_teacher_can_check_shared_api_without_configuration_permission(self):
        calls=[]
        class Provider(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                raw=json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}],'usage':{'total_tokens':15}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        self.settings.shared_from_env=True
        with patch.dict(os.environ,{'PROJECTMIND_AI_API_KEY':KEY,'PROJECTMIND_AI_MODEL':'env-fixture',
                                    'PROJECTMIND_AI_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1'},clear=True):
            status,value=self.request('teacher','POST','/api/ai-settings/check',{'mode':'shared'},csrf=False)
            self.assertEqual(status,403,value);self.assertEqual(calls,[])
            status,value=self.request('teacher','POST','/api/ai-settings/check',{'mode':'shared'})
            self.assertEqual(status,200,value);self.assertTrue(value['connected']);self.assertNotIn(KEY,json.dumps(value))
            self.assertEqual(len(calls),1);self.assertEqual(self.settings.budget()['chargedTokens'],15)
            status,value=self.request('teacher','POST','/api/ai-settings',config())
            self.assertEqual(status,403,(value,'availability check never grants configuration permission'))

    def test_teacher_generation_uses_shared_configuration_and_real_worker(self):
        from tests.test_archloop_ai_providers import VALID_GRAPH
        calls=[]
        class Provider(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append({'key':self.headers.get('Authorization'),'request':request})
                raw=json.dumps({'choices':[{'message':{'content':json.dumps(VALID_GRAPH)}}],
                                'usage':{'total_tokens':37}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        status,value=self.request('owner','POST','/api/ai-settings',config(f'http://127.0.0.1:{server.server_port}/v1'))
        self.assertEqual(status,200,value)
        status,workspace=self.request('teacher','POST','/api/archloop/workspaces',{'context':'planning','title':'老师无密钥演示','goals':'设计借书工具','constraints':'合成 API 测试'})
        self.assertEqual(status,200,workspace)
        status,generated=self.request('teacher','POST',f"/api/archloop/workspaces/{workspace['workspace']['workspaceId']}/generate",{})
        self.assertEqual(status,200,generated);self.assertEqual(generated['status'],'ai_generated')
        self.assertEqual(calls[-1]['key'],'Bearer '+KEY)
        self.assertEqual(self.settings.budget()['reportedTokens'],37)
        self.assertEqual(generated['model'],'fixture-model')
        self.assertNotIn(KEY,json.dumps(generated))

if __name__=='__main__':unittest.main()
