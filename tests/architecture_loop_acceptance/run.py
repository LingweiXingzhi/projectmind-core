"""One-command D evidence collection; incomplete checks exit 2, failures exit 1.

Product T01–T28 are distinct from D fixtures, B service tests and participant
observations. This collector never upgrades those components to whole-story PASS.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit

from extensions.continuity.store import Store
from extensions.continuity.fix_tasks import FixTaskService
from extensions.continuity.fix_gateway import FixTaskGateway
from extensions.handoff.architecture import (ArchitectureError, build_version_handoff,
    inspect_version_handoff, render_version_handoff, source_locator)
from tests.architecture_loop_acceptance.fixture import create, commit, git, GOOD
from tests.architecture_loop_acceptance.fixture_http import make_handler

SCENARIOS = [
 '已有项目说明与真实 AI 初图','功能职责图而非文件树','自然语言纠正与直接编辑',
 '关系编辑','期望过程步骤与分支编辑','持久化刷新重开','两客户端草稿冲突',
 '候选接受/修改/拒绝','未批准不能发布','批准产生不可变版本','历史读取与恢复草稿',
 '代码/图/图来源版本分离','完整 SHA 证据跳转','真实变化触发增量复核',
 '有观察证据的过程偏差','不足证据为 UNKNOWN','修正认知产生新图',
 '实施任务交给接收者','真实修正提交回挂再验证','第二 clone 同版交接',
 '同名异仓/过期审阅/改包拒绝','AI 未配置/失败诚实降级','真实 AI 与证据验证',
 'ProjectMind 新职责候选图覆盖','旧 Explorer/提案只读/CA/交接回归',
 '中断重试版本不丢不重复','无代码设计图全流程','规划关联代码保留实现差异']


def timestamp():return datetime.now(timezone.utc).isoformat()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def http(base,path,body=None,headers=None):
    req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json','Origin':base,**(headers or {})})
    try:
        with urlopen(req,timeout=15) as r:status,raw=r.status,r.read()
    except HTTPError as e:status,raw=e.code,e.read()
    try:result=json.loads(raw)
    except (ValueError,UnicodeError):result={'nonJson':raw[:1000].decode(errors='replace')}
    return {'path':path,'method':'POST' if body is not None else 'GET',
            'body':body,'status':status,'response':result,'at':timestamp()}


def run_d_fixture(output):
    f=create(output/'fixture')
    packet=build_version_handoff(f['versionEnvelope'],workspace_id='workspace-fixture',
        sources={'code':source_locator(f['code']),'architecture':source_locator(f['architecture'])})
    same=inspect_version_handoff(packet,architecture_repo=f['secondArchitecture'],code_repo=f['secondCode'])
    store=Store(output/'fixture-state'/'records.sqlite3')
    service=FixTaskService(store,architecture_repo=f['architecture'],code_repositories=[f['code']])
    v=packet['versionEnvelope']['version']
    # Observe the actual failure BEFORE creating the task, not a guessed trace.
    cmd=[sys.executable,'-B','check_flow.py']
    failed=subprocess.run(cmd,cwd=f['code'],capture_output=True,timeout=15)
    if failed.returncode==0:raise AssertionError('controlled bypass must fail')
    params={'packet':packet,'deviation_id':'deviation-bypass-C','deviation':'Observed B branch bypasses C',
        'expected_process_ref':{'processId':'process-ABC','stepIds':['step-B','step-C']},
        'evidence':[{'kind':'test_observation','codeRevision':v['codeRevision'],'codeRepoId':v['codeRepoId'],
          'detail':failed.stderr.decode(errors='replace'),'exitCode':failed.returncode,'command':cmd}],
        'scope':['flow.py'],'acceptance':'Observe A B C in actual check_flow.py', 'actor':'TEST_ONLY_HTTP'}
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service,None))
    origin='http://127.0.0.1:'+str(server.server_port)
    gateway=FixTaskGateway(service,origin,preview_provider=lambda tid:service.run_fixture_verification(tid,
        command=cmd,fixture_root=f['root'],observation='Actual fixture A B C after fix',
        recheck_ref='C_TEST_DOUBLE: actual C inference NOT_RUN'))
    server.RequestHandlerClass=make_handler(service,gateway)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    calls=[]
    def call(action,payload,auth):
        c=http(origin,'/actions',{'action':action,'payload':payload},auth);calls.append(c)
        if c['status']!=200:raise AssertionError(c)
        return c['response']['result']
    try:
        session=http(origin,'/session',{'actor':params.pop('actor')})['response']['result']
        auth={'Cookie':'d-session='+session['sessionId'],'X-CSRF-Token':session['csrfToken']}
        t=call('create_fix_task',params,auth)
        for state in ('received','in_progress'):
            t=call('transition',{'task_id':t['id'],'expected_revision':t['revision'],
                'expected_map_revision':t['mapRevision'],'status':state,'description':'Actual HTTP '+state},auth)
        git(f['code'],'checkout','-b','fix/fixture-bypass-C')
        (Path(f['code'])/'flow.py').write_text(GOOD)
        repaired=commit(f['code'],'fixture-only implementation fix')
        t=call('submit',{'task_id':t['id'],'expected_revision':t['revision'],
            'expected_map_revision':t['mapRevision'],'revision':repaired,'evidence':'Actual restricted flow.py commit'},auth)
        assert t['status']=='verification_pending' and t['deviationStatus']!='closed'
        preview=call('verification_preview',{'task_id':t['id']},auth)
        assert preview['verification']['exitCode']==0
        t=call('confirm_verification',{'task_id':t['id'],'expected_revision':t['revision'],
            'expected_map_revision':t['mapRevision'],'confirmation_token':preview['confirmationToken'],
            'reason':'TEST_ONLY_SIMULATED_HUMAN confirmed fixture observation'},auth)
        assert t['status']=='verified' and t['verification']['fixtureOnly']
    finally:
        server.shutdown();server.server_close();thread.join()
    # Runtime secrets and one-use confirmations never enter delivered evidence.
    for c in calls:
        c['body']['payload'].pop('confirmation_token',None)
        if isinstance(c.get('response',{}).get('result'),dict):
            c['response']['result'].pop('confirmationToken',None)
    planning=build_version_handoff(f['planningEnvelope'],workspace_id='workspace-planning',
        sources={'code':None,'architecture':source_locator(f['architecture'])})
    plancheck=inspect_version_handoff(planning,architecture_repo=f['secondArchitecture'])
    save(output/'d-http.json',calls)
    save(output/'same-version.json',same)
    save(output/'planning-handoff.json',plancheck)
    save(output/'fix-task.json',t)
    save(output/'handoff.json',packet)
    (output/'handoff.md').write_text(render_version_handoff(packet),encoding='utf-8')
    return {'status':'PASS','scope':'D_ONLY_REAL_GIT_HTTP_TEST_FIXTURE',
        'codeBaseline':f['badRevision'],'submittedRevision':repaired,'mapRevision':v['mapRevision'],
        'mapSourceRevision':f['versionEnvelope']['provenance']['mapSourceRevision'],
        'observedBeforeExitCode':failed.returncode,'observedAfterExitCode':0,
        'secondCloneSameVersion':True,'planningNullSha':True,
        'actualCRecheck':'NOT_RUN_C_TEST_DOUBLE','humanApproval':'TEST_ONLY_SIMULATED_HUMAN',
        'evidence':['d-http.json','same-version.json','planning-handoff.json','fix-task.json']}


def load_ui_evidence(path,head,base):
    ui=json.loads(path.read_text(encoding='utf-8'))
    if ui.get('targetHead')!=head or ui.get('baseUrl')!=base or not ui.get('observer') or not ui.get('observedAt'):
        raise ValueError('UI evidence identity/observer/time mismatch')
    for row in ui.get('checks',[]):
        if row.get('id') not in {f'T{i:02}' for i in range(1,29)} or row.get('status') not in ('PASS','FAIL','NOT_RUN'):
            raise ValueError('invalid UI check')
        if row['status'] in ('PASS','FAIL') and not row.get('evidence'):
            raise ValueError('UI claim needs evidence')
    return {**ui,'trust':'participant_observation_not_independent_audit'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--target-checkout',type=Path)
    p.add_argument('--target-head')
    p.add_argument('--base-url')
    p.add_argument('--run-d-fixture',action='store_true')
    p.add_argument('--ui-evidence',type=Path)
    a=p.parse_args()
    if a.base_url:
        u=urlsplit(a.base_url)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or not u.port \
                or u.username or u.password or u.path or u.query or u.fragment:
            p.error('base-url must be the exact configured loopback origin')
    output=a.output.resolve()
    if output.exists():p.error('output must be a new directory; never overwrite evidence')
    output.mkdir(parents=True)
    checks=[{'id':f'T{i:02}','name':name,'status':'NOT_RUN',
             'detail':'Await exact integrated product and traceable full-story evidence',
             'evidence':[],'componentChecks':[]} for i,name in enumerate(SCENARIOS,1)]
    report={'schemaVersion':'architecture_loop_acceptance_v1','startedAt':timestamp(),
        'collectorHead':git(Path(__file__).resolve().parents[2],'rev-parse','HEAD'),
        'targetHead':a.target_head,'checks':checks,'failures':[],
        'productAcceptance':'NOT_RUN','realAI':'NOT_RUN','crossDevice':'NOT_RUN',
        'audit':'AUDIT_PENDING','humanModelReview':'USER_MODEL_REVIEW_PENDING'}
    exit_code=2
    try:
        if a.run_d_fixture:
            report['dFixture']=run_d_fixture(output)
            for i in (12,18,19,20,21,27):
                checks[i-1]['componentChecks'].append({'status':'PASS','scope':'D_ONLY_TEST_FIXTURE',
                    'detail':'See dFixture; not full A/C/UI acceptance','evidence':report['dFixture']['evidence']})
        if a.target_checkout:
            if not a.target_head or not a.base_url:p.error('target requires --target-head and --base-url')
            actual=git(a.target_checkout,'rev-parse','HEAD');dirty=git(a.target_checkout,'status','--porcelain')
            if actual!=a.target_head or dirty:raise ValueError('target SHA mismatch or dirty worktree')
            requests=[http(a.base_url,'/api/archloop'),http(a.base_url,'/api/ai-status')]
            save(output/'product-http.json',requests)
            report['productHttp']=requests
            if requests[0]['status']==200:
                capabilities=requests[0]['response'].get('adapter',{}).get('registered',{})
                report['registeredBackends']=capabilities
                missing=set(('persistence','correction','handoff'))-set(capabilities)
                if missing:
                    for row in checks:
                        row.update(status='BLOCKED',detail='Product missing registered backends: '+','.join(sorted(missing)),
                                   evidence=['product-http.json'])
                if requests[1]['response'].get('configured') is False:
                    report['realAI']='NOT_RUN_AWAITING_CONFIGURATION'
                    for i in (1,23,27):
                        checks[i-1].update(status='NOT_RUN',detail='Real AI unconfigured; rule/sample is not AI proof')
            else:
                report['failures'].append({'owner':'A','severity':'HIGH','detail':'Architecture service not available',
                                           'evidence':['product-http.json']});exit_code=1
            if git(a.target_checkout,'rev-parse','HEAD')!=actual or git(a.target_checkout,'status','--porcelain'):
                raise ValueError('target changed during collection')
        if a.ui_evidence:
            report['uiObservation']=load_ui_evidence(a.ui_evidence,a.target_head,a.base_url)
            # UI evidence is supplementary; no whole-story status is inferred.
        report['productAcceptance']='FAIL' if report['failures'] else 'INCOMPLETE'
    except Exception as exc:
        report['failures'].append({'owner':'D','severity':'HIGH','detail':type(exc).__name__+': '+str(exc)})
        report['productAcceptance']='FAIL';exit_code=1
    report.update(finishedAt=timestamp(),exitCode=exit_code)
    save(output/'report.json',report)
    save(output/'failures.json',report['failures'])
    print(json.dumps({'report':str(output/'report.json'),'productAcceptance':report['productAcceptance'],
        'dFixture':report.get('dFixture',{}).get('status'),'exitCode':exit_code},ensure_ascii=False))
    return exit_code


if __name__=='__main__':sys.exit(main())
