import copy
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import test_continuity as fixtures
from app import make_handler
from extension_host import ExtensionError
from extensions.worklog.store import repository_store as logs
from extensions.continuity.store import repository_store as tasks
from extensions.continuity.extension import handle as continuity
from extensions.team_footprints.activity import collect_activity, summarize
from extensions.team_footprints.extension import handle


class FootprintTests(unittest.TestCase):
    setUp=fixtures.ContinuityTests.setUp
    tearDown=fixtures.ContinuityTests.tearDown
    git=fixtures.ContinuityTests.git

    def log(self,at='2026-10-05T23:30:00+00:00',**kw):
        data={'category':'daily','date':'2020-01-01','title':'真实日志','body':'完成接口','author':'Sum1',**kw}
        with patch('extensions.worklog.store.now',return_value=at): return logs(self.repo).save(data,self.revision)

    def create(self):
        with patch('extensions.continuity.store.now',return_value='2026-10-06T00:00:00+00:00'):
            return continuity(self.context,'POST',{'action':'create',**self.payload})['record']

    def event(self,r,kind,note='',**kw):
        with patch('extensions.continuity.store.now',return_value='2026-10-06T01:00:00+00:00'):
            return continuity(self.context,'POST',{'action':'event','id':r['id'],'expectedVersion':r['version'],'actor':'Sum1','kind':kind,'note':note,**kw})['record']

    def test_empty_read_does_not_create_stores(self):
        root=self.repo/'.git'
        result=handle(self.context,'GET',{'year':'2026'})
        self.assertEqual(result['total'],0);self.assertEqual(result['members'],[])
        self.assertTrue(all(not c['available'] for c in result['coverage']))
        self.assertFalse((root/'projectmind-worklog').exists())
        self.assertFalse((root/'projectmind-continuity').exists())
        self.assertEqual(len(result['days']),365)

    def test_meaningful_edits_daily_cap_and_actual_time(self):
        log=self.log()
        log=self.log(id=log['id'],expectedVersion=1)
        log=self.log(id=log['id'],expectedVersion=2,body='增加验证结果')
        before=logs(self.repo).path.read_bytes()
        dataset=collect_activity(self.repo)
        result=summarize(dataset,2026)
        day=handle(self.context,'GET',{'action':'day','year':'2026','date':'2026-10-06'})['day']
        self.assertEqual(result['metrics']['log'],1)
        self.assertEqual(len(day['events']),2)
        self.assertEqual(sum(e['counted'] for e in day['events']),1)
        self.assertEqual(before,logs(self.repo).path.read_bytes())
        utc=summarize(collect_activity(self.repo,'UTC'),2026)
        self.assertEqual(next(d for d in utc['days'] if d['date']=='2026-10-05')['count'],1)
        self.assertEqual(summarize(dataset,2020)['total'],0)  # user-filled date is not activity date

    def test_import_history_empty_claim_and_ai_are_not_new_work(self):
        r=self.create();r=self.event(r,'claim')
        r=self.event(r,'note','实际工作已推进')
        packet=continuity(self.context,'GET',{'action':'export','id':r['id']})['packet']
        continuity(self.context,'POST',{'action':'import_packet','packet':copy.deepcopy(packet)})
        continuity(self.context,'POST',{'action':'import_packet','packet':copy.deepcopy(packet)})
        self.log(origin='ai',author='Assistant')
        normal=handle(self.context,'GET',{'year':'2026'})
        self.assertEqual(normal['metrics']['checkpoint'],1)
        self.assertEqual(normal['metrics']['progress'],1)
        self.assertEqual(normal['metrics']['log'],0)
        self.assertEqual(normal['total'],2)
        with_ai=handle(self.context,'GET',{'year':'2026','includeAi':'true'})
        self.assertEqual(with_ai['metrics']['log'],1)
        self.assertTrue(any(p['origin']=='ai' for p in normal['members']))
        self.assertTrue(all(not d['events'] for d in normal['days']))

    def test_problem_resolution_session_and_relay(self):
        r=self.create();r=self.event(r,'block','缺少依赖')
        r=self.event(r,'claim','已准备依赖')
        r=self.event(r,'finish_session','今天做到这里',stopPoint='依赖已就绪',nextAction='运行验证')
        result=handle(self.context,'GET',{'year':'2026'})
        self.assertEqual(result['metrics']['problem'],1);self.assertEqual(result['metrics']['resolved'],1)
        self.assertEqual(result['metrics']['session'],1);self.assertEqual(result['metrics']['complete'],0)
        relay=handle(self.context,'GET',{'action':'relay','year':'2026','recordId':r['id'],'source':'continuity'})
        self.assertEqual([e['kind'] for e in relay['events']],['checkpoint','problem','resolved','session'])
        person=next(p for p in result['members'] if p['name']=='Sum1')
        only=handle(self.context,'GET',{'year':'2026','memberId':person['id']})
        self.assertEqual(only['total'],3)
        with self.assertRaises(ExtensionError): handle(self.context,'GET',{'year':'2026','memberId':'fake'})
        with self.assertRaises(ExtensionError): handle(self.context,'POST',{})
        with self.assertRaises(ExtensionError): handle(self.context,'GET',{'timezone':'not/a/zone'})
        self.assertEqual(len(handle(self.context,'GET',{'year':'2024'})['days']),366)

    def test_http_homepage_contract_and_repository_isolation(self):
        self.log()
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.repo,self.map));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            entries=json.load(urlopen(url+'/api/extensions'))['extensions']
            self.assertTrue(any(e['id']=='team_footprints' and e['status']=='ready' for e in entries))
            self.assertIn('日历',urlopen(url+'/ext/team_footprints').read().decode())
            response=json.load(urlopen(url+'/api/extensions/team_footprints?year=2026'))
            self.assertEqual(response['schemaVersion'],1)
            self.assertEqual(response['scope'],'local_available_records')
            self.assertEqual(len(response['trend']),12)
            req=Request(url+'/api/extensions/team_footprints',data=b'{}',headers={'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as error: urlopen(req)
            self.assertEqual(error.exception.code,405)
        finally: server.shutdown();server.server_close();thread.join()
        with tempfile.TemporaryDirectory() as tmp:
            other=Path(tmp);subprocess.run(['git','init','-q',str(other)],check=True)
            self.assertEqual(summarize(collect_activity(other),2026)['total'],0)

    def test_timezone_database_gap_is_distinguished_from_a_bad_key(self):
        # R48-06: ZoneInfo raises ZoneInfoNotFoundError both for an unknown key
        # and for an interpreter with no IANA database at all. They need
        # different answers — missing deployment data is not "pick a valid
        # zone", and the message must name the installation step.
        import extensions.team_footprints.activity as activity
        real = activity.ZoneInfo

        def only_utc(key):
            if key == 'UTC':
                return real('UTC')
            raise activity.ZoneInfoNotFoundError(key)

        with patch.object(activity, 'ZoneInfo', only_utc):
            with self.assertRaises(ExtensionError) as bad_key:
                handle(self.context, 'GET', {'year': '2026', 'timezone': 'Not/AZone'})
        self.assertEqual(bad_key.exception.status, 400)
        self.assertIn('有效的 IANA 时区', str(bad_key.exception))

        def nothing(key):
            raise activity.ZoneInfoNotFoundError(key)

        with patch.object(activity, 'ZoneInfo', nothing):
            with self.assertRaises(ExtensionError) as gap:
                handle(self.context, 'GET', {'year': '2026'})
        self.assertEqual(gap.exception.status, 503)
        self.assertIn('tzdata', str(gap.exception))

    def test_inherited_git_environment_cannot_redirect_the_record_lookup(self):
        # R35-D1: the explicit repo argument always wins. A hostile inherited
        # GIT_DIR / GIT_WORK_TREE / GIT_COMMON_DIR naming a DIFFERENT real
        # repository must not redirect the footprint read into that
        # repository's stores (it would read someone else's records, or fail
        # to locate the directory at all).
        self.log()
        with tempfile.TemporaryDirectory() as tmp:
            other=Path(tmp)/'other';other.mkdir()
            subprocess.run(['git','init','-q',str(other)],check=True)
            hostile={'GIT_DIR':str(other/'.git'),'GIT_WORK_TREE':str(other),
                     'GIT_COMMON_DIR':str(other/'.git')}
            with patch.dict(os.environ,hostile):
                result=handle(self.context,'GET',{'year':'2026'})
            self.assertEqual(result['metrics']['log'],1)
            self.assertTrue(any(c['available'] for c in result['coverage']))
            self.assertFalse((other/'.git'/'projectmind-worklog').exists())
            self.assertFalse((other/'.git'/'projectmind-continuity').exists())
