"""Real model workers send demo reasoning policy; synthetic provider/key only."""
import json
import os
import unittest
from unittest.mock import patch

from archloop import ai_transport as ai
from tests import test_archloop_ai_providers as fixtures


class ReasoningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.provider = fixtures._Provider(payload_text='{"ok":true}')
        self.addCleanup(self.provider.stop)
        self.env = patch.dict(os.environ, {
            'PROJECTMIND_AI_API_KEY': 'SYNTHETIC-NOT-A-REAL-KEY',
            'PROJECTMIND_AI_BASE_URL': self.provider.base,
            'PROJECTMIND_AI_MODEL': 'deepseek-v4.1-flash',
            'PROJECTMIND_AI_PROTOCOL': 'chat_completions'}, clear=False)
        self.env.start(); self.addCleanup(self.env.stop)
        os.environ.pop('PROJECTMIND_AI_REASONING_EFFORT', None)
        self.schema = {'type':'object','properties':{'ok':{'type':'boolean'}},
                       'required':['ok'],'additionalProperties':False}

    def call(self):
        self.assertEqual(ai.call_model('fixture JSON', {}, 's', self.schema, timeout=5), {'ok':True})
        return self.provider.handler.calls[-1]['body']

    def test_deepseek_v4_chat_sends_low_in_real_worker_request(self):
        body = self.call()
        self.assertEqual(body.get('thinking'), {'type':'enabled'})
        self.assertEqual(body.get('reasoning_effort'), 'low')
        self.assertEqual(body['response_format'], {'type':'json_object'})

    def test_responses_uses_its_native_reasoning_field(self):
        os.environ['PROJECTMIND_AI_PROTOCOL'] = 'responses'
        body = self.call()
        self.assertEqual(body.get('reasoning'), {'effort':'low'})
        self.assertNotIn('reasoning_effort', body)
        self.assertNotIn('thinking', body)

    def test_compatibility_retry_preserves_requested_low_effort(self):
        self.provider.handler.reject_response_format = True
        self.call()
        self.assertEqual(len(self.provider.handler.calls), 2)
        for request in self.provider.handler.calls:
            self.assertEqual(request['body'].get('reasoning_effort'), 'low')

    def test_other_models_and_legacy_deepseek_requests_are_unchanged(self):
        for model in ('gpt-example','qwen-example','deepseek-chat','deepseek-reasoner'):
            with self.subTest(model=model):
                os.environ['PROJECTMIND_AI_MODEL'] = model
                body = self.call()
                self.assertNotIn('thinking', body)
                self.assertNotIn('reasoning_effort', body)
                self.assertNotIn('reasoning', body)

    def test_admin_can_explicitly_disable_thinking_or_restore_high(self):
        os.environ['PROJECTMIND_AI_REASONING_EFFORT'] = 'none'
        body = self.call()
        self.assertEqual(body.get('thinking'), {'type':'disabled'})
        self.assertNotIn('reasoning_effort', body)
        os.environ['PROJECTMIND_AI_REASONING_EFFORT'] = 'high'
        body = self.call()
        self.assertEqual(body.get('thinking'), {'type':'enabled'})
        self.assertEqual(body.get('reasoning_effort'), 'high')

    def test_invalid_effort_refuses_before_network_and_does_not_echo_private_value(self):
        os.environ['PROJECTMIND_AI_REASONING_EFFORT'] = 'SYNTHETIC-PRIVATE-VALUE'
        with patch.object(ai.subprocess,'Popen') as worker:
            with self.assertRaises(ai.AIError) as caught:
                ai.call_model('fixture', {}, 's', self.schema)
            worker.assert_not_called()
        self.assertNotIn('SYNTHETIC',str(caught.exception))

    def test_public_status_reports_requested_effort_without_secrets(self):
        status = ai.ai_status()
        self.assertEqual(status.get('reasoningEffort'), 'low')
        self.assertNotIn('SYNTHETIC', json.dumps(status))


if __name__ == '__main__':
    unittest.main()
