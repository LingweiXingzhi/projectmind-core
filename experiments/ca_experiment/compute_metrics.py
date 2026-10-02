"""Independent aggregation: reject incomplete data and compare factual content."""
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {'A1': 'raw', 'A2': 'raw', 'A3': 'raw', 'B1': 'ca', 'B2': 'ca', 'B3': 'ca'}
VERDICTS = {'CORRECT', 'PARTIAL', 'WRONG', 'UNCERTAIN'}

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def aggregate(gt, judgments):
    qids = {row['qid'] for row in gt}
    if len(qids) != len(gt) or len(qids) != 20:
        raise ValueError('Ground truth must contain exactly 20 unique questions')
    seen = set()
    for row in judgments:
        pair = (row['run'], row['qid'])
        if pair in seen or row['run'] not in RUNS or row['qid'] not in qids:
            raise ValueError('Duplicate or unexpected judgment')
        if row['condition'] != RUNS[row['run']] or row['verdict'] not in VERDICTS:
            raise ValueError('Invalid condition or verdict')
        if not isinstance(row.get('normalized_answer'), str) or not row['normalized_answer']:
            raise ValueError('Independent semantic normalization required')
        if not isinstance(row.get('reason'), str) or not row['reason'].strip():
            raise ValueError('Independent judgment reason required')
        for field in ('used_stale_source', 'unsupported_assumption'):
            if type(row.get(field)) is not bool:
                raise ValueError(f'{field} must be boolean')
        seen.add(pair)
    if seen != set(itertools.product(RUNS, qids)):
        raise ValueError('All six runs x 20 questions must be judged')
    result = {'per_condition': {}, 'per_question_disagreement': {}, 'conflict_detection_rate': None,
              'conflict_detection_note': 'Frozen twenty questions contain no unresolved-conflict truth label. N/A; adversarial HUMAN_REQUIRED tests separately cover actual conflicts.'}
    for cond in ('raw', 'ca'):
        selected = [j for j in judgments if j['condition'] == cond]
        totals = {v.lower(): sum(j['verdict'] == v for j in selected) for v in sorted(VERDICTS)}
        pairs = disagree = 0
        per_question = {}
        for qid in sorted(qids):
            answers = [j for j in selected if j['qid'] == qid]
            count = sum(a['normalized_answer'] != b['normalized_answer'] for a,b in itertools.combinations(answers,2))
            per_question[qid] = {'disagreeing_pairs': count, 'pairs': 3}
            disagree += count
            pairs += 3
        stale = sum(j['used_stale_source'] for j in selected)
        unsupported = sum(j['unsupported_assumption'] for j in selected)
        result['per_condition'][cond] = {'runs': 3, 'answers': 60, **totals,
            'ground_truth_accuracy': totals['correct']/60,
            'partial_credit_accuracy': (totals['correct']+0.5*totals['partial'])/60,
            'factual_disagreement_rate': disagree/pairs, 'disagreeing_pairs': disagree, 'pairs': pairs,
            'stale_source_usage': stale, 'stale_source_usage_rate': stale/60,
            'unsupported_assumptions': unsupported, 'unsupported_assumption_rate': unsupported/60,
            'conflict_detection_rate': None}
        result['per_question_disagreement'][cond] = per_question
    return result

def main():
    freeze = json.loads((HERE/'INPUT_FREEZE.json').read_text(encoding='utf-8'))
    for relative, expected in freeze['sha256'].items():
        if hashlib.sha256((HERE/relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen input changed: {relative}')
    metrics = aggregate(rows(HERE/'ground_truth.jsonl'), rows(HERE/'judgments.jsonl'))
    (HERE/'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metrics['per_condition'], ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
