"""Linux non-root runtime check on a root-owned fixed release, not systemd boot.

Run as root in an isolated test machine, explicitly selecting an existing
unprivileged account. No production users/configuration are created or changed.
Dependencies must be installed in the supplied isolated venv beforehand.
"""
import argparse
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE)); sys.path.insert(0, str(SOURCE/'tests'))
from deployment.access import create_account_file
from deployment.host import private_json, stage_release
from test_archloop_a_backend_b import tiny_code_repo, architecture_repo, run_git

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--user', required=True)
parser.add_argument('--python', type=Path, required=True)
args = parser.parse_args()
assert os.geteuid() == 0
user = pwd.getpwnam(args.user); assert user.pw_uid != 0
root = args.output.resolve(); assert not root.exists()
def mapped(path, identifier):
    if not path.exists(): return True
    return any(start <= identifier < start+count for start, outer, count in
               (map(int, line.split()) for line in path.read_text().splitlines()))
if not mapped(Path('/proc/self/uid_map'), user.pw_uid) or not mapped(Path('/proc/self/gid_map'), user.pw_gid):
    root.mkdir(mode=0o700)
    report = {'schemaVersion':'projectmind_service_user_fixture_v1', 'fixtureOnly':True,
              'status':'NOT_RUN_USER_ID_NOT_MAPPED', 'runtimeUserVerified':False,
              'systemdActivation':'NOT_RUN_NO_SYSTEMD_PID1', 'publicNetwork':'NOT_RUN'}
    private_json(root/'REPORT.json', report)
    print(json.dumps(report)); raise SystemExit(2)
root.mkdir(mode=0o755)
private = root/'private'; private.mkdir(mode=0o700)
code = tiny_code_repo(private); arch = architecture_repo(private)
state = private/'state'; state.mkdir(mode=0o700)
create_account_file(private/'accounts.json', 'fixture', 'synthetic-fixture-password-only')
config = private/'runtime.json'
origin = 'https://projectmind.example.invalid'
private_json(config, {'schemaVersion': 'projectmind_deploy_v1', 'publicOrigin': origin,
                     'accountsFile': str(private/'accounts.json'), 'dataRoot': str(state), 'codeRepositories': [str(code)],
                     'architectureRepo': str(arch), 'architectureBranch': 'architecture/candidates/archloop-test'})
for path in [private, *private.rglob('*')]: os.chown(path, user.pw_uid, user.pw_gid)
head = run_git(SOURCE, 'rev-parse', 'HEAD')
release = stage_release(SOURCE, head, root/'releases'); app = root/'releases'/head/'app'
with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
prefix = ['runuser', '-u', args.user, '--', str(args.python.absolute())]
# This host preflight deliberately has safe.directory for the exact source
# probe; runtime Git reads the registered code/architecture owned by this user.
probe = subprocess.run(prefix+['-m','deployment.host','preflight','--config',str(config),
                              '--source',str(app),'--expected-sha',head], cwd=app, capture_output=True, timeout=60)
assert probe.returncode == 0, 'Unprivileged preflight failed (inspect private fixture only)'
handle = (root/'application.log').open('w')
process = subprocess.Popen(prefix+['-m','deployment.server','serve','--config',str(config),'--port',str(port)],
                           cwd=app, stdout=handle, stderr=handle,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
try:
    ready = False
    for attempt in range(100):
        assert process.poll() is None, 'Unprivileged service stopped'
        connection = HTTPConnection('127.0.0.1', port, timeout=2)
        try:
            connection.request('GET','/api/archloop',headers={'Host':'projectmind.example.invalid'})
            response = connection.getresponse(); response.read()
            if response.status == 401: ready=True; break
        except OSError: pass
        finally: connection.close()
        time.sleep(.1)
    assert ready
    report = {'schemaVersion':'projectmind_service_user_fixture_v1', 'fixtureOnly':True,
              'effectiveUserNonRoot':True, 'rootOwnedRelease':app.stat().st_uid == 0,
              'preflightPassed':True, 'actualWaitressAnonymousAPI':401,
              'sourceLocalSHA':head, 'sourceTree':release['tree'],
              'systemdActivation':'NOT_RUN_NO_SYSTEMD_PID1', 'publicNetwork':'NOT_RUN'}
    private_json(root/'REPORT.json', report)
    print(json.dumps(report))
finally:
    process.terminate()
    try: process.wait(timeout=10)
    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    handle.close()
