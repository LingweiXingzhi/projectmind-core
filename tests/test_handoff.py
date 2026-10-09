import copy
import json
import os
import subprocess
import tempfile
import unittest
import threading
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from types import SimpleNamespace
from http import HTTPStatus
from extension_host import ExtensionHost, ExtensionError
from extensions.handoff.handoff import build_handoff, HandoffError, render_markdown, render_ai_context

ROOT = Path(__file__).resolve().parents[1]


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / 'docs/standards/MVP_CONTRACT_EXAMPLE.json').read_text())

    def build(self, **overrides):
        values = dict(snapshot=self.fixture['snapshot'], source_locator=self.fixture['sourceLocator'],
                      comparison=self.fixture['comparison'], ai_candidates=[self.fixture['aiCandidate']])
        values.update(overrides)
        return build_handoff(**values)

    def test_complete_and_no_mutation(self):
        before = copy.deepcopy(self.fixture)
        result = self.build()
        self.assertEqual(result['mapRevision'], 'UNKNOWN')
        self.assertEqual(result['aiCandidates'][0], self.fixture['aiCandidate'])
        self.assertEqual(result['sourceLocator'], self.fixture['sourceLocator'])
        self.assertEqual(result['reviewCandidates'][0]['nodeId'], 'entry-feature')
        result['aiCandidates'][0]['explanation']['unknowns'].append('changed')
        self.assertEqual(self.fixture, before)

    def test_without_optional_inputs_does_not_claim_no_changes(self):
        result = self.build(comparison=None, ai_candidates=None)
        self.assertEqual(result['changes'], [])
        self.assertTrue(any('不表示代码没有变化' in s for s in result['unknowns']))

    def test_invalid_source_and_comparison(self):
        with self.assertRaises(HandoffError):
            self.build(source_locator={'kind': 'git_remote', 'value': ' '})
        self.fixture['comparison']['targetRevision'] = '2' * 40
        with self.assertRaises(HandoffError):
            self.build()

    def test_reject_wrong_ai_version_and_fabricated_evidence(self):
        candidate = copy.deepcopy(self.fixture['aiCandidate'])
        candidate['targetRevision'] = '2' * 40
        with self.assertRaises(HandoffError):
            self.build(ai_candidates=[candidate])
        candidate = copy.deepcopy(self.fixture['aiCandidate'])
        candidate['explanation']['evidencePaths'] = ['invented.py']
        with self.assertRaises(HandoffError):
            self.build(ai_candidates=[candidate])

    def test_main_revision_ignores_inherited_git_environment(self):
        # R35-D1: resolving the handoff draft's origin/main must never follow
        # an inherited GIT_DIR / GIT_WORK_TREE / GIT_COMMON_DIR into a
        # different real repository (there it would read that repository's
        # origin/main, or fail outright).
        from extensions.handoff.extension import main_revision
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'T'], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 't@example.invalid'], check=True)
            (repo / 'a.py').write_text('x = 1\n', encoding='utf-8')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'base'], check=True)
            head = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                                  capture_output=True, check=True).stdout.decode().strip()
            subprocess.run(['git', '-C', str(repo), 'update-ref',
                            'refs/remotes/origin/main', head], check=True)
            other = Path(tmp) / 'other'
            other.mkdir()
            subprocess.run(['git', 'init', '-q', str(other)], check=True)
            self.assertEqual(main_revision(SimpleNamespace(repo=repo)), head)
            with patch.dict(os.environ, {'GIT_DIR': str(other / '.git'),
                                         'GIT_WORK_TREE': str(other),
                                         'GIT_COMMON_DIR': str(other / '.git')}):
                self.assertEqual(main_revision(SimpleNamespace(repo=repo)), head)

    def test_local_path_and_missing_evidence_visible(self):
        self.fixture['snapshot']['nodes'][0]['evidence'][0]['existsAtCommit'] = False
        result = self.build(source_locator={'kind': 'local_path', 'value': '/example/repo'})
        self.assertTrue(any('接收者电脑' in s for s in result['unknowns']))
        self.assertTrue(any('src/entry.py' in s for s in result['unknowns']))

    def test_markdown_preserves_replay_information(self):
        text = render_markdown(self.build())
        self.assertGreater(len(text.splitlines()), 20)
        for value in ['example://contract-fixture', '1' * 40, '0' * 40, 'UNKNOWN',
                      'entry-feature', 'src/entry.py', '运行行为未验证', '下一步']:
            self.assertIn(value, text)

    def test_markdown_is_readable_and_escapes_source_markup(self):
        self.fixture['snapshot']['nodes'][0]['title'] = '<script>x</script>|[link](x)\nnext'
        text = render_markdown(self.build())
        self.assertNotIn('```json', text)
        self.assertNotIn('<script>', text)
        self.assertIn('共 1 个变化文件', text)
        self.assertIn('| 新增', render_markdown(self.build(comparison={**self.fixture['comparison'], 'changes': [{'code': 'A', 'path': 'new.py'}]}, ai_candidates=[])))
        self.assertIn('&lt;script&gt;', text)
        self.assertIn('\\|', text)

    def test_markdown_distinguishes_missing_comparison_and_unmapped_changes(self):
        text = render_markdown(self.build(comparison=None, ai_candidates=[]))
        self.assertIn('不能据此判断代码是否变化', text)
        comparison = {**self.fixture['comparison'], 'reviewCandidates': []}
        text = render_markdown(self.build(comparison=comparison, ai_candidates=[]))
        self.assertIn('新增文件可能尚未登记', text)

    def test_actual_host_discovers_extension_and_adapter_rejects_stale_page(self):
        context = SimpleNamespace(snapshot=lambda: self.fixture['snapshot'],
                                  compare=lambda base, target: self.fixture['comparison'])
        host = ExtensionHost(ROOT / 'extensions', context)
        self.assertIn('handoff', host.loaded)
        payload = {'expectedRevision': self.fixture['snapshot']['revision'],
                   'sourceLocator': self.fixture['sourceLocator'],
                   'baseRevision': self.fixture['comparison']['baseRevision'],
                   'aiCandidates': [self.fixture['aiCandidate']]}
        result = host.run('handoff', 'POST', payload)
        self.assertEqual(result['handoff']['codeRevision'], payload['expectedRevision'])
        payload['expectedRevision'] = '2' * 40
        with self.assertRaises(ExtensionError) as error:
            host.run('handoff', 'POST', payload)
        self.assertEqual(error.exception.status, HTTPStatus.BAD_REQUEST)

    def test_unmapped_changes_include_only_changes_without_declared_paths(self):
        comparison = {**self.fixture['comparison'], 'changes': [
            {'code': 'M', 'path': 'src/entry.py'},
            {'code': 'A', 'path': 'extensions/new.py'},
            {'code': 'R100', 'oldPath': 'src/entry.py', 'path': 'renamed.py'},
            {'code': 'D', 'path': 'unused.py'}]}
        result = self.build(comparison=comparison)
        self.assertEqual([c['path'] for c in result['unmappedChanges']], ['extensions/new.py', 'unused.py'])
        self.assertIn('地图未覆盖的变化', render_markdown(result))
        self.assertTrue(any('未匹配' in v for v in result['unknowns']))
        self.assertNotIn('unmappedChanges', self.build(comparison=None, ai_candidates=[]))
        self.assertEqual(self.build(comparison={**comparison, 'changes': []}, ai_candidates=[])['unmappedChanges'], [])

    def test_ai_context_keeps_versions_limits_and_work_notes(self):
        context = render_ai_context(self.build(work_notes={'nextSteps': '检查扩展边界'}))
        for text in ['0' * 40, '1' * 40, 'UNKNOWN', 'src/entry.py',
                     '不是权限授权', '检查扩展边界', '尚未独立核实']:
            self.assertIn(text, context)

    def test_main_resolves_local_tracking_ref_each_time(self):
        import tempfile
        import subprocess
        from extensions.handoff.extension import handle
        with tempfile.TemporaryDirectory() as folder:
            def git(*args):
                return subprocess.check_output(['git', '-C', folder, *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-b', 'main')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-m', 'base')
            first = git('rev-parse', 'HEAD')
            context = SimpleNamespace(repo=Path(folder), snapshot=lambda: self.fixture['snapshot'],
                                      compare=lambda base, target: {**self.fixture['comparison'], 'baseRevision': base})
            self.assertIsNone(handle(context, 'GET', {})['mainRevision'])
            with self.assertRaises(ExtensionError):
                handle(context, 'POST', {'expectedRevision': self.fixture['snapshot']['revision'],
                       'sourceLocator': self.fixture['sourceLocator'], 'comparisonMode': 'main'})
            git('update-ref', 'refs/remotes/origin/main', first)
            payload = {'expectedRevision': self.fixture['snapshot']['revision'],
                       'sourceLocator': self.fixture['sourceLocator'], 'comparisonMode': 'main'}
            self.assertEqual(handle(context, 'POST', payload)['handoff']['baseRevision'], first)
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-m', 'next')
            second = git('rev-parse', 'HEAD')
            git('update-ref', 'refs/remotes/origin/main', second)
            self.assertEqual(handle(context, 'POST', payload)['handoff']['baseRevision'], second)
            self.assertEqual(handle(context, 'GET', {})['mainRevision'], second)
            payload['baseRevision'] = first
            with self.assertRaises(ExtensionError):
                handle(context, 'POST', payload)

    def test_notes_are_separate_unverified_records_and_validate_types(self):
        notes = {'completed': '导出草稿', 'nextSteps': '<script>检查证据</script>'}
        result = self.build(work_notes=notes)
        self.assertEqual(result['workNotes']['status'], 'contributor_notes')
        self.assertIn('尚未独立核实', render_markdown(result))
        self.assertNotIn('<script>', render_markdown(result))
        self.assertNotIn('status', notes)
        for value in ([], {'completed': []}, {'nextSteps': 'x' * 4001}, {'unexpected': 'x'}):
            with self.assertRaises(HandoffError):
                self.build(work_notes=value)

    def test_reject_malformed_ai_lists_and_short_baseline(self):
        from extensions.handoff.extension import handle
        for key in ('observations', 'possibleEffects', 'unknowns', 'evidencePaths'):
            candidate = copy.deepcopy(self.fixture['aiCandidate'])
            candidate['explanation'][key] = 'invalid list'
            with self.assertRaises(HandoffError):
                self.build(ai_candidates=[candidate])
        context = SimpleNamespace(snapshot=lambda: self.fixture['snapshot'],
                                 compare=lambda *args: self.fail('invalid baseline reached compare'))
        with self.assertRaises(ExtensionError) as error:
            handle(context, 'POST', {'expectedRevision': self.fixture['snapshot']['revision'],
                   'sourceLocator': self.fixture['sourceLocator'], 'baseRevision': '1234'})
        self.assertEqual(error.exception.status, HTTPStatus.BAD_REQUEST)

    def test_live_http_page_generate_and_stale_error(self):
        from app import make_handler, MAP_PATH
        # Isolation (B0-01): bind a disposable repo so extension stores and
        # git refs never touch the real checkout's shared databases.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        repo = Path(folder.name) / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.com',
                        'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin',
                        'https://github.com/LingweiXingzhi/projectmind-core.git'], check=True)
        head = subprocess.check_output(
            ['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip()
        subprocess.run(['git', '-C', str(repo), 'update-ref',
                        'refs/remotes/origin/main', head], check=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(repo, MAP_PATH))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urlopen(base + '/ext/handoff') as response:
                self.assertIn('下载 Markdown', response.read().decode())
            with urlopen(base + '/api/snapshot') as response:
                snapshot = json.load(response)
            payload = {'expectedRevision': snapshot['revision'],
                       'sourceLocator': {'kind': 'git_remote', 'value': 'https://github.com/LingweiXingzhi/projectmind-core'}}
            def send():
                return urlopen(Request(base + '/api/extensions/handoff',
                                       data=json.dumps(payload).encode(),
                                       headers={'Content-Type': 'application/json'}, method='POST'))
            with send() as response:
                result = json.load(response)
            self.assertEqual(result['handoff']['codeRevision'], snapshot['revision'])
            self.assertIn(snapshot['revision'], result['markdown'])
            payload['expectedRevision'] = '2' * 40
            with self.assertRaises(HTTPError) as error:
                send()
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        finally:
            server.shutdown()
            thread.join(2)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
