import copy
import json
import unittest
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from types import SimpleNamespace
from http import HTTPStatus
from extension_host import ExtensionHost, ExtensionError
from extensions.handoff.handoff import build_handoff, HandoffError, render_markdown

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

    def test_live_http_page_generate_and_stale_error(self):
        from app import make_handler, MAP_PATH
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(ROOT, MAP_PATH))
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
