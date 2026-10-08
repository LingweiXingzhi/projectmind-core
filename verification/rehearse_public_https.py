"""Isolated local TLS + production CLI rehearsal; never real project approval.

Requires an explicitly supplied, independently verified Caddy executable.
Output must be a new private directory outside all Git working trees.
This HTTP client verifies TLS certificates/hostname; it is not a browser test.
"""
import argparse, json, os, pathlib, shutil, socket, sqlite3, ssl, subprocess, sys, time
from http.client import HTTPSConnection
SOURCE = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=pathlib.Path, required=True)
parser.add_argument("--caddy", type=pathlib.Path, required=True)
args = parser.parse_args()
caddy = args.caddy.resolve(strict=True)
sys.path.insert(0,str(SOURCE));sys.path.insert(0,str(SOURCE/'tests'))
from deployment.access import create_account_file, _outside_git
from test_archloop_a_backend_b import tiny_code_repo, architecture_repo, run_git
import secrets
fixture = _outside_git(args.output)
if fixture.exists(): raise RuntimeError('Preserve existing evidence; choose a new run name')
fixture.mkdir(mode=0o700, parents=True)
code=tiny_code_repo(fixture);arch=architecture_repo(fixture)
run_git(arch, 'remote', 'add', 'origin', 'https://example.invalid/architecture-fixture.git')
password=secrets.token_urlsafe(24);create_account_file(fixture/'accounts.json','browser-fixture',password)
def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
backend_port, proxy_port=port(),port()
origin=f'https://projectmind.example.invalid:{proxy_port}'
config={'schemaVersion':'projectmind_deploy_v1','publicOrigin':origin,
    'accountsFile':str(fixture/'accounts.json'),'dataRoot':str(fixture/'state'),
    'codeRepositories':[str(code)],'architectureRepo':str(arch),
    'architectureBranch':'architecture/candidates/archloop-test'}
(fixture/'runtime.json').write_text(json.dumps(config))
caddyfile=f'''{{
    admin off
    persist_config off
    skip_install_trust
    auto_https disable_redirects
}}
{origin} {{
    bind 127.0.0.1
    tls internal
    request_body {{
        max_size 1MB
    }}
    reverse_proxy 127.0.0.1:{backend_port} {{
        header_up -Forwarded
        header_up -X-Forwarded-User
    }}
}}
'''
(fixture/'Caddyfile').write_text(caddyfile)
env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', XDG_DATA_HOME=str(fixture/'caddy-data'),
    XDG_CONFIG_HOME=str(fixture/'caddy-config'))
