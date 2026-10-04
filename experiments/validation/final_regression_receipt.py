"""Repeat final complete regressions without replacing frozen experiment inputs."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def main():
    runs = []
    semantic = []
    for number in range(1,4):
        log = HERE/'regression_runs'/f'final_run_{number}.log'
        if '--recheck-logs' in sys.argv:
            output = log.read_text(encoding='utf-8')
            exit_code = 0 if re.search(r'\nOK\s*$', output) else 1
        else:
            proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                  cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
            output = proc.stdout+proc.stderr
            exit_code = proc.returncode
            log.write_text(output, encoding='utf-8')
        count = re.search(r'Ran (\d+) tests', output)
        # HTTP log timestamps can follow unittest's unfinished test line.
        # Compare identities and complete no-skip OK summaries, not log bytes.
        outcomes = re.findall(r'^(test_.*?) \.\.\. ', output, flags=re.MULTILINE)
        runs.append({'run':number,'exit_code':exit_code,'tests':int(count[1]) if count else None,
                     'log':str(log.relative_to(HERE)),'sha256':hashlib.sha256(output.encode()).hexdigest()})
        semantic.append(outcomes)
        print(f'Final complete regression {number}: {runs[-1]["tests"]} tests, exit={exit_code}', flush=True)
        if exit_code: break
    passed = len(runs)==3 and all(r['exit_code']==0 and r['tests']==172 for r in runs) and semantic[0]==semantic[1]==semantic[2]
    result = {'validated_product_commit':'3e12fdfebc507ff1755f9f8bcb01e67a0eac14d6',
              'runs':runs,'semantic_outcomes_equal':len(semantic)==3 and semantic[0]==semantic[1]==semantic[2],
              'pass':passed,'note':'After final metrics/harness fixes. Product code unchanged; frozen pack and participant inputs untouched. Initial comparison included HTTP log timestamps; corrected receipt compares test identities plus complete OK results without rerunning or editing logs.'}
    (HERE/'FINAL_REGRESSION_RECEIPT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
