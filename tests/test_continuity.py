import base64
import copy
import hashlib
import io
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from extensions.continuity.extension import handle
from extensions.continuity.inspection import canonical_remote, inspect, capture, read_evidence
from extensions.continuity.model import validate_packet, ai_context, export_packet, ready_missing
from extensions.continuity.store import repository_store
from extensions.worklog.store import repository_store as log_store
from extension_host import ExtensionError
from app import make_handler, build_snapshot, compare_commits

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'https://github.com/example/test-project'


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        self.git('remote', 'add', 'origin', REMOTE + '.git')
        (self.repo / 'feature.py').write_text('def feature():\n    return 1\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.revision = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('update-ref', 'refs/remotes/origin/main', self.revision)
        self.map = Path(self.tmp.name) / 'map.json'
        self.map.write_text(json.dumps({'note': '人工演示图，未知适用版本', 'nodes': [{'id': 'feature', 'title': '功能', 'summary': '人工职责', 'entryPoint': 'feature.py', 'position': {'x': 0, 'y': 0}, 'evidence': [{'path': 'feature.py', 'reason': '实现'}]}], 'edges': []}))
        self.context = SimpleNamespace(repo=self.repo, map_path=self.map,
                                       snapshot=lambda: build_snapshot(self.repo, self.map),
                                       compare=lambda a, b: compare_commits(self.repo, self.map, a, b))
        self.job = {'title': '恢复接口开发', 'goal': '完成返回值验证', 'stopPoint': '实现已提交，尚未验证',
                    'nextAction': '先读取 feature.py', 'acceptance': '返回值验证通过',
                    'runInstructions': 'python -m unittest', 'completed': '接口首版', 'owner': 'Tester'}
        self.payload = {'task': self.job, 'sourceLocator': {'kind': 'git_remote', 'value': REMOTE},
                        'comparisonMode': 'main', 'expectedRevision': self.revision,
                        'checklist': [{'id': 'run-test', 'text': '验证返回值', 'state': 'pending', 'note': '', 'evidence': ''}], 'scope': ['feature']}

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL)

    def create(self, **values):
        return handle(self.context, 'POST', {'action': 'create', **self.payload, **values})['record']

    def event(self, record, kind, **extra):
        return handle(self.context, 'POST', {'action': 'event', 'id': record['id'], 'expectedVersion': record['version'],
                                            'actor': 'Receiver', 'kind': kind, **extra})['record']

    def test_full_sender_receiver_feedback_completion_and_history(self):
        r = self.create()
        self.assertEqual(r['state'], 'draft')
        r = self.event(r, 'ready')
        self.assertEqual(r['state'], 'ready')
        r = self.event(r, 'receive')
        with self.assertRaises(ExtensionError): self.event(r, 'start')
        review = {key: True for key in ('materials', 'environment', 'understanding', 'nextStep')}
        r = self.event(r, 'start', review=review)
        self.assertEqual(r['review']['status'], 'participant_report')
        r = self.event(r, 'question', note='返回值约定在哪里？')
        r = self.event(r, 'note', note='接口约定位于 feature.py', origin='ai')
        self.assertEqual(r['events'][-1]['status'], 'ai_candidate')
        r = self.event(r, 'block', note='缺少运行环境')
        self.assertEqual(r['state'], 'blocked')
        r = self.event(r, 'resume', note='已恢复环境', review=review)
        with self.assertRaises(ExtensionError): self.event(r, 'complete', note='已完成', evidence='python -m unittest 通过')
        r = handle(self.context, 'POST', {'action': 'update', 'id': r['id'], 'expectedVersion': r['version'],
                                         'checklist': [{**r['checklist'][0], 'state': 'done', 'note': '通过', 'evidence': '实际输出 1'}]})['record']
        r = self.event(r, 'complete', note='完成验证', evidence='实际输出 1')
        self.assertEqual(r['state'], 'completed')
        store = repository_store(self.repo)
        self.assertEqual(store.get(r['id']), r)
        self.assertEqual(len(store.history(r['id'])), r['version'])
        with self.assertRaises(ExtensionError):
            handle(self.context, 'POST', {'action': 'update', 'id': r['id'], 'expectedVersion': r['version']})

    def test_direct_claim_keeps_unchecked_reviews_unverified(self):
        r = self.create()
        r = self.event(r, 'claim', review={'materials': True, 'environment': False})
        self.assertEqual(r['state'], 'active')
        self.assertEqual(r['review']['checks'], {'materials': True, 'environment': False})
        self.assertNotIn('nextStep', r['review']['checks'])
        self.assertEqual(r['review']['status'], 'participant_report')
        other = self.create()
        with self.assertRaises(ExtensionError): self.event(other, 'claim', review={'environment': 'yes'})

    def test_finish_session_preserves_open_items_and_new_entry_point_on_import(self):
        r = self.event(self.create(), 'claim')
        before = copy.deepcopy(r['checklist'])
        r = self.event(r, 'finish_session', note='已读资料，环境仍未准备',
                       stopPoint='等待安装运行环境', nextAction='先安装依赖，再验证返回值')
        self.assertEqual(r['state'], 'ready')
        self.assertEqual(r['checklist'], before)
        self.assertEqual(r['task']['stopPoint'], '等待安装运行环境')
        exported = handle(self.context, 'GET', {'action': 'export', 'id': r['id']})
        self.assertIn('先安装依赖，再验证返回值', exported['aiContext'])
        imported = handle(self.context, 'POST', {'action': 'import_packet', 'packet': exported['packet']})['record']
        self.assertEqual(imported['state'], 'receiving')
        self.assertEqual(imported['task'], r['task'])
        self.assertEqual(imported['checklist'], before)
        self.assertEqual(imported['importedHistory'][-1]['nextAction'], r['task']['nextAction'])
        self.assertEqual(r['handoff']['mapRevision'], 'UNKNOWN')
        self.assertEqual(r['handoff'], exported['legacyHandoff'])
        again = self.event(r, 'claim')
        self.assertEqual(again['state'], 'active')

    def test_session_end_rejects_missing_entry_point_atomically_and_stale_writes(self):
        r = self.event(self.create(), 'claim')
        with self.assertRaises(ExtensionError): self.event(r, 'finish_session', note='暂停', stopPoint='环境待准备')
        self.assertEqual(repository_store(self.repo).get(r['id']), r)
        updated = self.event(r, 'note', note='准备环境')
        with self.assertRaises(ExtensionError) as error:
            self.event(r, 'finish_session', note='暂停', stopPoint='环境待准备', nextAction='安装依赖')
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(repository_store(self.repo).get(r['id']), updated)

    def test_problem_impact_and_completion_are_distinct(self):
        r = self.event(self.create(), 'claim')
        r = self.event(r, 'question', note='参数用途需要确认')
        self.assertEqual(r['state'], 'active')
        r = self.event(r, 'block', note='缺少必要凭据，无法运行')
        self.assertEqual(r['state'], 'blocked')
        with self.assertRaises(ExtensionError): self.event(r, 'claim')
        r = self.event(r, 'claim', note='改用独立测试环境，可继续验证')
        with self.assertRaises(ExtensionError) as error:
            self.event(r, 'complete', note='完成', evidence='运行结果')
        self.assertIn('验证返回值', str(error.exception))
        self.assertIn('结束本次接手', str(error.exception))
        r = handle(self.context, 'POST', {'action': 'update', 'id': r['id'], 'expectedVersion': r['version'],
                    'checklist': [{**r['checklist'][0], 'state': 'done'}]})['record']
        with self.assertRaises(ExtensionError): self.event(r, 'complete', note='完成')
        r = self.event(r, 'complete', note='已验证返回值', evidence='实际返回 1')
        self.assertEqual(r['state'], 'completed')

    def test_old_export_import_preserves_feedback_and_handoff(self):
        # A synthetic old-format record, independent of the user's local data.
        r = self.event(self.create(), 'ready', note='旧版发送方记录')
        r = self.event(r, 'receive', note='旧版接收记录')
        packet = export_packet(r)
        imported = handle(self.context, 'POST', {'action': 'import_packet', 'packet': packet})['record']
        imported = self.event(imported, 'claim')
        self.assertEqual([e['kind'] for e in imported['importedHistory']], ['ready', 'receive'])
        exported = handle(self.context, 'GET', {'action': 'export', 'id': imported['id']})['packet']
        self.assertEqual(exported['format'], packet['format'])
        self.assertEqual(exported['record']['handoff'], packet['record']['handoff'])

    def test_real_http_quick_actions_session_end_and_reimport(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.repo, self.map))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/api/extensions/continuity'
        def post(action, **values):
            request = Request(base, data=json.dumps({'action': action, **values}).encode(),
                              headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        def event(record, kind, **values):
            return post('event', id=record['id'], expectedVersion=record['version'],
                        actor='HTTP Receiver', kind=kind, **values)['record']
        try:
            r = post('create', **self.payload)['record']
            r = event(r, 'claim')
            self.assertEqual(r['review']['checks'], {})
            r = event(r, 'question', note='确认输入范围')
            self.assertEqual(r['state'], 'active')
            r = event(r, 'block', note='等待测试数据')
            self.assertEqual(r['state'], 'blocked')
            with self.assertRaises(HTTPError) as error:
                event(r, 'complete', note='完成', evidence='尚未执行')
            self.assertEqual(error.exception.code, 400)
            self.assertIn('验证返回值', json.load(error.exception)['error'])
            error.exception.close()
            r = event(r, 'finish_session', note='已读资料，测试稍后继续',
                      stopPoint='等待测试数据', nextAction='准备数据并运行返回值验证')
            self.assertEqual(r['state'], 'ready')
            self.assertEqual(r['checklist'][0]['state'], 'pending')
            with urlopen(base + '?action=export&id=' + r['id']) as response:
                exported = json.load(response)
            self.assertIn('准备数据并运行返回值验证', exported['aiContext'])
            imported = post('import_packet', packet=exported['packet'])['record']
            self.assertEqual(imported['state'], 'receiving')
            self.assertEqual(imported['task'], r['task'])
            self.assertEqual(imported['importedHistory'][-1]['kind'], 'finish_session')
        finally:
            server.shutdown(); thread.join(2); server.server_close()

    def test_task_readiness_not_equals_acceptance(self):
        r = self.create(task={'title': '只有标题'})
        self.assertEqual(len(ready_missing(r)), 4)
        with self.assertRaises(ExtensionError): self.event(r, 'ready')
        r = self.create()
        with self.assertRaises(ExtensionError): self.event(r, 'complete', note='完成', evidence='假设')
        r = self.event(r, 'ready')
        r = handle(self.context, 'POST', {'action': 'update', 'id': r['id'], 'expectedVersion': r['version'],
                                        'task': {**r['task'], 'nextAction': '第一步已修改'}})['record']
        self.assertEqual(r['state'], 'draft')

    def test_logs_are_fixed_snapshots_and_original_untouched(self):
        logs = log_store(self.repo)
        meta = dict(category='decision', date='2026-10-02', title='方案依据', body='已有探索结果', author='AI', origin='ai')
        entry = logs.save(meta, self.revision)
        r = self.create(logIds=[entry['id']])
        self.assertEqual(r['logs'][0]['status'], 'ai_candidate')
        self.assertEqual(logs.get(entry['id']), entry)
        logs.save({**meta, 'id': entry['id'], 'expectedVersion': 1, 'body': '新的判断'}, self.revision)
        self.assertEqual(repository_store(self.repo).get(r['id'])['logs'][0]['body'], '已有探索结果')
        self.assertEqual(inspect(self.context, r)['logs'][0]['state'], 'updated')
        export = export_packet(r)
        other = repository_store(self.repo).import_record(export)
        self.assertEqual(other['logs'][0]['version'], 1)
        self.assertEqual(len(logs.listing()), 1)

    def test_attachment_roundtrip_missing_and_tampered_hash(self):
        logs = log_store(self.repo)
        raw = '# 工作证据\n原件内容'.encode()
        start = logs.start(dict(category='daily', date='2026-10-02', title='文件记录', filename='work.md', size=len(raw)))
        logs.chunk({'uploadId': start['uploadId'], 'offset': 0, 'base64': base64.b64encode(raw).decode()})
        e = logs.finish(start, self.revision)
        r = self.create(logIds=[e['id']], includeAttachments=True)
        f = r['logs'][0]['attachment']
        self.assertEqual(base64.b64decode(f['base64']), raw)
        result = validate_packet(export_packet(r))
        self.assertTrue(result['logs'][0]['attachment']['included'])
        bad = export_packet(r)
        bad['record']['logs'][0]['attachment']['sha256'] = '0' * 64
        with self.assertRaises(ExtensionError): validate_packet(bad)
        missing = self.create(logIds=[e['id']])
        self.assertFalse(missing['logs'][0]['attachment']['included'])
        self.assertNotIn('base64', missing['logs'][0]['attachment'])

    def test_git_checks_renames_changes_source_mismatch_and_worktree(self):
        r = self.create()
        self.assertEqual(inspect(self.context, r)['revisionState'], 'same')
        self.git('mv', 'feature.py', 'renamed.py')
        self.git('commit', '-qm', 'rename')
        d = inspect(self.context, r)
        self.assertEqual(d['revisionState'], 'different')
        self.assertEqual(d['comparison']['changes'][0]['oldPath'], 'feature.py')
        self.assertEqual(d['comparison']['reviewCandidates'][0]['nodeId'], 'feature')
        self.assertEqual(read_evidence(self.context, r, 'feature.py')['content'], 'def feature():\n    return 1\n')
        (self.repo / 'untracked.txt').write_text('must not be read automatically')
        (self.repo / 'renamed.py').write_text('modified uncommitted')
        d = inspect(self.context, r)
        self.assertEqual(len(d['workspace']['files']), 2)
        self.assertFalse(d['workspace']['diffIncluded'])
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/repo')
        d = inspect(self.context, r)
        self.assertEqual(d['sourceState'], 'address_mismatch')
        self.assertIsNone(d['comparison'])
        with self.assertRaises(ExtensionError): read_evidence(self.context, r, 'feature.py')

    def test_missing_commit_and_map_changed(self):
        r = self.create()
        r['handoff']['codeRevision'] = '0' * 40
        self.assertEqual(inspect(self.context, r)['revisionState'], 'missing')
        model = json.loads(self.map.read_text())
        model['nodes'][0]['summary'] = '新职责'
        self.map.write_text(json.dumps(model))
        self.assertEqual(inspect(self.context, r)['mapState'], 'changed')

    def test_capture_worktree_optional_and_snapshot_refresh(self):
        (self.repo / 'feature.py').write_text('def feature():\n    return 2\n')
        r = self.create(includeWorktreeDiff=True)
        self.assertIn('return 2', r['workspace']['diff'])
        self.assertEqual(r['handoff']['codeRevision'], self.revision)
        r = self.event(r, 'ready')
        self.git('add', '.')
        self.git('commit', '-qm', 'next')
        revision = self.git('rev-parse', 'HEAD').decode().strip()
        updated = handle(self.context, 'POST', {'action': 'refresh_checkpoint', 'id': r['id'], 'expectedVersion': r['version'],
                                              'expectedRevision': revision, 'sourceLocator': r['handoff']['sourceLocator']})['record']
        self.assertEqual(updated['state'], 'draft')
        self.assertEqual(updated['handoff']['codeRevision'], revision)
        old = repository_store(self.repo).history(r['id'])[-1]
        self.assertEqual(old['handoff']['codeRevision'], self.revision)

    def test_legacy_import_json_and_ai_context_preserve_unknowns(self):
        r = self.create()
        legacy = r['handoff']
        imported = repository_store(self.repo).import_record(legacy)
        self.assertEqual(imported['state'], 'receiving')
        self.assertEqual(imported['handoff']['mapRevision'], 'UNKNOWN')
        text = ai_context(imported)
        for value in ('UNKNOWN', self.revision, '不是执行授权', '不得猜测为已执行', 'feature.py'):
            self.assertIn(value, text)
        with self.assertRaises(ExtensionError):
            validate_packet({'status': 'handoff_draft', 'codeRevision': self.revision, 'nodes': 'bad'})
        attack = export_packet(r)
        attack['record']['handoff']['nodes'][0]['evidence'][0]['path'] = '../outside'
        with self.assertRaises(ExtensionError): validate_packet(attack)

    def test_import_events_are_not_local_authority_and_survive_next_export(self):
        r = self.event(self.create(), 'ready', note='已准备')
        imported = repository_store(self.repo).import_record(export_packet(r))
        self.assertEqual(imported['events'], [])
        self.assertEqual(imported['state'], 'receiving')
        self.assertEqual(len(imported['importedHistory']), 1)
        imported = self.event(imported, 'note', note='已读文件')
        twice = repository_store(self.repo).import_record(export_packet(imported))
        self.assertEqual(len(twice['importedHistory']), 2)

    def test_concurrent_write_conflicts_and_followup(self):
        r = self.create()
        outcomes = []
        def write():
            try:
                repository_store(self.repo).event({'id': r['id'], 'expectedVersion': 1, 'kind': 'note', 'actor': 'Tester', 'note': 'progress'})
                outcomes.append('saved')
            except ExtensionError as error: outcomes.append(error.status)
        threads = [threading.Thread(target=write) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertCountEqual(outcomes, ['saved', 409])
        previous = repository_store(self.repo).get(r['id'])
        newer = handle(self.context, 'POST', {'action': 'followup', 'id': previous['id'], 'expectedVersion': previous['version']})['record']
        self.assertEqual(newer['parentId'], r['id'])
        self.assertEqual(newer['state'], 'draft')
        self.assertEqual(repository_store(self.repo).get(r['id']), previous)

    def test_remote_normalization_and_path_validation(self):
        self.assertEqual(canonical_remote('git@github.com:example/test-project.git'), canonical_remote(REMOTE))
        self.assertEqual(canonical_remote('ssh://git@github.com/example/test-project.git'), canonical_remote(REMOTE))
        self.assertIsNone(canonical_remote('https://user:token@github.com/example/repo'))
        self.assertIsNone(canonical_remote('/tmp/project'))
        with self.assertRaises(ExtensionError): self.create(scope=['missing'])
        with self.assertRaises(ExtensionError): self.create(logIds=['missing'])

    def test_real_http_import_chunks_export_and_old_pages_available(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.repo, self.map))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def post(action, **data):
            with urlopen(Request(base + '/api/extensions/continuity', data=json.dumps({'action': action, **data}).encode(), headers={'Content-Type':'application/json'}, method='POST')) as response:
                return json.load(response)
        try:
            for page in ('continuity', 'worklog', 'handoff'):
                with urlopen(base + '/ext/' + page) as response:
                    self.assertEqual(response.status, 200)
            r = post('create', **self.payload)['record']
            with urlopen(base + '/api/extensions/continuity?action=export&id=' + r['id']) as response:
                exported = json.load(response)
            raw = json.dumps(exported['packet'], ensure_ascii=False).encode()
            start = post('import_start', filename='session.json', size=len(raw))
            with self.assertRaises(HTTPError) as error:
                post('import_chunk', uploadId=start['uploadId'], offset=1, base64='YQ==')
            self.assertEqual(error.exception.code, 409)
            error.exception.close()
            for offset in range(0, len(raw), 24576):
                post('import_chunk', uploadId=start['uploadId'], offset=offset, base64=base64.b64encode(raw[offset:offset+24576]).decode())
            imported = post('import_finish', uploadId=start['uploadId'])['record']
            self.assertEqual(imported['state'], 'receiving')
            self.assertEqual(imported['task'], r['task'])
            self.assertEqual(imported['handoff']['codeRevision'], self.revision)
            with urlopen(base + '/api/extensions/continuity?action=inspect&id=' + imported['id']) as response:
                self.assertEqual(json.load(response)['sourceState'], 'address_match')
        finally:
            server.shutdown();thread.join(2);server.server_close()


if __name__ == '__main__': unittest.main()