env.pop('OPENAI_API_KEY',None);env.pop('PROJECTMIND_AI_MODEL',None)
processes=[];files=[]
try:
    for name,command,cwd in [
        ('application',[sys.executable,'-m','deployment.server','serve','--config',str(fixture/'runtime.json'),'--port',str(backend_port)],SOURCE),
        ('proxy',[str(caddy),'run','--config',str(fixture/'Caddyfile'),'--adapter','caddyfile'],fixture)]:
        handle=(fixture/(name+'.log')).open('w');files.append(handle)
        processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=handle,stderr=handle))
    root_certificate=fixture/'caddy-data/caddy/pki/authorities/local/root.crt'
    for _ in range(100):
        if any(p.poll() is not None for p in processes): raise RuntimeError('Fixture service failed; inspect private logs')
        if root_certificate.exists(): break
        time.sleep(.1)
    else: raise RuntimeError('Local CA did not start')
    context=ssl.create_default_context(cafile=str(root_certificate))
    class LocalTLS(HTTPSConnection):
        def connect(self):
            raw=socket.create_connection(('127.0.0.1',proxy_port),timeout=10)
            self.sock=self._context.wrap_socket(raw,server_hostname='projectmind.example.invalid')
    verified=False
    for _ in range(40):
        connection=LocalTLS('projectmind.example.invalid',proxy_port,context=context,timeout=10)
        try:
            connection.request('GET','/api/archloop',headers={'Host':f'projectmind.example.invalid:{proxy_port}'})
            response=connection.getresponse();response.read()
            if response.status==401: verified=True;break
            time.sleep(.1)
        except (OSError,ssl.SSLError):time.sleep(.1)
        finally:connection.close()
    assert verified,'TLS certificate/hostname or unauthenticated boundary failed'
    code_before=(run_git(code,'rev-parse','HEAD'),run_git(code,'status','--porcelain'))
    observations=[]
    def request(method,path,payload=None,auth=None,request_origin=origin):
        connection=LocalTLS('projectmind.example.invalid',proxy_port,context=context,timeout=20)
        headers={'Host':f'projectmind.example.invalid:{proxy_port}','Content-Type':'application/json'}
        if request_origin is not None:headers['Origin']=request_origin
        headers.update(auth or {})
        try:
            connection.request(method,path,body=json.dumps(payload or {}).encode() if method=='POST' else None,headers=headers)
            response=connection.getresponse();raw=response.read()
            metadata=dict(response.getheaders())
            body=json.loads(raw) if raw and metadata.get('Content-Type','').startswith('application/json') else None
            observations.append({'method':method,'route':path.split('/workspaces/')[0], 'status':response.status})
            return response.status,metadata,body
        finally:connection.close()
    from http.cookies import SimpleCookie
    def login():
        status,headers,body=request('POST','/api/auth/login',{'username':'browser-fixture','password':password})
        assert status==200
        cookie=SimpleCookie();cookie.load(headers['Set-Cookie'])
        assert cookie['__Host-projectmind']['secure'] and cookie['__Host-projectmind']['httponly']
        return {'Cookie':'__Host-projectmind='+cookie['__Host-projectmind'].value,'X-ProjectMind-CSRF':body['csrf']}
    assert request('GET','/api/archloop',request_origin=None)[0]==401
    auth,other=login(),login()
    duplicate=subprocess.run([sys.executable,'-m','deployment.server','serve','--config',str(fixture/'runtime.json'),
        '--port',str(port())],cwd=SOURCE,env=env,capture_output=True,text=True,timeout=20)
    assert duplicate.returncode==1,'A second serving process used the same data root'
    registered_key=request('GET','/api/auth/session',auth=auth)[2]['repositories'][0]['key']
    assert request('POST','/api/archloop/workspaces',{},auth={'Cookie':auth['Cookie']})[0]==403
    assert request('POST','/api/archloop/workspaces',{},auth=auth,request_origin='https://evil.example.invalid')[0]==403
    publications=[]; tasks=[]
    for planning in (False,True):
        payload={'context':'planning' if planning else 'existing_project','title':'TLS fixture only',
            'goals':'保存设计','constraints':'不伪造实现','description':'isolated fixture'}
        if not planning:payload['repoPath']=registered_key
        status,_,opened=request('POST','/api/archloop/workspaces',payload,auth);assert status==200
        path='/api/archloop/workspaces/'+opened['workspace']['workspaceId']
        status,_,candidate=request('POST',path+'/generate',{'mode':'rule_based'},auth);assert status==200
        status,_,applied=request('POST',path+'/apply-candidate',{'candidateId':candidate['candidateId'],'expectedDraftRevision':None},auth);assert status==200
        if not planning:
            node=applied['draft']['graph']['nodes'][0]['id']
            status,_,applied=request('POST',path+'/apply-ops', {
                'expectedDraftRevision':applied['draft']['draftRevision'],
                'operations':[{'type':'update_process','nodeId':node,'process':[
                    {'stepId':'fixture-return','title':'Fixture expected return','detail':'Not real runtime evidence',
                     'inputs':[],'outputs':[],'branches':[],'next':[]}]}]},auth)
            assert status==200
        status,_,preview=request('POST',path+'/review-preview',{'actor':'FORGED_JSON_ACTOR',
            'verifyCode':False,'reason':'FIXTURE ONLY simulated design/expected-process review'},auth);assert status==200
        confirmation={'previewDigest':preview['previewDigest'],'decision':'accept'}
        assert request('POST',path+'/review-confirm',confirmation,other)[0]==403
        assert request('POST',path+'/review-confirm',confirmation,auth)[0]==200
        assert request('POST',path+'/publish',{},other)[0]==403
        status,_,published=request('POST',path+'/publish',{},auth);assert status==200
        assert published['envelope']['lastPublish']['actor']=='browser-fixture'
        assert published['provenance']['mapSourceRevision']==run_git(arch,'rev-parse','HEAD')
        assert request('GET',path,auth=other)[2]['identity']['mapRevision']==published['version']['mapRevision']
        if planning:assert published['version']['codeRevision'] is None and published['version']['verifiedCodeRevision'] is None
        publications.append({'context':payload['context'],'mapRevision':published['version']['mapRevision'],
            'mapSourceRevision':published['provenance']['mapSourceRevision'],'codeRevision':published['version']['codeRevision']})
        if not planning:
            status,_,hints=request('GET',path+'/fix-task-hints',auth=auth);assert status==200 and hints['canCreate']
            process=hints['processes'][0]
            status,_,task=request('POST',path+'/fix-tasks',{
                'expectedMapRevision':hints['mapRevision'],'expectedDraftRevision':hints['draftRevision'],
                'expectedProcessRef':{'processId':process['id'],'stepIds':[process['steps'][0]['id']]},
                'deviation':'Synthetic declared observation','scope':['service.py'],
                'evidence':[{'kind':'test_observation','detail':'Fixture only, real team runtime NOT_RUN',
                    'codeRepoId':hints['codeRepoId'],'codeRevision':hints['codeRevision']}],
                'acceptance':'Synthetic acceptance','actor':'FORGED_JSON_ACTOR'},auth)
            assert status==200 and task['actor']=='browser-fixture' and task['actorIdentity']=='authenticated_account'
            status,_,task=request('POST',path+'/fix-tasks/'+task['id']+'/governance',{
                'action':'transition','expectedRevision':task['revision'],'expectedMapRevision':task['mapRevision'],
                'status':'received','description':'FIXTURE ONLY received'},auth)
            assert status==200 and task['status']=='received'
            status,_,listed=request('GET',path+'/fix-tasks',auth=other)
            assert status==200 and listed['tasks'][0]['id']==task['id'] and 'versionHandoff' not in listed['tasks'][0]
            status,_,handoff=request('GET',path+'/handover',auth=other)
            assert status==200 and handoff['schemaVersion']=='architecture_handoff_v1'
            tasks.append({'id':task['id'],'workspaceId':task['workspaceId'],'mapRevision':task['mapRevision'],
                'revision':task['revision'],'status':task['status'],'actorIdentity':task['actorIdentity']})
    assert code_before==(run_git(code,'rev-parse','HEAD'),run_git(code,'status','--porcelain'))
    report={'schemaVersion':'local_https_rehearsal_v1','fixtureOnly':True,'backend':'actual Waitress CLI',
        'proxy':subprocess.check_output([str(caddy),'version'],text=True).strip(),'localCertificateAndHostnameVerified':True,
        'codeGitUnchanged':True,'publicNetwork':'NOT_RUN','realTeamApproval':'NOT_RUN',
        'browser':'NOT_RUN_NOT_A_BROWSER_HARNESS','requests':len(observations),
        'observations':observations,'publishedFixtures':publications,
        'crossSessionConfirmRejected':True,'crossSessionPublishRejected':True,
        'csrfRejected':True,'wrongOriginRejected':True,'trustedActorFromSession':True,
        'planningNoFakeCodeSHA':True,'secondServingProcessRejected':True,
        'governedTasks':tasks,'nativeHandoffSchema':bool(tasks),
        'sourceLocalSHA':run_git(SOURCE,'rev-parse','HEAD'),'sourceTree':run_git(SOURCE,'rev-parse','HEAD^{tree}'),
        'sourceWorkingTreeDirty':bool(run_git(SOURCE,'status','--porcelain'))}
    (fixture/'HTTPS_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')

