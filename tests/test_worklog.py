import base64
import io
import os
import json
import subprocess
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from extension_host import ExtensionError
from extensions.worklog.store import Store, preview, repository_store
from extensions.worklog.extension import handle

ROOT = Path(__file__).resolve().parents[1]


class WorklogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'records.sqlite3'
        self.store = Store(self.path)
        self.meta = dict(category='daily', date='2026-10-02', title='HTTP 验证', body='真实结果与下一步', author='Tester', origin='human')

    def tearDown(self):
        self.folder.cleanup()

    def upload(self, raw, filename='log.md'):
        start = self.store.start({**self.meta, 'filename': filename, 'size': len(raw)})
        for offset in range(0, len(raw), 24576):
            self.store.chunk({'uploadId': start['uploadId'], 'offset': offset,
                              'base64': base64.b64encode(raw[offset:offset + 24576]).decode()})
        return start

    def test_d01_explicit_repo_wins_over_inherited_git_env(self):
        # D-01 (MEDIUM): an inherited GIT_DIR pointing at another repository
        # used to redirect D storage there (repo identity isolation broken).
        # The explicit repo argument must always win.
        repo_a = Path(self.folder.name) / 'repo-a'
        repo_b = Path(self.folder.name) / 'repo-b'
        for repo in (repo_a, repo_b):
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True,
                           capture_output=True)
        with patch.dict(os.environ, {'GIT_DIR': str(repo_b / '.git')}):
            store = repository_store(repo_a)
        self.assertIn('repo-a', str(store.path))
        self.assertNotIn('repo-b', str(store.path))
        self.assertIn('projectmind-worklog', str(store.path))

    def test_persistence_history_conflict_and_ai_state(self):
        e = self.store.save(self.meta, '1' * 40)
        second = Store(self.path)
        self.assertEqual(second.get(e['id']), e)
        saved = second.save({**self.meta, 'id': e['id'], 'expectedVersion': 1, 'origin': 'ai'}, '2' * 40)
        self.assertEqual(saved['status'], 'ai_candidate')
        with self.assertRaises(ExtensionError) as exc:
            self.store.save({**self.meta, 'id': e['id'], 'expectedVersion': 1}, '3' * 40)
        self.assertEqual(exc.exception.status, 409)
        self.assertEqual([v['version'] for v in second.history(e['id'])], [2, 1])
        self.assertEqual(second.get(e['id'])['codeRevision'], '2' * 40)

    def test_concurrent_writers_only_one_wins(self):
        e = self.store.save(self.meta, '1' * 40)
        outcomes = []
        def write():
            try:
                self.store.save({**self.meta, 'id': e['id'], 'expectedVersion': 1}, '2' * 40)
                outcomes.append('saved')
            except ExtensionError as error:
                outcomes.append(error.status)
        threads = [threading.Thread(target=write) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertCountEqual(outcomes, ['saved', 409])

    def test_chunk_order_finish_and_original_backup(self):
        raw = ('# 决策\n\n' + '测试\n' * 12000).encode()
        start = self.store.start({**self.meta, 'filename': 'decision.md', 'size': len(raw)})
        with self.assertRaises(ExtensionError):
            self.store.finish(start, '1' * 40)
        with self.assertRaises(ExtensionError):
            self.store.chunk({**start, 'offset': 5, 'base64': 'YWJj'})
        self.store.cancel(start['uploadId'])
        start = self.upload(raw)
        e = self.store.finish(start, '1' * 40)
        f = Store(self.path).file(e['attachment']['id'])
        self.assertEqual(base64.b64decode(f['base64']), raw)
        self.assertIn('# 决策', f['preview'])
        saved = self.store.save({**self.meta, 'id': e['id'], 'expectedVersion': 1}, '2' * 40)
        self.assertEqual(saved['attachment'], e['attachment'])
        backup = self.store.backup()
        self.assertEqual(len(backup['history']), 2)
        self.assertEqual(base64.b64decode(backup['files'][0]['base64']), raw)
        with self.assertRaises(ExtensionError):
            self.store.finish(start, '1' * 40)

    def test_docx_extracts_paragraphs_and_keeps_original(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>验证结果</w:t></w:r></w:p><w:p><w:r><w:t>下一步</w:t></w:r></w:p></w:body></w:document>')
        raw = stream.getvalue()
        e = self.store.finish(self.upload(raw, 'work.docx'), '1' * 40)
        f = self.store.file(e['attachment']['id'])
        self.assertEqual(f['preview'], '验证结果\n下一步')
        self.assertEqual(base64.b64decode(f['base64']), raw)

    def test_pdf_and_document_errors(self):
        self.assertEqual(preview(b'%PDF-1.4\n%%EOF', 'pdf')[0], '')
        for raw, kind in [(b'not pdf', 'pdf'), (b'PKbroken', 'docx'), (b'not doc', 'doc'), (b'\xff', 'md')]:
            with self.assertRaises(ExtensionError): preview(raw, kind)
        with patch('extensions.worklog.store.shutil.which', return_value=None):
            with self.assertRaises(ExtensionError) as exc:
                preview(bytes.fromhex('d0cf11e0a1b11ae1'), 'doc')
            self.assertIn('DOCX', str(exc.exception))

    def test_doc_conversion_adapter(self):
        with patch('extensions.worklog.store.shutil.which', return_value='/usr/bin/textutil'), patch('extensions.worklog.store.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='工作结果'.encode())) as call:
            self.assertEqual(preview(bytes.fromhex('d0cf11e0a1b11ae1') + b'test', 'doc')[0], '工作结果')
            self.assertIn('-stdout', call.call_args.args[0])

    def test_validation_and_repository_isolation(self):
        for data in [{**self.meta, 'category': 'x'}, {**self.meta, 'date': 'wrong'}, {**self.meta, 'origin': 'confirmed'}, {**self.meta, 'body': 'x' * 15001}]:
            with self.assertRaises(ExtensionError): self.store.save(data, '1' * 40)
        for name, size in [('a.exe', 10), ('a.md', 0), ('a.md', True), ('a.md', 11 * 1024 * 1024)]:
            with self.assertRaises(ExtensionError): self.store.start({**self.meta, 'filename': name, 'size': size})
        with self.assertRaises(ExtensionError): self.store.get('../../file')
        repos = []
        for name in ('one', 'two'):
            repo = Path(self.folder.name) / name
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            repos.append(repository_store(repo))
        repos[0].save(self.meta, '1' * 40)
        self.assertEqual(repos[1].listing(), [])
        self.assertIn('.git', str(repos[0].path))

    def test_real_http_create_import_history_and_conflict(self):
        from app import make_handler, MAP_PATH
        repo = Path(self.folder.name) / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(repo, MAP_PATH))
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def post(action, **data):
            with urlopen(Request(base + '/api/extensions/worklog', data=json.dumps({'action': action, **data}).encode(), headers={'Content-Type': 'application/json'}, method='POST')) as r:
                return json.load(r)
        try:
            with urlopen(base + '/ext/worklog') as r:
                self.assertIn('每日工作日志', r.read().decode())
            e = post('save', **self.meta)['entry']
            post('save', **self.meta, id=e['id'], expectedVersion=1)
            with self.assertRaises(HTTPError) as exc:
                post('save', **self.meta, id=e['id'], expectedVersion=1)
            self.assertEqual(exc.exception.code, 409)
            exc.exception.close()
            raw = ('# 大文件\n' + '记录' * 18000).encode()
            start = post('import_start', **self.meta, filename='test.md', size=len(raw))
            for offset in range(0, len(raw), 24576):
                post('import_chunk', uploadId=start['uploadId'], offset=offset, base64=base64.b64encode(raw[offset:offset + 24576]).decode())
            imported = post('import_finish', uploadId=start['uploadId'])['entry']
            with urlopen(base + '/api/extensions/worklog?action=file&id=' + imported['attachment']['id']) as r:
                self.assertEqual(base64.b64decode(json.load(r)['file']['base64']), raw)
            with urlopen(base + '/api/extensions/worklog?action=list') as r:
                self.assertEqual(len(json.load(r)['entries']), 2)
        finally:
            server.shutdown()
            t.join(2)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
