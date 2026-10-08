"""Concurrency and authority boundaries before the new D gateway is public."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import unittest

from extensions.continuity.fix_gateway import FixTaskGateway, RequestContext
from extensions.handoff.architecture import ArchitectureError


class Stub:
    def __init__(self):
        self.receipts = set()
        self.calls = 0

    def run_verification(self, task_id):
        self.calls += 1
        token = 'fixture-receipt-' + str(self.calls)
        self.receipts.add(token)
        return token, {'fixtureOnly': True}

    def discard_verification(self, token):
        self.receipts.discard(token)

    def confirm_verification(self, **payload):
        return {'fixtureOnly': True, 'actor': payload['actor']}


class GatewayBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000]
        self.service = Stub()
        self.context = RequestContext('127.0.0.1', '127.0.0.1:8765', 'http://127.0.0.1:8765')
        self.gateway = FixTaskGateway(self.service, self.context.origin, max_sessions=2,
                                      max_confirmations=1, clock=lambda: self.now[0])

    def session(self, gateway=None, context=None, actor='fixture'):
        gateway, context = gateway or self.gateway, context or self.context
        auth = gateway.create_session(actor, context)
        return replace(context, session_id=auth['sessionId'], csrf_token=auth['csrfToken'])

    def test_concurrent_session_capacity_and_expired_reuse(self):
        def start(_):
            try:
                return self.session()
            except ArchitectureError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            sessions = list(pool.map(start, range(8)))
        self.assertEqual(sum(x is not None for x in sessions), 2)
        self.assertEqual(len(self.gateway.sessions), 2)
        self.now[0] += 3601
        self.session()
        self.assertEqual(len(self.gateway.sessions), 1)

    def test_preview_capacity_prevents_provider_work_and_pruning_releases_receipt(self):
        context = self.session()
        self.gateway.call('verification_preview', {'task_id': 'fixture-task'}, context)
        with self.assertRaises(ArchitectureError):
            self.gateway.call('verification_preview', {'task_id': 'fixture-task'}, context)
        self.assertEqual(self.service.calls, 1)
        self.assertEqual(len(self.service.receipts), 1)
        self.now[0] += 601
        self.gateway.call('verification_preview', {'task_id': 'fixture-task'}, context)
        self.assertEqual(self.service.receipts, {'fixture-receipt-2'})
        self.assertEqual(len(self.gateway.confirmations), 1)

    def test_successful_confirmation_consumes_token_and_unicode_csrf_is_controlled(self):
        context = self.session()
        preview = self.gateway.call('verification_preview', {'task_id': 'fixture-task'}, context)
        payload = {'task_id': 'fixture-task', 'confirmation_token': preview['confirmationToken']}
        self.assertEqual(self.gateway.call('confirm_verification', payload, context)['actor'], 'fixture')
        self.assertEqual(self.gateway.confirmations, {})
        self.assertEqual(self.service.receipts, set())
        with self.assertRaises(ArchitectureError):
            self.gateway.call('confirm_verification', payload, context)
        with self.assertRaises(ArchitectureError):
            self.gateway.call('verification_preview', {'task_id': 'fixture-task'},
                              replace(context, csrf_token='不是令牌'))

    def test_public_context_requires_real_peer_actor_and_same_browser_binding(self):
        origin = 'https://projectmind.example.invalid'
        public = FixTaskGateway(self.service, origin, trusted_https_proxy=True)
        context = RequestContext('127.0.0.1', 'projectmind.example.invalid', origin,
                                 actor='fixture', browser_binding='a'*64)
        for change in ({'peer': '203.0.113.1'}, {'host': 'elsewhere.invalid'},
                       {'origin': 'https://elsewhere.invalid'}, {'actor': ''}, {'browser_binding': ''}):
            with self.subTest(change=change), self.assertRaises(ArchitectureError):
                public.create_session('fixture', replace(context, **change))
        with self.assertRaises(ArchitectureError):
            public.create_session('forged', context)
        context = self.session(public, context)
        public.call('verification_preview', {'task_id': 'fixture-task'}, context)
        with self.assertRaises(ArchitectureError):
            public.call('verification_preview', {'task_id': 'fixture-task'},
                        replace(context, browser_binding='b'*64))
        with self.assertRaises(ArchitectureError):
            public.call('verification_preview', {'task_id': 'fixture-task', 'actor': 'forged'}, context)


if __name__ == '__main__':
    unittest.main()
