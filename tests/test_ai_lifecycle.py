"""Actual disposable workers and HTTP; no external provider or real key."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from archloop import ai_transport as transport

SCHEMA = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
          'required': ['ok'], 'additionalProperties': False}
WIRE = json.dumps({'choices': [{'message': {'content': '{"ok":true}'}}]}).encode()


class LifecycleTests(unittest.TestCase):
    def endpoint(self, mode):
        calls = []
        entered = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                calls.append(self.path); entered.set()
                try:
                    if mode == 'headers':
                        time.sleep(.8)
                    if mode == 'retry':
                        time.sleep(.25)
                        if len(calls) == 1:
                            self.send_response(400); self.send_header('Content-Length', '0'); self.end_headers()
                            return
                    self.send_response(200); self.send_header('Content-Length', str(len(WIRE))); self.end_headers()
                    if mode == 'body':
                        for byte in WIRE:
                            self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.02)
                    else:
                        self.wfile.write(WIRE)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}', calls, entered

    def config(self, url):
        return patch.dict(os.environ, {'PROJECTMIND_AI_API_KEY': 'synthetic-fixture',
            'PROJECTMIND_AI_MODEL': 'fixture', 'PROJECTMIND_AI_BASE_URL': url,
            'PROJECTMIND_AI_PROTOCOL': 'chat_completions'})

    def track(self):
        children = []
        launch = subprocess.Popen
        def start(*args, **kwargs):
            process = launch(*args, **kwargs); children.append(process); return process
        return children, patch.object(transport.subprocess, 'Popen', side_effect=start)

    def assert_reaped(self, children):
        self.assertTrue(children)
        for child in children:
            self.assertIsNotNone(child.poll(), 'network worker must have exited')
            self.assertTrue(child.stdin.closed)
            self.assertTrue(child.stdout.closed)

    def test_success_reaps_worker(self):
        url, calls, _ = self.endpoint('fast'); children, tracked = self.track()
        with self.config(url), tracked:
            self.assertEqual(transport.call_model('fixture', {}, 's', SCHEMA, timeout=2), {'ok': True})
        self.assertEqual(len(calls), 1); self.assert_reaped(children)

    def test_slow_headers_and_slow_drip_obey_one_total_budget(self):
        for mode in ('headers', 'body'):
            url, _, _ = self.endpoint(mode); children, tracked = self.track()
            with self.subTest(mode=mode), self.config(url), tracked:
                started = time.monotonic()
                with self.assertRaises(transport.AITimeout):
                    transport.call_model('fixture', {}, 's', SCHEMA, timeout=.3)
                self.assertLess(time.monotonic()-started, 1.2)
            self.assert_reaped(children)

    def test_http400_retry_does_not_reset_total_budget(self):
        url, calls, _ = self.endpoint('retry'); children, tracked = self.track()
        with self.config(url), tracked:
            with self.assertRaises(transport.AITimeout):
                transport.call_model('fixture', {}, 's', SCHEMA, timeout=.45)
        self.assertEqual(len(calls), 2); self.assert_reaped(children)

    def test_cancel_active_request_terminates_and_reaps_worker(self):
        url, _, entered = self.endpoint('headers'); cancel = threading.Event()
        children, tracked = self.track()
        errors = []
        def run():
            try: transport.call_model('fixture', {}, 's', SCHEMA, timeout=3, cancel_event=cancel)
            except transport.AIError as exc: errors.append(exc)
        with self.config(url), tracked:
            thread = threading.Thread(target=run); thread.start()
            self.assertTrue(entered.wait(2))
            cancel.set(); thread.join(1)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1); self.assertIsInstance(errors[0], transport.AICancelled)
        self.assert_reaped(children)

    def test_cancel_queued_call_never_launches_worker(self):
        cancel = threading.Event()
        for _ in range(4): transport._WORKERS.acquire()
        timer = threading.Timer(.1, cancel.set); timer.start()
        try:
            with self.config('http://127.0.0.1:1'), patch.object(transport.subprocess, 'Popen') as launch:
                with self.assertRaises(transport.AICancelled):
                    transport.call_model('fixture', {}, 's', SCHEMA, timeout=1, cancel_event=cancel)
                launch.assert_not_called()
        finally:
            timer.cancel()
            for _ in range(4): transport._WORKERS.release()

    def test_parallel_timeouts_release_all_admission_slots(self):
        url, _, _ = self.endpoint('headers'); children, tracked = self.track()
        def run(_):
            try: transport.call_model('fixture', {}, 's', SCHEMA, timeout=.25)
            except transport.AITimeout: return True
            return False
        with self.config(url), tracked, ThreadPoolExecutor(max_workers=3) as pool:
            self.assertTrue(all(pool.map(run, range(3))))
        self.assert_reaped(children)
        for _ in range(4): self.assertTrue(transport._WORKERS.acquire(blocking=False))
        for _ in range(4): transport._WORKERS.release()

    def test_invalid_budget_and_precancel_refuse_before_start(self):
        cancel = threading.Event(); cancel.set()
        with self.config('http://127.0.0.1:1'), patch.object(transport.subprocess, 'Popen') as launch:
            for timeout in (0, -1, True, float('nan'), float('inf')):
                with self.assertRaises(transport.AIError):
                    transport.call_model('fixture', {}, 's', SCHEMA, timeout=timeout)
            with self.assertRaises(transport.AICancelled):
                transport.call_model('fixture', {}, 's', SCHEMA, cancel_event=cancel)
            launch.assert_not_called()
