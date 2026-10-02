"""Review only this branch's changed/added text; no secret values in output."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = 'ff22b76966e6198b062c60fa9f0f4dbb987b027e'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').splitlines()

def main():
    names = set(git('diff', '--name-only', BASE)) | set(git('ls-files', '--others', '--exclude-standard'))
    secret = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
    private = re.compile(r'[A-Z]:[/\\]Users[/\\][^/\\\s\"\']+')
    files, findings = [], []
    for name in sorted(names):
        path = ROOT/name
        if not path.is_file() or name.endswith('PUBLICATION_AUDIT.json'):
            continue
        data = path.read_bytes()
        text = data.decode('utf-8', errors='replace')
        categories = []
        if secret.search(text): categories.append('potential_credential')
        if private.search(text): categories.append('personal_local_user_path')
        if len(data) > 10*1024*1024: categories.append('large_file')
        if name.startswith(('collaboration/', 'data/project-map', 'app.py', 'extension_host.py')):
            categories.append('outside_owned_CA_scope')
        if categories: findings.append({'path': name, 'categories': categories})
        files.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    result = {'baseline': BASE, 'branch': git('branch','--show-current')[0],
              'files': files, 'findings': findings, 'pass': not findings,
              'scope': 'All CA-owned changes/additions since pre-CA PR21 parent, including interrupted MVP; no teammate source bundle'}
    (ROOT/'experiments/validation/PUBLICATION_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files),'findings':findings,'pass':result['pass']}))
    return 0 if result['pass'] else 1

if __name__ == '__main__': raise SystemExit(main())
