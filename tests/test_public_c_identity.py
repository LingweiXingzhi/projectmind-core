"""Actual public HTTP C calls, declared trace provenance and honest UNKNOWN."""
import unittest
from unittest.mock import patch

import test_public_deployment as fixtures
from archloop import backend_c


class CIdentityHTTPTests(fixtures.PublicHTTPTests):
    def prepared(self, auth, planning=False):
        path, envelope = self.workspace(auth, planning=planning)
        node = envelope['draft']['graph']['nodes'][0]['id']
        status, _, envelope = self.request('POST', path+'/apply-ops', {
            'expectedDraftRevision':envelope['draft']['draftRevision'],
            'operations':[{'type':'update_process','nodeId':node,'process':[
                {'stepId':step,'title':step,'detail':'Synthetic expected process','inputs':[],
                 'outputs':[],'branches':[],'next':[]} for step in ('a','b')]}]},auth=auth)
        self.assertEqual(status,200,envelope)
        return path,envelope,node

    def test_registry_and_actual_calls_use_the_same_engine(self):
        auth=self.login(); registered=self.request('GET','/api/archloop/backend',auth=auth)[2]['adapter']['registered']
        self.assertEqual(registered['correction'],'extension:map_proposal')
        service=self.application.service; original=service.adapter._backends['correction']['call']; calls=[]
        def invoke(action,payload):calls.append(action);return original(action,payload)
        with patch.dict(service.adapter._backends['correction'],{'call':invoke}):
            path,envelope,node=self.prepared(auth)
            self.assertEqual(self.request('POST',path+'/deviations',{'observedTraces':[]},auth=auth)[0],200)
        self.assertIn('bootstrap_candidate',calls);self.assertIn('deviations_for',calls)

    def test_declared_matching_foreign_and_malformed_traces(self):
        auth=self.login();path,envelope,node=self.prepared(auth); identity=envelope['identity']
        def observe(trace):return self.request('POST',path+'/deviations',{'observedTraces':[trace]},auth=auth)
        trace={'called_steps':['a','b'],'codeRepoId':identity['codeRepoId'],'codeRevision':identity['codeRevision']}
        status,_,result=observe(trace);self.assertEqual(status,200);self.assertEqual(result['verdict'],'ALIGNED')
        self.assertEqual(result['coveredNodes'],[node]);self.assertIn('提供的追踪数据',result['labeled'])
        status,_,result=observe({**trace,'called_steps':['a']});self.assertEqual(status,200)
        self.assertEqual(result['verdict'],'DEVIATION_DETECTED');self.assertTrue(result['deviations'])
        for mismatch in ({'codeRepoId':'foreign'}, {'codeRevision':'f'*40}, {'called_steps':[[]]},
                         {'called_steps':['a']*201}):
            with self.subTest(mismatch=mismatch):
                status,_,result=observe({**trace,**mismatch});self.assertEqual(status,200,result)
                self.assertEqual(result['verdict'],'UNKNOWN');self.assertTrue(result['rejectedTraces'])
                self.assertEqual(result['deviations'],[])
        self.assertEqual(self.request('POST',path+'/deviations',{'observedTraces':[trace]*201},auth=auth)[0],400)

    def test_planning_trace_cannot_claim_runtime_alignment(self):
        auth=self.login();path,_,_=self.prepared(auth,planning=True)
        status,_,result=self.request('POST',path+'/deviations',{'observedTraces':[
            {'called_steps':['a','b'],'codeRepoId':'declared','codeRevision':'a'*40}]},auth=auth)
        self.assertEqual(status,200,result);self.assertEqual(result['verdict'],'UNKNOWN')
        self.assertTrue(result['rejectedTraces']);self.assertEqual(result['coveredNodes'],[])


for _name in fixtures.PublicHTTPTests.__dict__:
    if _name.startswith('test_'):setattr(CIdentityHTTPTests,_name,None)
