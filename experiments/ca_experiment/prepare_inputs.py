"""Freeze existing 20-question experiment without exposing answers to agents."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = Path('G:/jiagou/projectmind-core')
BENCH = Path('G:/jiagou/projectmind-benchmark')
PR = BENCH / 'B_PR22_HOLDOUT/pr22_tree/LingweiXingzhi-projectmind-core-0c46747147f765260bf2033f6eae40189b58ca0c'

def command(args):
    return subprocess.check_output(args, cwd=CORE).decode('utf-8')

def main():
    freeze = HERE / 'INPUT_FREEZE.json'
    if freeze.exists():
        raise SystemExit('Inputs already frozen; refusing to overwrite')
    raw = HERE / 'raw_inputs'
    ca = HERE / 'context_inputs'
    raw.mkdir(exist_ok=True)
    ca.mkdir(exist_ok=True)
    provenance = {}
    def write(directory, name, data, source):
        p = directory / name
        p.write_text(data, encoding='utf-8', newline='\n')
        provenance[str(p.relative_to(HERE))] = source
    for rev, tag in [('7484d44ddeac3c054ca3ba68f92293d965bb615c', 'main'), ('ff22b76966e6198b062c60fa9f0f4dbb987b027e', 'pr21')]:
        for name in ['COLLABORATION_CONTRACT', 'MVP_INTERFACES', 'TEAM_SOP']:
            path = f'docs/standards/{name}.md'
            write(raw, f'{tag}_{name}.md', command(['git', 'show', f'{rev}:{path}']), f'projectmind-core@{rev}:{path}')
        write(raw, f'{tag}_extensions.txt', command(['git', 'ls-tree', '-r', '--name-only', rev, 'extensions']), f'git ls-tree {rev} extensions')
    for number in [21, 22]:
        endpoint = f'repos/LingweiXingzhi/projectmind-core/pulls/{number}'
        data = json.loads(command(['gh', 'api', endpoint]))
        fields = {k: data[k] for k in ['number', 'state', 'merged', 'title']}
        fields['head'] = data['head']['sha']
        write(raw, f'pr{number}_status.json', json.dumps(fields, ensure_ascii=False, indent=2), endpoint)
    write(raw, 'main_head.txt', command(['gh', 'api', 'repos/LingweiXingzhi/projectmind-core/commits/main', '--jq', '.sha']), 'GitHub commits/main')
    for name in ['FINAL_BENCHMARK_REPORT.md', 'B_PR22_BENCHMARK_REPORT.md']:
        write(raw, name, (BENCH / name).read_text(encoding='utf-8'), str(BENCH / name))
    write(raw, 'B_DELIVERY_CONTRACT.md', (PR / 'collaboration/b/2026-10-01-wang-haining/README.md').read_text(encoding='utf-8'), 'PR22@0c46747147f765260bf2033f6eae40189b58ca0c collaboration/b/2026-10-01-wang-haining/README.md')
    write(raw, 'B_BOUNDARY_AUDIT.md', (BENCH / 'B_PR22_HOLDOUT/B_CONTRACT_BOUNDARY_AUDIT.md').read_text(encoding='utf-8'), 'Original benchmark audit, not Context Authority artifact')
    for directory in [raw, ca]:
        write(directory, 'questions.jsonl', (HERE / 'questions.jsonl').read_text(encoding='utf-8'), 'Existing frozen questions')
    write(ca, 'CONTEXT_PACK.json', (HERE / 'CONTEXT_PACK.json').read_text(encoding='utf-8'), 'Existing interrupted experiment pack; fixed snapshot condition')
    write(ca, 'AGENT_BOOTSTRAP.md', (HERE.parents[1] / 'AGENT_BOOTSTRAP.md').read_text(encoding='utf-8'), 'Existing consumer rules')
    paths = [HERE / 'questions.jsonl', HERE / 'ground_truth.jsonl'] + list(raw.iterdir()) + list(ca.iterdir())
    payload = {'frozen_at': datetime.now(timezone.utc).isoformat(), 'baseline_commit': 'ffd8781', 'formal_runs_present': [], 'question_count': 20, 'protocol': 'fresh agents fork_turns=none; filesystem allowlist by instruction and recorded reads, not OS sandbox; CA answers only context_inputs; raw only raw_inputs; no truth, reports, other runs', 'provenance': provenance, 'sha256': {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    freeze.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Frozen {len(paths)} input files; original questions and ground truth preserved')

if __name__ == '__main__':
    main()
