"""Managed shared API can use provider defaults without a local token ceiling."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from archloop.ai_settings import AISettings, SettingsError
from archloop import ai_transport as ai

SCHEMA = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
          'required': ['ok'], 'additionalProperties': False}
ENV = {'PROJECTMIND_AI_UNLIMITED': '1', 'PROJECTMIND_AI_API_KEY': 'SYNTHETIC-NOT-A-REAL-KEY',
       'PROJECTMIND_AI_MODEL': 'fixture-model', 'PROJECTMIND_AI_PROTOCOL': 'chat_completions'}


class UnlimitedSharedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'ai.sqlite3'
        self.settings = AISettings(self.path, shared_from_env=True)

    def test_usage_persists_beyond_former_ceiling_without_reset(self):
        with self.settings._database() as db:
            db.execute('UPDATE settings SET charged=60000, reported=60000 WHERE id=1')
        with patch.dict(os.environ, ENV, clear=True):
            ticket = self.settings.reserve(100000)
            self.settings.settle(ticket, 7000)
            reloaded = AISettings(self.path, shared_from_env=True)
            budget = reloaded.budget()
            self.assertIsNone(budget['tokenLimit'])
            self.assertIsNone(budget['outputLimit'])
            self.assertIsNone(budget['remainingTokens'])
            self.assertEqual(budget['chargedTokens'], 67000)
            self.assertEqual(budget['reportedTokens'], 67000)
            self.assertEqual(budget['pendingRequests'], 0)
            self.assertEqual(reloaded._row()['config'], '{}')

    def test_personal_and_unmanaged_profiles_keep_their_limits(self):
        with patch.dict(os.environ, ENV, clear=True):
            for settings in (AISettings(self.path), self.settings.profile('fixture-account')):
                with self.subTest(personal=settings.personal):
                    self.assertEqual(settings.budget()['tokenLimit'], 50000)
                    with self.assertRaises(SettingsError):
                        settings.reserve(50001)

    def test_all_protocols_omit_wire_output_caps_when_managed_unlimited(self):
        with patch.dict(os.environ, ENV, clear=True), ai.settings_context(self.settings):
            config = ai.ai_config()
            for protocol, host in (('chat_completions', 'gateway.example.invalid'),
                                   ('chat_completions', 'api.openai.com'),
                                   ('responses', 'api.openai.com')):
                with self.subTest(protocol=protocol, host=host):
                    body = ai._request_body(dict(config, protocol=protocol, host=host), 'JSON fixture', {}, 's', SCHEMA)
                    for field in ('max_tokens', 'max_completion_tokens', 'max_output_tokens'):
                        self.assertNotIn(field, body)

    def test_real_worker_receives_complete_json_and_records_usage(self):
        calls = []
        class Provider(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(body)
                limited = any(field in body for field in ('max_tokens', 'max_completion_tokens', 'max_output_tokens'))
                raw = json.dumps({'choices': [{'finish_reason': 'length' if limited else 'stop',
                                              'message': {'content': '{"ok":' if limited else '{"ok":true}'}}],
                                  'usage': {'total_tokens': 37}}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        env = dict(ENV, PROJECTMIND_AI_BASE_URL=f'http://127.0.0.1:{server.server_port}/v1',
                   NO_PROXY='127.0.0.1,localhost')
        # Keep Windows system variables required by a fresh network worker.
        with patch.dict(os.environ, env), ai.settings_context(self.settings):
            value = ai.call_model('Return JSON', {}, 's', SCHEMA, timeout=10)
            self.assertEqual(value, {'ok': True})
            self.assertEqual(self.settings.budget()['reportedTokens'], 37)
            self.assertEqual(self.settings.budget()['chargedTokens'], 37)
            self.assertEqual(self.settings.budget()['pendingRequests'], 0)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('max_tokens', calls[0])
        self.assertEqual(self.settings._row()['config'], '{}')


if __name__ == '__main__':
    unittest.main()
