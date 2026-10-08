"""Consume the actual optional C module against real isolated Git observations.

This is a component probe, never public UI or a confirmed project model. Every
external discrepancy is recorded as a finding, not repaired in another owner.
"""
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from tests.architecture_loop_acceptance.fixture import create, commit, git, GOOD
from extensions.handoff.architecture import build_version_handoff, source_locator
from extensions.continuity.fix_tasks import FixTaskService
from extensions.continuity.store import Store


def probe(output, *, source_checkout):
    output = Path(output).resolve()
    source_checkout = Path(source_checkout).resolve()
    if output.exists():
        raise ValueError('output already exists; preserving previous evidence')
    from extensions.map_proposal import candidates as c
    from extensions.architecture_workspace.proposals import validate_proposal
    from extensions.architecture_workspace.errors import WorkspaceError
    source = Path(c.__file__).resolve()
    if source_checkout not in source.parents:
        raise ValueError('C source is not in the specified checkout')
    head = git(source_checkout, 'rev-parse', 'HEAD')
    if git(source_checkout, 'status', '--porcelain'):
        raise ValueError('validation checkout must be clean')
    f = create(output / 'fixture')
    v = f['versionEnvelope']['version']
    graph = {'mapRevision': v['mapRevision'], 'codeRevision': v['codeRevision'],
             'nodes': [{'nodeId': 'node-B', 'role': 'Expected B reaches C',
                        'expectedProcesses': ['A', 'B', 'C']}]}
    command = [sys.executable, '-B', '-c',
               'import json; from flow import execute; print(json.dumps(execute()))']
    def observe():
        process = subprocess.run(command, cwd=f['code'], capture_output=True, timeout=15)
        if process.returncode:
            raise RuntimeError(process.stderr.decode(errors='replace'))
        return {'called_steps': json.loads(process.stdout),
                'codeRepoId': v['codeRepoId'], 'codeRevision': git(f['code'], 'rev-parse', 'HEAD'),
                'command': command, 'exitCode': process.returncode,
                'outputDigest': 'sha256:' + hashlib.sha256(process.stdout).hexdigest()}
    before = observe()
    detected = c.detect_process_deviations(deepcopy(graph), [before])
    if detected.get('verdict') != 'DEVIATION_DETECTED' or not detected.get('deviations'):
        raise RuntimeError('Actual controlled bypass was not detected; do not create a successful closure')
    unknown = c.detect_process_deviations(deepcopy(graph), [])
    unrelated = c.detect_process_deviations(deepcopy(graph), [
        {'called_steps': ['X'], 'codeRepoId': 'wrong-repository', 'codeRevision': '0' * 40}])
    packet = build_version_handoff(f['versionEnvelope'], workspace_id='workspace-fixture',
        sources={'code': source_locator(f['code']), 'architecture': source_locator(f['architecture'])})
    service = FixTaskService(Store(output / 'state' / 'records.sqlite3'),
                            architecture_repo=f['architecture'], code_repositories=[f['code']])
    task = service.create_fix_task(packet=packet, deviation_id='actual-C-bypass',
        deviation='Actual C reports B bypasses C in a real fixture trace',
        expected_process_ref={'processId': 'process-ABC', 'stepIds': ['step-B', 'step-C']},
        evidence=[{'kind': 'test_observation', **before, 'detail': json.dumps(detected)}],
        scope=['flow.py'], acceptance='Actual trace A B C, check_flow passes, C no deviations',
        actor='TEST_ONLY_SIMULATED_HUMAN')
    for state in ['received', 'in_progress']:
        task = service.transition(task['id'], expected_revision=task['revision'],
            expected_map_revision=task['mapRevision'], status=state,
            actor='TEST_ONLY_SIMULATED_HUMAN', description=state)
    git(f['code'], 'checkout', '-b', 'fix/actual-c-observation')
    Path(f['code'], 'flow.py').write_text(GOOD)
    repaired = commit(f['code'], 'TEST ONLY fix actual observed bypass')
    task = service.submit(task['id'], expected_revision=task['revision'],
        expected_map_revision=task['mapRevision'], revision=repaired,
        actor='TEST_ONLY_SIMULATED_HUMAN', evidence='Actual restricted fixture commit')
    after = observe()
    recheck_graph = deepcopy(graph); recheck_graph['codeRevision'] = repaired
    recheck = c.detect_process_deviations(recheck_graph, [after])
    if after['called_steps'] != ['A', 'B', 'C'] or recheck.get('verdict') != 'ALIGNED' or recheck.get('deviations'):
        raise RuntimeError('Actual repaired trace or C recheck failed; keep deviation pending')
    c_digest = 'sha256:' + hashlib.sha256(json.dumps(recheck, sort_keys=True).encode()).hexdigest()
    token, verification = service.run_fixture_verification(task['id'],
        command=[sys.executable, '-B', 'check_flow.py'], fixture_root=f['root'],
        observation=json.dumps(after), recheck_ref='actual_C_component:' + c_digest)
    task = service.confirm_verification(task['id'], token=token, expected_revision=task['revision'],
        expected_map_revision=task['mapRevision'], actor='TEST_ONLY_SIMULATED_HUMAN',
        reason='Fixture actual test and actual C recheck observed', human_confirmed=True)
    planning_context = {'mode': 'planning', 'workspaceId': 'workspace-probe',
        'goals': [{'id': 'req-one', 'title': 'Authentication', 'description': 'Login'}]}
    first = c.generate_bootstrap_proposal(planning_context)
    changed_context = deepcopy(planning_context)
    changed_context['goals'][0]['description'] = 'Completely different responsibility'
    changed = c.generate_bootstrap_proposal(changed_context)
    nl = c.generate_nl_correction_patch(graph, {'nodeId': 'node-B'}, 'Remove authentication responsibility')
    basis = {'workspaceId': 'workspace-probe', 'mapId': 'map-probe', 'mode': 'planning',
             'codeRepoId': None, 'codeRevision': None, 'baseMapRevision': None,
             'draftId': None, 'draftRevision': None}
    try:
        validate_proposal(first, basis)
        boundary = {'accepted': True}
    except WorkspaceError as exc:
        boundary = {'accepted': False, 'code': exc.code, 'message': str(exc)}
    self_candidate = json.loads((source.parent / 'PROJECTMIND_SELF_CANDIDATE.json').read_text())
    evidence = []
    for node in self_candidate['graphCandidate']['nodes']:
        for ev in node.get('evidence', []):
            path = ev.get('path')
            if path:
                try:
                    kind = git(source_checkout, 'cat-file', '-t', self_candidate['codeRevision'] + ':' + path.rstrip('/'))
                except subprocess.CalledProcessError:
                    kind = 'MISSING'
                evidence.append({'nodeId': node['nodeId'], 'path': path,
                                 'atClaimedRevision': self_candidate['codeRevision'], 'gitType': kind})
    findings = []
    if unrelated.get('verdict') == 'ALIGNED':
        findings.append({'id': 'D-C-01', 'severity': 'HIGH', 'scenario': 'T16/T21',
            'detail': 'Unrelated trace missing expected steps and with wrong repo/SHA returned ALIGNED instead of UNKNOWN or rejection'})
    if first['proposalId'] == changed['proposalId'] and first['graphCandidate'] != changed['graphCandidate']:
        findings.append({'id': 'D-C-02', 'severity': 'HIGH',
            'detail': 'Same proposalId identifies different planning candidate content'})
    if not boundary['accepted']:
        findings.append({'id': 'D-BC-01', 'severity': 'BLOCKER',
            'detail': 'Actual C planning output rejected by actual B canonical validator; no automatic schema conversion claimed'})
    if any(e['gitType'] != 'blob' for e in evidence):
        findings.append({'id': 'D-C-03', 'severity': 'HIGH', 'scenario': 'T24',
            'detail': 'Self candidate contains missing or directory evidence at its claimed baseline SHA'})
    result = {'schemaVersion': 'd_actual_candidate_probe_v1',
        'scope': 'ACTUAL_B_C_D_COMPONENTS_SYNTHETIC_FIXTURE_NOT_PUBLIC_UI',
        'at': datetime.now(timezone.utc).isoformat(), 'targetHead': head,
        'CSourceBlob': hashlib.sha1(b'blob ' + str(len(source.read_bytes())).encode() + b'\0' + source.read_bytes()).hexdigest(),
        'fixture': {'baseline': v['codeRevision'], 'submitted': repaired, 'mapRevision': v['mapRevision'],
                    'mapSourceRevision': f['versionEnvelope']['provenance']['mapSourceRevision']},
        'before': before, 'detected': detected, 'noTrace': unknown, 'unrelatedTrace': unrelated,
        'after': after, 'actualCRecheck': recheck, 'verification': verification,
        'task': service.export_task(task['id']), 'planningFirst': first, 'planningChanged': changed,
        'naturalLanguagePatch': nl, 'BValidationOfC': boundary, 'selfCandidateEvidence': evidence,
        'findings': findings, 'humanApproval': 'TEST_ONLY_SIMULATED_HUMAN',
        'realAI': 'NOT_RUN_AWAITING_CONFIGURATION', 'publicIntegration': 'BLOCKED',
        'audit': 'AUDIT_PENDING'}
    if git(source_checkout, 'rev-parse', 'HEAD') != head or git(source_checkout, 'status', '--porcelain'):
        raise ValueError('target changed during observation')
    (output / 'candidate-probe.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-checkout', required=True)
    args = parser.parse_args()
    result = probe(args.output, source_checkout=args.source_checkout)
    print(json.dumps({'report': str(Path(args.output) / 'candidate-probe.json'),
                      'findings': len(result['findings']), 'task': 'verified_fixture_only'}))
    sys.exit(1 if result['findings'] else 0)
