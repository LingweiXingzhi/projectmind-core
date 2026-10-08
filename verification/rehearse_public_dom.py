"""Run owned scripts in jsdom against a real isolated production HTTP app."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / 'tests'))
from test_public_deployment import PublicHTTPTests, run_git
from deployment.access import _outside_git


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True, type=Path)
    parser.add_argument('--jsdom', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = _outside_git(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.environ.pop('OPENAI_API_KEY', None)
    os.environ.pop('PROJECTMIND_AI_MODEL', None)
    class Runtime(PublicHTTPTests):
        pass
    Runtime.setUpClass()
    try:
        run_git(Runtime.arch, 'remote', 'add', 'origin', 'https://example.invalid/dom-architecture-fixture.git')
        before = (run_git(Runtime.code, 'rev-parse', 'HEAD'), run_git(Runtime.code, 'status', '--porcelain'))
        payload = {'port': Runtime.port, 'username': 'fixture', 'password': Runtime.password}
        with (output / 'stderr.log').open('w') as error:
            result = subprocess.run([str(args.node), str(Path(__file__).with_suffix('.cjs')), str(args.jsdom)],
                input=json.dumps(payload), text=True, capture_output=False, stdout=subprocess.PIPE,
                stderr=error, timeout=90)
        (output / 'stdout.log').write_text(result.stdout)
        if result.returncode:
            raise RuntimeError('DOM rehearsal failed; inspect the private output directory')
        report = json.loads(result.stdout)
        assert before == (run_git(Runtime.code, 'rev-parse', 'HEAD'), run_git(Runtime.code, 'status', '--porcelain'))
        report['codeGitUnchanged'] = True
        report['sourceLocalSHA'] = run_git(SOURCE, 'rev-parse', 'HEAD')
        report['sourceWorkingTreeDirty'] = bool(run_git(SOURCE, 'status', '--porcelain'))
        (output / 'FULL_DOM_REPORT.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report))
    finally:
        Runtime.tearDownClass()


if __name__ == '__main__':
    main()
