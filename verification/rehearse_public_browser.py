"""Actual local TLS + production CLI + isolated headless browser fixture."""
import argparse, json, os, pathlib, socket, ssl, subprocess, sys, time
from http.client import HTTPSConnection
SOURCE = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--caddy', type=pathlib.Path, required=True)
parser.add_argument('--node', type=pathlib.Path, required=True)
parser.add_argument('--playwright', type=pathlib.Path, required=True)
parser.add_argument('--browser-cache', type=pathlib.Path)
args = parser.parse_args()
ROOT = args.output.parent.resolve()

sys.path.insert(0,str(SOURCE));sys.path.insert(0,str(SOURCE/'tests'))
from deployment.access import create_account_file
from test_archloop_a_backend_b import tiny_code_repo, architecture_repo, run_git
import secrets
from deployment.access import _outside_git
fixture = _outside_git(args.output)
if fixture.exists(): raise RuntimeError('Preserve existing evidence; choose a new run name')
fixture.mkdir(mode=0o700, parents=True)
code=tiny_code_repo(fixture);arch=architecture_repo(fixture)
run_git(arch, 'remote', 'add', 'origin', 'https://example.invalid/native-browser-fixture.git')
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
if args.browser_cache:
    env['PLAYWRIGHT_BROWSERS_PATH']=str(args.browser_cache.resolve(strict=True))
env.pop('OPENAI_API_KEY',None);env.pop('PROJECTMIND_AI_API_KEY',None);env.pop('PROJECTMIND_AI_MODEL',None)
processes=[];files=[]
try:
    for name,command,cwd in [
        ('application',[sys.executable,'-m','deployment.server','serve','--config',str(fixture/'runtime.json'),'--port',str(backend_port)],SOURCE),
        ('proxy',[str(args.caddy.resolve(strict=True)),'run','--config',str(fixture/'Caddyfile'),'--adapter','caddyfile'],fixture)]:
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
    browser=subprocess.run([str(args.node.resolve(strict=True)),str(SOURCE/'verification/rehearse_public_browser.cjs'),str(args.playwright.resolve(strict=True))],
        input=json.dumps({'origin':origin,'password':password,'output':str(fixture)}),env=env,text=True,capture_output=True,timeout=110)
    (fixture/'browser.stdout.log').write_text(browser.stdout)
    (fixture/'browser.stderr.log').write_text(browser.stderr)
    assert browser.returncode==0,'Browser fixture failed; inspect local report'
    assert code_before==(run_git(code,'rev-parse','HEAD'),run_git(code,'status','--porcelain'))
    report={'schemaVersion':'local_https_rehearsal_v1','fixtureOnly':True,'backend':'actual Waitress CLI',
        'proxy':subprocess.run([str(args.caddy.resolve(strict=True)),'version'],check=True,capture_output=True,text=True).stdout.strip(),
        'localCertificateAndHostnameVerified':True,
        'codeGitUnchanged':True,'publicNetwork':'NOT_RUN','realTeamApproval':'NOT_RUN',
        'browserReport':'BROWSER_REPORT.json',
        'sourceLocalSHA':run_git(SOURCE,'rev-parse','HEAD'),
        'sourceTree':run_git(SOURCE,'rev-parse','HEAD^{tree}'),
        'sourceWorkingTreeDirty':bool(run_git(SOURCE,'status','--porcelain'))}
    (fixture/'HTTPS_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
finally:
    for process in reversed(processes):
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    for handle in files:handle.close()
