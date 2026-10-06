"""D tool self-checks, never product acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from fixture import generate, cleanup, git, tracked, blob, SYMBOLS, IMPORTS


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.m = generate()
        self.repo = Path(self.m['repository'])

    def tearDown(self):
        cleanup(self.m)

    def test_two_actual_commits_and_fixed_changes(self):
        self.assertEqual(git(self.repo, 'rev-list', '--count', 'HEAD').strip(), b'2')
        self.assertEqual(self.m['expectedChanges'], [
            {'status': 'A', 'path': 'pkg/new.py', 'oldPath': None},
            {'status': 'D', 'path': 'pkg/old.py', 'oldPath': None},
            {'status': 'R', 'path': 'pkg/relocated.py', 'oldPath': 'pkg/moved.py'},
            {'status': 'M', 'path': 'pkg/service.py', 'oldPath': None}])
        self.assertRegex(self.m['baseRevision'], r'^[a-f0-9]{40}$')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD').decode().strip(), self.m['targetRevision'])

    def test_isolated_same_name_repositories_no_map_no_execution(self):
        self.assertEqual(self.repo.name, Path(self.m['secondRepository']).name)
        self.assertEqual(Path(git(self.repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip()), self.repo / '.git')
        second = Path(self.m['secondRepository'])
        self.assertEqual(Path(git(second, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip()), second / '.git')
        self.assertNotEqual(self.m['targetRevision'], self.m['secondRevision'])
        self.assertFalse(self.m['facts']['mapJson'])
        self.assertFalse(self.m['facts']['sourceExecuted'])
        self.assertFalse((self.repo / 'EXECUTED_MARKER').exists())
        self.assertNotIn('untracked-only.py', self.m['targetPaths'])
        self.assertNotIn('DIRTY_WORKTREE_CANARY', blob(self.repo, self.m['targetRevision'], 'pkg/service.py').decode())
        self.assertIn('DIRTY_WORKTREE_CANARY', (self.repo / 'pkg/service.py').read_text())
        self.assertEqual(self.m['targetPaths']['outside-link'], '120000')
        self.assertEqual(self.m['targetPaths']['vendor/submodule'], '160000')

    def test_fixed_line_oracles_can_be_checked_without_product_parser(self):
        lines = blob(self.repo, self.m['baseRevision'], 'pkg/service.py').decode().splitlines()
        for name, qualified, kind, start, end, doc in SYMBOLS:
            self.assertIn(('class ' if kind == 'class' else 'def ') + name, lines[start - 1])
            self.assertTrue(lines[end - 1].strip())
        for kind, module, level, name, alias, start, end, status, target in IMPORTS:
            self.assertIn('import', lines[start - 1])
            self.assertEqual(start, end)
        self.assertEqual(len(lines), 32)

    def test_rebuild_same_git_shas(self):
        other = generate()
        try:
            for field in ['baseRevision', 'targetRevision', 'secondRevision', 'expectedChanges']:
                self.assertEqual(self.m[field], other[field])
        finally: cleanup(other)

    def test_cleanup_refuses_redirected_root_and_fixture_parent_repo(self):
        forged = dict(self.m, root=str(self.repo))
        with self.assertRaises(ValueError): cleanup(forged)
        with self.assertRaises(ValueError): generate(self.repo)
        with tempfile.TemporaryDirectory() as folder:
            changed = dict(self.m, repository=folder)
            with self.assertRaises(ValueError): cleanup(changed)
        self.assertTrue(self.repo.exists())


# These adversarial checks exercise D's verdict logic, not A's product.
import contextlib
import copy
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from acceptance import Client, Runner, GROUPS, identity, coverage, load_fixture


class OracleClient:
    def __init__(self, data): self.data, self.calls = data, []
    def success(self, action, params=None, post=None):
        self.calls.append({'action': action, 'params': params, 'post': post})
        return copy.deepcopy(self.data)


class AcceptanceToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.m = generate()
    @classmethod
    def tearDownClass(cls): cleanup(cls.m)

    def test_no_service_never_counts_not_run_as_pass(self):
        runner = Runner(self.m)
        with contextlib.redirect_stdout(io.StringIO()): report = runner.run()
        self.assertEqual(len(report['http']), len(GROUPS))
        self.assertTrue(all(r['status'] == 'NOT_RUN' for r in report['http'] + report['ui']))
        self.assertEqual(report['productAcceptance'], 'NOT_RUN')
        self.assertEqual(report['toolReadiness'], 'READY')
        self.assertFalse(any(r['requests'] for r in report['http']))

    def test_symbols_oracle_rejects_legacy_null_end_stale_and_fabricated(self):
        fields = ['name', 'qualified_name', 'kind', 'start_line', 'end_line', 'docstring']
        data = {'projectId': 'p', 'revision': self.m['baseRevision'], 'path': 'pkg/service.py',
                'status': 'ok', 'parser': 'python_ast_v1', 'warnings': [],
                'symbols': [dict(zip(fields, s)) for s in SYMBOLS]}
        ctx = {'projectId': 'p', 'revision': self.m['baseRevision']}
        Runner(self.m, OracleClient(data)).symbols(ctx, 'pkg/service.py', SYMBOLS)
        for mutation in ['legacy', 'null_end', 'stale_sha', 'fake_name', 'unavailable']:
            bad = copy.deepcopy(data)
            if mutation == 'legacy': bad['parser'] = 'legacy_code_facts'
            if mutation == 'null_end': bad['symbols'][0]['end_line'] = None
            if mutation == 'stale_sha': bad['revision'] = self.m['targetRevision']
            if mutation == 'fake_name': bad['symbols'][0]['qualified_name'] = 'imagined'
            if mutation == 'unavailable': bad.update(status='unavailable', symbols=[])
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                Runner(self.m, OracleClient(bad)).symbols(ctx, 'pkg/service.py', SYMBOLS)

    def test_failure_has_severity_expected_actual_and_reproduction(self):
        data = {'projectId': 'p', 'revision': 'bad', 'path': 'pkg/service.py'}
        runner = Runner(self.m, OracleClient(data))
        runner.base = {'projectId': 'p', 'revision': self.m['baseRevision']}
        with contextlib.redirect_stdout(io.StringIO()): runner.one('D03', runner.check_symbols)
        r = runner.results[0]
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(r['severity'], 'MEDIUM')
        self.assertIn('expected', r['detail']); self.assertIn('actual', r['detail'])
        self.assertTrue(r['requests']); self.assertTrue(r['reproduce'])

    def test_relations_oracle_never_resolves_uncertain_target(self):
        ctx = {'projectId': 'p', 'revision': self.m['baseRevision']}
        data = {**ctx, 'path': 'pkg/service.py', 'status': 'ok', 'dependents': [], 'warnings': [],
                'imports': [{'resolution': {'status': 'ambiguous', 'targetPath': None, 'candidates': ['a.py', 'b.py']}}]}
        Runner(self.m, OracleClient(data)).relations(ctx, 'pkg/service.py')
        data['imports'][0]['resolution']['targetPath'] = 'a.py'
        with self.assertRaises(AssertionError): Runner(self.m, OracleClient(data)).relations(ctx, 'pkg/service.py')
        data['imports'][0]['resolution']['status'] = 'resolved'
        with self.assertRaises(AssertionError): Runner(self.m, OracleClient(data)).relations(ctx, 'pkg/service.py')

    def test_coverage_bad_types_and_wrong_project_never_pass(self):
        data = {'coverage': {'trackedFileCount': len(self.m['basePaths']), 'indexedFileCount': 1,
                             'partial': True, 'skipped': [{'path': 'oversize.py', 'reason': 'limit'}]}}
        coverage(data, self.m['basePaths'])
        for field, value in [('partial', 'false'), ('trackedFileCount', 1), ('indexedFileCount', -1)]:
            bad = copy.deepcopy(data); bad['coverage'][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError): coverage(bad, self.m['basePaths'])
        with self.assertRaises(AssertionError): identity({'projectId': 'other', 'revision': self.m['baseRevision']}, 'p', self.m['baseRevision'])

    def test_manifest_corruption_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'manifest.json'
            altered = copy.deepcopy(self.m); altered['targetPaths']['invented.py'] = '100644'
            p.write_text(json.dumps(altered))
            with self.assertRaises(AssertionError): load_fixture(p)

    def test_actual_urllib_transport_error_contract_and_schema(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                code = 500 if self.path.endswith('crash') else 200 if self.path.endswith('success') else 400
                value = {'schemaVersion': 1} if code == 200 else {'error': {'code': 'BAD_REQUEST', 'message': '拒绝'}}
                self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps(value).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            c = Client('http://127.0.0.1:' + str(server.server_port), timeout=1)
            self.assertEqual(c.success('success')['schemaVersion'], 1)
            self.assertEqual(c.reject('reject')['error']['code'], 'BAD_REQUEST')
            with self.assertRaises(AssertionError): c.reject('crash')
            with self.assertRaises(AssertionError): c.success('reject')
            self.assertEqual(len(c.calls), 4)
            self.assertEqual(c.calls[-1]['httpStatus'], 400)
        finally: server.shutdown(); server.server_close(); thread.join()
        with self.assertRaises(AssertionError): Client('http://127.0.0.1:' + str(server.server_port), timeout=1).success('success')
        with self.assertRaises(ValueError): Client('https://example.com')


if __name__ == '__main__': unittest.main()
