import base64
import copy
import hashlib
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from pathlib import Path
import test_continuity as fixtures
REMOTE = fixtures.REMOTE
from app import make_handler
from extension_host import ExtensionError
from extensions.continuity_github.extension import handle
from extensions.continuity_github.references import references
from extensions.continuity_github.logs import repository_store as logs
from extensions.continuity_github.store import repository_store as tasks
from extensions.worklog.store import repository_store as original_logs
from extensions.continuity.store import repository_store as original_tasks


class GitHubExperimentTests(unittest.TestCase):
    setUp = fixtures.ContinuityTests.setUp
    tearDown = fixtures.ContinuityTests.tearDown
    git = fixtures.ContinuityTests.git

    def ref(self, suffix):
        return {'url': REMOTE + '/' + suffix, 'reason': '真实工作依据'}

    def save_log(self, **kw):
        data = {'category':'daily','date':'2026-10-06','title':'接口改进','body':'完成实现','author':'Sum1','origin':'human',**kw}
        return handle(self.context, 'POST', {'action':'log_save',**data})['entry']

    def test_links_are_canonical_fixed_and_unverified(self):
        good = [self.ref('issues/42'), self.ref('pull/43'), self.ref('commit/'+self.revision), self.ref('blob/'+self.revision+'/feature.py#L1-L2')]
        good[0]['status'] = 'verified'
        out = references(good + good)
        self.assertEqual(len(out),4)
        self.assertTrue(all(r['status']=='user_link_unverified' for r in out))
        for url in ['https://github.com.evil.test/a/b/issues/1','javascript:alert(1)',REMOTE+'/blob/main/feature.py',REMOTE+'/commit/abc123',REMOTE+'/issues/0',REMOTE+'/issues/1?token=secret',REMOTE+'/blob/'+self.revision+'/%2e%2e/secret','https://git:secret@github.com/a/b/issues/1']:
            with self.subTest(url=url), self.assertRaises(ExtensionError): references([{'url':url}])

    def test_isolated_logs_history_conflicts_and_fixed_handoff(self):
        old = original_logs(self.repo).save({'category':'daily','date':'2026-10-06','title':'原日志','body':'不能改','author':'A'}, self.revision)
        original_tasks(self.repo)
        paths=[original_logs(self.repo).path,original_tasks(self.repo).path]
        before=[p.read_bytes() for p in paths]
        log=self.save_log(references=[self.ref('issues/42')])
        payload={**self.payload,'references':[self.ref('pull/43')],'logIds':[log['id']]}
        r=handle(self.context,'POST',{'action':'create',**payload})['record']
        self.assertEqual(r['logs'][0]['references'][0]['kind'],'issue')
        changed=self.save_log(id=log['id'],expectedVersion=1,body='新正文',references=[self.ref('issues/46')])
        self.assertEqual(logs(self.repo).history(log['id'])[-1]['references'][0]['url'],REMOTE+'/issues/42')
        self.assertEqual(tasks(self.repo).get(r['id'])['logs'][0]['body'],'完成实现')
        with self.assertRaises(ExtensionError) as error: self.save_log(id=log['id'],expectedVersion=1)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(before,[p.read_bytes() for p in paths])
        self.assertEqual(original_logs(self.repo).get(old['id'])['body'],'不能改')
        self.assertNotEqual(logs(self.repo).path,original_logs(self.repo).path)
        index=handle(self.context,'GET',{'action':'reference_index'})['items']
        self.assertTrue(any(x['reference']['kind']=='pr' and x['tasks'] for x in index))

    def test_copy_original_log_is_explicit_and_keeps_source_bytes(self):
        old = original_logs(self.repo).save({'category':'daily','date':'2026-10-06','title':'原工作','body':'保留原文','author':'A'}, self.revision)
        source = original_logs(self.repo).path
        before = source.read_bytes()
        out = handle(self.context,'GET',{'action':'original_logs'})
        self.assertEqual(out['entries'][0]['id'],old['id'])
        copied = handle(self.context,'POST',{'action':'copy_original_log','id':old['id']})['entry']
        self.assertNotEqual(copied['id'],old['id'])
        self.assertEqual(copied['sourceRecord']['version'],1)
        self.save_log(id=copied['id'],expectedVersion=1,body='实验版修改')
        self.assertEqual(before,source.read_bytes())
        self.assertEqual(original_logs(self.repo).get(old['id'])['body'],'保留原文')
        self.assertEqual(logs(self.repo).get(copied['id'])['sourceRecord']['id'],old['id'])

    def test_export_reimport_and_session_retain_references(self):
        r=handle(self.context,'POST',{'action':'create',**self.payload,'references':[self.ref('issues/42')]})['record']
        r=handle(self.context,'POST',{'action':'event','id':r['id'],'expectedVersion':1,'kind':'finish_session','actor':'Tester','note':'实现结束','stopPoint':'实现已保存','nextAction':'检查 PR'})['record']
        out=handle(self.context,'GET',{'action':'export','id':r['id']})
        self.assertIn(REMOTE+'/issues/42',out['markdown'])
        self.assertIn(REMOTE+'/issues/42',out['aiContext'])
        packet=copy.deepcopy(out['packet']);packet['record']['references'][0]['status']='verified'
        imported=handle(self.context,'POST',{'action':'import_packet','packet':packet})['record']
        self.assertEqual(imported['references'][0]['status'],'user_link_unverified')
        self.assertEqual(imported['state'],'receiving')
        self.assertEqual(imported['events'],[])
        self.assertEqual(imported['importedHistory'][-1]['kind'],'finish_session')
        encoded=json.dumps(packet).encode()
        u=handle(self.context,'POST',{'action':'import_start','filename':'job.json','size':len(encoded)})
        for offset in range(0,len(encoded),u['chunkBytes']):
            handle(self.context,'POST',{'action':'import_chunk','uploadId':u['uploadId'],'offset':offset,'base64':base64.b64encode(encoded[offset:offset+u['chunkBytes']]).decode()})
        self.assertEqual(handle(self.context,'POST',{'action':'import_finish','uploadId':u['uploadId']})['record']['references'],imported['references'])

    def test_local_code_requires_repository_identity(self):
        refs=[self.ref('blob/'+self.revision+'/feature.py#L1')]
        result=handle(self.context,'POST',{'action':'verify_references','references':refs})['references'][0]
        self.assertEqual(result['localState'],'code_present');self.assertIn('def feature',result['content'])
        wrong={'url':'https://github.com/other/repo/commit/'+self.revision}
        self.assertEqual(handle(self.context,'POST',{'action':'verify_references','references':[wrong]})['references'][0]['localState'],'repository_unconfirmed')
        missing=self.ref('commit/'+'f'*40)
        self.assertEqual(handle(self.context,'POST',{'action':'verify_references','references':[missing]})['references'][0]['localState'],'missing')

    def test_imported_file_references_and_http_discovery(self):
        raw=b'# MD log'
        u=handle(self.context,'POST',{'action':'log_import_start','category':'daily','date':'2026-10-06','title':'导入','body':'','author':'Tester','filename':'log.md','size':len(raw),'references':[self.ref('issues/42')]})
        handle(self.context,'POST',{'action':'log_import_chunk','uploadId':u['uploadId'],'offset':0,'base64':base64.b64encode(raw).decode()})
        log=handle(self.context,'POST',{'action':'log_import_finish','uploadId':u['uploadId']})['entry']
        self.assertEqual(log['references'][0]['kind'],'issue')
        r=handle(self.context,'POST',{'action':'create',**self.payload,'logIds':[log['id']],'includeAttachments':True})['record']
        imported=handle(self.context,'POST',{'action':'import_packet','packet':handle(self.context,'GET',{'action':'export','id':r['id']})['packet']})['record']
        self.assertEqual(imported['logs'][0]['attachment']['preview'],'# MD log')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.repo,self.map));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            discovery=json.load(urlopen(url+'/api/extensions'))
            self.assertTrue(any(e['id']=='continuity_github' and e['status']=='ready' for e in discovery['extensions']))
            self.assertIn('GitHub 实验版',urlopen(url+'/ext/continuity_github').read().decode())
            self.assertIn('github-references',json.load(urlopen(url+'/api/extensions/continuity_github?action=log_page'))['html'])
            req=Request(url+'/api/extensions/continuity_github',data=json.dumps({'action':'verify_references','references':[self.ref('commit/'+self.revision)]}).encode(),headers={'Content-Type':'application/json'})
            self.assertEqual(json.load(urlopen(req))['references'][0]['localState'],'commit_present')
        finally: server.shutdown();server.server_close();thread.join()
