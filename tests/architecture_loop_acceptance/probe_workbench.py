"""D-owned public HTTP probes on an explicitly supplied isolated A instance.

Creates test workspaces/drafts only; no formal review is attempted outside a
labeled dev sample. This is not browser evidence or a real AI-generation run.
"""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from extensions.handoff.architecture import code_identity
from tests.architecture_loop_acceptance.run import http, save, timestamp


def probe(base, fixture_code, second_code, output, target_head):
    requests=[]; findings=[]; observations=[]
    def call(path,body=None,headers=None):
        r=http(base,path,body,headers);requests.append(r);return r
    def result(r):
        if r['status']!=200:raise AssertionError(r)
        return r['response']
    # public writes require a live server-side session plus its anti-forgery
    # header (D-A-02); the probe drives that real path, then proves a write
    # without it is refused (below).
    from http.cookies import SimpleCookie
    from archloop.web_session import SESSION_COOKIE as SESSION_COOKIE_NAME
    session_url = base + '/api/archloop/session?operator=TEST_ONLY_D_PROBE_OPERATOR'
    session_request = Request(session_url, headers={'Origin': base})
    with urlopen(session_request, timeout=15) as response:
        session_body = json.loads(response.read())
        raw_cookie = response.headers.get('Set-Cookie') or ''
    jar = SimpleCookie(); jar.load(raw_cookie)
    token = session_body.get('csrfToken')
    cookie = None
    if SESSION_COOKIE_NAME in jar:
        cookie = f"{SESSION_COOKIE_NAME}={jar[SESSION_COOKIE_NAME].value}"
    observations.append({'case':'write_session','status':200,
                         'csrfIssued':bool(token),'cookieIssued':bool(cookie),
                         'httpOnly': 'httponly' in raw_cookie.lower(),
                         'operatorDeclared':True})
    if not token or not cookie:
        findings.append({'id':'D-A-02','owner':'A','severity':'HIGH',
            'detail':'Server did not issue a write session cookie/CSRF token; the public write path cannot be exercised'})
    def auth_headers():
        return {'Cookie':cookie,'X-CSRF-Token':token}
    def write(path,body=None,explicit=None):
        return call(path,body,explicit if explicit is not None else auth_headers())
    status=result(call('/api/archloop'))
    identity_observations=[]
    for repo in [fixture_code,second_code]:
        r=result(write('/api/archloop/workspaces',{'context':'existing_project',
            'title':'D_TEST_ONLY existing','repoPath':str(repo),'description':'Temporary fixture, expected A B C'}))
        entry={'case':'existing_identity','identity':r['identity'],'workspaceId':r['workspace']['workspaceId']}
        identity_observations.append(entry);observations.append(entry)
    first_id,second_id=[x['identity']['codeRepoId'] for x in identity_observations]
    b_id=code_identity(fixture_code)
    if first_id!=second_id or first_id!=b_id:
        findings.append({'id':'D-A-01','owner':'A','severity':'HIGH',
            'detail':'A IDs differ between same-origin clones and differ from B exact origin identity',
            'actual':{'AFirst':first_id,'ASecond':second_id,'B':b_id},
            'expected':'Shared registered repository identity; path differences must not change it'})
    planning=result(write('/api/archloop/workspaces',{'context':'planning','title':'D_TEST_ONLY planning',
        'goals':'Expected A B C','constraints':'No code required','description':'Temporary acceptance fixture'}))
    wid=planning['workspace']['workspaceId']
    observations.append({'case':'planning_null_sha','identity':planning['identity']})
    production=write('/api/archloop/workspaces/'+wid+'/generate',{})
    observations.append({'case':'real_ai_generation','status':production['status'],'response':production['response']})
    sample=result(call('/api/archloop/sample-graph?context=planning'))
    candidate=result(write('/api/archloop/workspaces/'+wid+'/generate',
        {'mode':'dev_sample','sampleGraph':sample['graph']}))
    draft=result(write('/api/archloop/workspaces/'+wid+'/apply-candidate',{'candidateId':candidate['candidateId']}))
    node=draft['draft']['graph']['nodes'][0]
    operation={'type':'update_node','nodeId':node['id'],'fields':{'summary':'D actual public HTTP correction'}}
    edited=write('/api/archloop/workspaces/'+wid+'/apply-ops',
        {'expectedDraftRevision':draft['draft']['draftRevision'],'operations':[operation]})
    reopen=call('/api/archloop/workspaces/'+wid)
    observed_summary = (reopen.get('response',{}).get('draft') or {}).get('graph',{}).get('nodes',[{}])[0].get('summary')
    if edited['status'] != 200 or observed_summary != 'D actual public HTTP correction':
        findings.append({'id':'D-A-04','owner':'A','severity':'HIGH','detail':'Direct edit did not persist after HTTP reopen'})
    observations.append({'case':'public_edit_reopen_component','editStatus':edited['status'],
        'reopenStatus':reopen['status'],'observedSummary':observed_summary,'origin':'dev_sample','notRealAI':True})
    review=write('/api/archloop/workspaces/'+wid+'/review',
        {'expectedMapRevision':reopen['response']['draft']['graph']['mapRevision'],
         'decision':'accept','actor':'TEST_ONLY_SIMULATED_HUMAN','reason':'Sample must not publish'})
    observations.append({'case':'sample_cannot_publish','status':review['status'],'response':review['response']})
    bad_origin=write('/api/archloop/workspaces',{'context':'planning','title':'D blocked cross-site'},
                    {'Origin':'http://other.invalid',**auth_headers()})
    observations.append({'case':'cross_origin_reject','status':bad_origin['status']})
    # No Origin/Cookie/CSRF: a genuine request, not a static code inference.
    req=Request(base+'/api/archloop/workspaces',data=json.dumps(
        {'context':'planning','title':'D_TEST_ONLY missing session/CSRF'}).encode(),
        headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=10) as r:no_auth={'status':r.status,'response':json.load(r)}
    except HTTPError as e:no_auth={'status':e.code,'response':json.load(e)}
    requests.append({'path':'/api/archloop/workspaces','method':'POST','headers':{'Origin':'ABSENT','Cookie':'ABSENT','CSRF':'ABSENT'},
                     **no_auth,'at':timestamp()})
    if no_auth['status']==200:
        findings.append({'id':'D-A-02','owner':'A','severity':'HIGH',
            'detail':'New workspace write accepts absent Origin/session/CSRF',
            'expected':'Task §A7 requires server-side session anti-forgery token on all new writes'})
    missing={'persistence','correction','handoff'}-set(status.get('adapter',{}).get('registered',{}))
    if missing:
        findings.append({'id':'D-A-03','owner':'A/B/C/D integration','severity':'BLOCKER',
            'detail':'No registered real shared backends: '+','.join(sorted(missing)),
            'expected':'B immutable version / C patch / protected D task binding; module presence is insufficient'})
    save(output,{'schemaVersion':'d_workbench_http_probe_v1','targetHead':target_head,'baseUrl':base,
        'observedAt':timestamp(),'scope':'ISOLATED_RUNTIME_COMPOSITION_NOT_A_ACCEPTED_DELIVERY',
        'requests':requests,'observations':observations,'findings':findings,
        'realAI':'NOT_RUN_AWAITING_CONFIGURATION','browserUI':'NOT_RUN','audit':'AUDIT_PENDING'})
    return findings


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',required=True)
    p.add_argument('--fixture-code',type=Path,required=True);p.add_argument('--second-code',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--target-head',required=True)
    a=p.parse_args()
    if a.output.exists():p.error('do not overwrite evidence')
    print(json.dumps(probe(a.base_url,a.fixture_code,a.second_code,a.output,a.target_head),ensure_ascii=False))
