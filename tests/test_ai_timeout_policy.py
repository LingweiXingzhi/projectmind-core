"""Generation waiting policy against real disposable workers and delayed HTTP."""
import json
import os
import time
import unittest
from unittest.mock import patch

from archloop import ai_transport as transport
from tests import test_ai_lifecycle as fixtures


class TimeoutPolicyTests(unittest.TestCase):
    endpoint = fixtures.LifecycleTests.endpoint
    config = fixtures.LifecycleTests.config

    def test_default_generation_call_has_three_minute_total_budget(self):
        observed = []
        def worker(message, deadline, cancel):
            observed.append((json.loads(message)['timeout'], deadline-time.monotonic()))
            return {'ok': True}
        with self.config('http://127.0.0.1:1'), patch.dict(os.environ, {}, clear=False), \
                patch.object(transport, '_isolated_call', side_effect=worker):
            os.environ.pop('PROJECTMIND_AI_TIMEOUT_SECONDS', None)
            self.assertEqual(transport.call_model('fixture', {}, 's', fixtures.SCHEMA), {'ok': True})
        self.assertEqual(observed[0][0], 180)
        self.assertGreater(observed[0][1], 170)
        self.assertLessEqual(observed[0][1], 180)

    def test_server_override_controls_real_slow_request_and_can_extend_wait(self):
        url, calls, _ = self.endpoint('headers')
        with self.config(url), patch.dict(os.environ, {'PROJECTMIND_AI_TIMEOUT_SECONDS': '.3'}):
            started = time.monotonic()
            with self.assertRaises(transport.AITimeout):
                transport.call_model('fixture', {}, 's', fixtures.SCHEMA)
            self.assertLess(time.monotonic()-started, 1.2)
        with self.config(url), patch.dict(os.environ, {'PROJECTMIND_AI_TIMEOUT_SECONDS': '2'}):
            self.assertEqual(transport.call_model('fixture', {}, 's', fixtures.SCHEMA), {'ok': True})
        self.assertEqual(len(calls), 2)

    def test_explicit_short_probe_budget_is_preserved(self):
        url, _, _ = self.endpoint('headers')
        with self.config(url), patch.dict(os.environ, {'PROJECTMIND_AI_TIMEOUT_SECONDS': '180'}):
            with self.assertRaises(transport.AITimeout):
                transport.call_model('fixture', {}, 's', fixtures.SCHEMA, timeout=.3)

    def test_invalid_admin_values_refuse_before_provider_and_do_not_echo_values(self):
        with self.config('http://127.0.0.1:1'), patch.object(transport.subprocess, 'Popen') as worker:
            for value in ('0', '-1', 'nan', 'inf', '601', 'SYNTHETIC-PRIVATE-VALUE'):
                with self.subTest(value=value), patch.dict(os.environ, {'PROJECTMIND_AI_TIMEOUT_SECONDS':value}):
                    with self.assertRaises(transport.AIError) as error:
                        transport.call_model('fixture', {}, 's', fixtures.SCHEMA)
                    self.assertNotIn(value, str(error.exception))
            worker.assert_not_called()

    def test_readiness_exposes_wait_duration_without_credentials(self):
        with self.config('https://example.invalid/v1'), patch.dict(os.environ, {'PROJECTMIND_AI_TIMEOUT_SECONDS':'180'}):
            status = transport.ai_status()
        self.assertTrue(status['configured'])
        self.assertEqual(status['requestTimeoutSeconds'], 180)
        self.assertNotIn('synthetic-fixture', json.dumps(status))


if __name__ == '__main__':
    unittest.main()
