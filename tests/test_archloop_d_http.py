import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from extensions.continuity.fix_gateway import FixTaskGateway
from tests.architecture_loop_acceptance.fixture_http import make_handler
from tests import test_archloop_d_fix_tasks as fixture_tests


class GatewayHttpTests(fixture_tests.FixTasksTests):
    # Reuse fixture setup, not the parent test methods.
    def setUp(self):
        super().setUp()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service,None))
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        self.gateway=FixTaskGateway(self.service,self.origin)
        self.server.RequestHandlerClass=make_handler(self.service,self.gateway)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.auth=self.request('/session',{'actor':'TEST_ONLY_HTTP'})[1]['result']

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();super().tearDown()

    def request(self,path,body=None,auth=None,extra=None):
        headers={'Origin':self.origin,'Content-Type':'application/json'}
        if auth:headers.update({'Cookie':'d-session='+auth['sessionId'],'X-CSRF-Token':auth['csrfToken']})
        headers.update(extra or {})
        req=Request(self.origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urlopen(req,timeout=5) as r:return r.status,json.load(r)
        except HTTPError as e:return e.code,json.load(e)

    def test_real_http_session_csrf_cross_origin_and_forged_context(self):
        body={'action':'transition','payload':{'task_id':self.task['id'],'expected_revision':1,
            'expected_map_revision':self.task['mapRevision'],'status':'received','description':'actual HTTP receive'}}
        self.assertEqual(self.request('/actions',body)[0],403)
        self.assertEqual(self.request('/actions',body,self.auth,{'Origin':'http://other.invalid'})[0],403)
        forged=json.loads(json.dumps(body));forged['payload']['actor']='forged'
        self.assertEqual(self.request('/actions',forged,self.auth)[0],403)
        status,result=self.request('/actions',body,self.auth)
        self.assertEqual(status,200);self.assertEqual(result['result']['status'],'received')
        self.assertEqual(self.request('/actions',body,self.auth)[1]['code'],'REVISION_CONFLICT')
        status,result=self.request('/tasks?id='+self.task['id'])
        self.assertEqual(status,200);self.assertEqual(result['result']['revision'],2)

    def test_legacy_http_contract_does_not_open_unprotected_new_write(self):
        from types import SimpleNamespace
        from extensions.handoff.extension import handle
        from extension_host import ExtensionError
        info=handle(SimpleNamespace(),'POST',{'action':'archloop_contract_info'})
        self.assertNotIn('contract',info)
        with self.assertRaises(ExtensionError) as err:handle(SimpleNamespace(),'POST',{'action':'create_fix_task'})
        self.assertEqual(int(err.exception.status),403)

    def test_missing_real_provider_does_not_fabricate_verification(self):
        self.start();self.task=self.submit(self.fix())
        code,body=self.request('/actions',{'action':'verification_preview','payload':{'task_id':self.task['id']}},self.auth)
        self.assertEqual(code,503);self.assertEqual(body['code'],'BACKEND_UNAVAILABLE')

    def test_confirmation_is_bound_to_session_task_and_preview(self):
        import sys
        self.start();self.task=self.submit(self.fix())
        self.gateway.preview_provider=lambda task_id:self.service.run_fixture_verification(task_id,
            command=[sys.executable,'-B','check_flow.py'],fixture_root=self.f['root'],
            observation='Actual fixture trace after fix',recheck_ref='C_TEST_DOUBLE; real C NOT_RUN')
        code,body=self.request('/actions',{'action':'verification_preview','payload':{'task_id':self.task['id']}},self.auth)
        self.assertEqual(code,200);token=body['result']['confirmationToken']
        second=self.request('/session',{'actor':'TEST_ONLY_SECOND'})[1]['result']
        payload={'task_id':self.task['id'],'expected_revision':self.task['revision'],
            'expected_map_revision':self.task['mapRevision'],'reason':'TEST_ONLY confirm actual fixture test',
            'confirmation_token':token}
        self.assertEqual(self.request('/actions',{'action':'confirm_verification','payload':payload},second)[0],403)
        code,body=self.request('/actions',{'action':'confirm_verification','payload':payload},self.auth)
        self.assertEqual(code,200);self.assertEqual(body['result']['status'],'verified')
        self.assertTrue(body['result']['verification']['fixtureOnly'])
        self.assertNotEqual(self.request('/actions',{'action':'confirm_verification','payload':payload},self.auth)[0],200)


# Avoid running the inherited fixture tests twice in this HTTP suite.
for name in list(fixture_tests.FixTasksTests.__dict__):
    if name.startswith('test_'):setattr(GatewayHttpTests,name,None)

if __name__=='__main__':unittest.main()
