"""Persist exact resume state. Does not commit, publish, or mutate other repos."""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
def update(phase, next_action, finished=False):
    ca_path = ROOT/'CONTEXT_AUTHORITY_CHECKPOINT.json'
    previous = json.loads(ca_path.read_text(encoding='utf-8'))
    ca = {**previous, 'timestamp': datetime.now(timezone(timedelta(hours=8))).isoformat(),
          'phase': phase, 'branch': git('branch','--show-current'), 'commit': git('rev-parse','HEAD'),
          'tests': previous.get('tests', {'baseline': '44/44 freshly passed'}),
          'agent_experiment': {cond: [p.name for p in sorted((ROOT/'experiments/ca_experiment'/directory).glob('*.jsonl'))] for cond,directory in [('raw','raw_agent_runs'),('ca','context_agent_runs')]},
          'validation_status': previous.get('validation_status','IN_PROGRESS'),
          'context_authority_status': previous.get('context_authority_status','EXPERIMENTAL'),
          'C_consumable': previous.get('C_consumable','NO'), 'benchmark_audit': previous.get('benchmark_audit','NOT_GIT_REPO; case C'),
          'benchmark_upload_status': 'BENCHMARK_REMOTE_TARGET_REQUIRED', 'other_assets': 'inventory pending',
          'github_pushes': previous.get('github_pushes',[]), 'draft_prs': previous.get('draft_prs',[]),
          'known_failures': previous.get('known_failures',[]),
          'human_decisions': ['Benchmark independent repository ownership/visibility/remote', 'Formal team baseline and contract changes', 'Main merge requires explicit human approval'],
          'next_action': next_action, 'finished': finished, 'scheduler_status':'ACTIVE_NATIVE_HEARTBEAT projectmind-context-authority'}
    ca_path.write_text(json.dumps(ca,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'UPLOAD_CHECKPOINT.json').write_text(json.dumps(ca,ensure_ascii=False,indent=2),encoding='utf-8')
    print(phase, ca['commit'], next_action)
if __name__ == '__main__':
    update(sys.argv[1],sys.argv[2])
