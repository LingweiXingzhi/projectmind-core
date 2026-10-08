"""Real isolated repositories, expected A→B→C and an observed bypass of C."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import os

from extensions.handoff.architecture import code_identity, digest, SEMANTIC, source_locator

GOOD = "def execute():\n    trace = ['A', 'B']\n    trace.append('C')\n    return trace\n"
BAD = "def execute():\n    trace = ['A', 'B']\n    return trace  # observed branch bypasses C\n"
TEST = "from flow import execute\nassert execute() == ['A', 'B', 'C'], execute()\nprint('expected process A -> B -> C observed')\n"


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE,
        env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}).decode().strip()


def init(repo, remote):
    repo.mkdir(parents=True)
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'config', 'user.name', 'TEST_ONLY')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    git(repo, 'remote', 'add', 'origin', remote)


def commit(repo, message):
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', message)
    return git(repo, 'rev-parse', 'HEAD')


def version_packet(repo, revision, planning=False):
    """TEST_ONLY_SIMULATED_HUMAN B-shaped fixture, not actual owner approval."""
    rid = None if planning else code_identity(repo)
    revision = None if planning else revision
    ev = {'id': 'goal-process', 'kind': 'user_goal', 'reason': 'test requirement',
          'content': 'Expected A then B then C'}
    graph = {'schemaVersion': 'architecture_graph_v1', 'nodes': [], 'edges': [],
             'evidence': [ev], 'processes': []}
    for name in 'ABC':
        graph['nodes'].append({'id': 'node-' + name, 'title': name,
            'responsibility': 'fixture responsibility ' + name,
            'implementationStatus': 'planned' if planning else 'unknown',
            'interfaces': [], 'evidenceIds': ['goal-process']})
    if not planning:
        graph['evidence'].insert(0, {'id': 'code-flow', 'kind': 'code', 'reason': 'real fixture source',
            'path': 'flow.py', 'codeRepoId': rid, 'codeRevision': revision, 'lineStart': 1, 'lineEnd': 4})
    graph['processes'] = [{'id': 'process-ABC', 'title': 'Expected fixture process', 'kind': 'expected',
        'evidenceIds': ['goal-process'], 'steps': [{'id': 'step-' + n, 'nodeId': 'node-' + n,
        'title': n, 'inputs': [], 'outputs': [], 'condition': '', 'branches': [],
        'nextStepIds': [] if n == 'C' else ['step-' + chr(ord(n)+1)], 'allowedFailures': [],
        'evidenceIds': ['goal-process']} for n in 'ABC']}]
    coverage = {'scope': 'all', **{k: sorted(o['id'] for o in graph[k])
                for k in ('nodes', 'edges', 'processes', 'evidence')}}
    review = {'draftId': 'draft-fixture', 'draftRevision': 1, 'workspaceId': 'workspace-fixture',
        'mapId': 'map-fixture', 'expectedMapRevision': None, 'codeRepoId': rid,
        'codeRevision': revision, 'proposalId': 'proposal-fixture',
        'actor': 'TEST_ONLY_SIMULATED_HUMAN', 'reason': 'TEST ONLY fixture',
        'beforeGraph': None, 'afterGraph': deepcopy(graph), 'appliedOperations': [],
        'rejectedCandidates': [], 'reviewCoverage': coverage,
        'limits': ['TEST_ONLY_SIMULATED_HUMAN'], 'verifyCode': False, 'origin': 'manual'}
    preview_digest = digest(review)
    review.update(reviewId='review-fixture', decision='accept', reviewedAt=1,
        previewDigest=preview_digest, verifiedCodeRevision=None,
        actorIdentity='local_operator_declaration')
    packet = {'schemaVersion': 'architecture_version_v1', 'mapId': 'map-fixture',
        'mapRevision': None, 'codeRepoId': rid, 'codeRevision': revision, 'verifiedCodeRevision': None,
        'status': 'confirmed_design' if planning else 'confirmed_cognition',
        'graph': graph, 'reviewCoverage': coverage,
        'limits': ['TEST_ONLY_SIMULATED_HUMAN', '核查仅适用于列明覆盖；不证明运行时全流程'],
        'review': review, 'origin': 'manual',
        'confirmation': {k: {'confirmed': coverage[k], 'unconfirmed': []}
                         for k in ('nodes', 'edges', 'processes', 'evidence')}}
    packet['mapRevision'] = digest({k: packet[k] for k in SEMANTIC})
    return packet


def publish_fixture(architecture_repo, packet):
    path = architecture_repo / 'versions' / packet['mapId'] / (packet['mapRevision'][7:] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':')), encoding='utf-8')
    sha = commit(architecture_repo, 'TEST ONLY immutable architecture fixture')
    return {'version': packet, 'provenance': {'mapSourceRevision': sha, 'sourceKind': 'git_commit'}}


def create(root):
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('fixture output must not already exist')
    parent = root.parent
    while not parent.exists():
        parent = parent.parent
    probe = subprocess.run(['git','-C',str(parent),'rev-parse','--show-toplevel'],capture_output=True,
        env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')})
    if probe.returncode == 0:
        raise ValueError('fixture must not be created inside an existing Git checkout')
    root.mkdir(parents=True)
    (root / '.projectmind-test-fixture').write_text('TEST ONLY isolated Git fixture\n')
    code, arch = root/'client-one'/'code', root/'client-one'/'architecture'
    init(code, 'https://example.invalid/archloop/code.git')
    (code/'flow.py').write_text(GOOD)
    (code/'check_flow.py').write_text(TEST)
    good = commit(code, 'expected process')
    (code/'flow.py').write_text(BAD)
    bad = commit(code, 'observed bypass C')
    init(arch, 'https://example.invalid/archloop/architecture.git')
    packet = version_packet(code, bad)
    envelope = publish_fixture(arch, packet)
    planning = publish_fixture(arch, version_packet(None, None, planning=True))
    second_code, second_arch = root/'client-two'/'code', root/'client-two'/'architecture'
    second_code.parent.mkdir(parents=True)
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    subprocess.run(['git', 'clone', '--no-hardlinks', '-q', str(code), str(second_code)], check=True,env=env)
    subprocess.run(['git', 'clone', '--no-hardlinks', '-q', str(arch), str(second_arch)], check=True,env=env)
    git(second_code, 'remote', 'set-url', 'origin', source_locator(code))
    git(second_arch, 'remote', 'set-url', 'origin', source_locator(arch))
    wrong = root/'wrong-client'/'code'
    init(wrong, 'https://example.invalid/other/code.git')
    (wrong/'flow.py').write_text('different repository\n'); commit(wrong, 'unrelated')
    return {'root': str(root), 'code': str(code), 'architecture': str(arch),
            'secondCode': str(second_code), 'secondArchitecture': str(second_arch),
            'wrongCode': str(wrong), 'goodRevision': good, 'badRevision': bad,
            'versionEnvelope': envelope, 'planningEnvelope': planning}