finally:
    for process in reversed(processes):
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    for handle in files:handle.close()

# The CLI/proxy have stopped. Copy state + architecture together into a new
# private fixture; preserve the original and never restore login credentials.
restored = fixture / "cold-restore"
restored.mkdir(mode=0o700)
shutil.copytree(fixture / "state", restored / "state")
shutil.copytree(arch, restored / "architecture")
def documents(path):
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        return connection.execute("SELECT kind, id, body FROM documents ORDER BY kind, id").fetchall()
assert documents(fixture/"state/b/workspace.sqlite3") == documents(restored/"state/b/workspace.sqlite3")
def d_tasks(path):
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro",uri=True) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return connection.execute('SELECT id,revision,document FROM architecture_fix_tasks ORDER BY id').fetchall()
assert d_tasks(fixture/'state/d/continuity.sqlite3') == d_tasks(restored/'state/d/continuity.sqlite3')
assert run_git(arch,"rev-parse","HEAD") == run_git(restored/"architecture","rev-parse","HEAD")
restore_config = dict(config, dataRoot=str(restored/"state"), architectureRepo=str(restored/"architecture"))
restore_path = restored / "runtime.json"
restore_path.write_text(json.dumps(restore_config))
from deployment.server import build_application
application = build_application(restore_path)
rows = application.service.list_workspaces()["workspaces"]
assert len(rows) == 2
identities = []
for row in rows:
    opened = application.service.open_workspace(row["workspaceId"])
    identities.append((opened["identity"]["mapRevision"], opened["identity"]["mapSourceRevision"]))
assert sorted(identities) == sorted((v["mapRevision"], v["mapSourceRevision"]) for v in publications)
assert len(application.access.sessions) == 0
reopened=application.service.backend_d.service.listing()
assert [(v['id'],v['revision'],v['status']) for v in reopened] == [(v['id'],v['revision'],v['status']) for v in tasks]
assert len(application.service.backend_d.gateway.sessions)==0
restore_report = {"schemaVersion":"cold_restore_fixture_v1", "fixtureOnly":True,
    "serviceStoppedBeforeCopy":True, "sqliteIntegrity":"ok", "bDocumentsEqual":True,
    "aWorkspacesReopened":len(rows), "architectureGitHeadEqual":True, "newBrowserSessions":0,
    "scope":"same host, same registered code fixture; not cloud recovery",
    "sourceLocalSHA":report["sourceLocalSHA"], "sourceTree":report["sourceTree"]}
restore_report.update(dSQLiteIntegrity='ok',dTasksEqual=True,dTasksReopened=len(reopened),dSessionsRestored=0)
(restored/"RESTORE_REPORT.json").write_text(json.dumps(restore_report,indent=2)+"\n")
print(json.dumps({"https":report,"restore":restore_report}))
