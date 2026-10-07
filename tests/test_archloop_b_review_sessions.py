"""Session lifecycle tests. No real-human approval or public gateway is created."""
from concurrent.futures import ThreadPoolExecutor
import copy
import threading
import unittest
from unittest.mock import patch

from extensions.architecture_workspace.review import HumanReviewGateway
from extensions.architecture_workspace.errors import WorkspaceError


ORIGIN = "http://127.0.0.1:18832"
BOUNDARY = {"peer": "127.0.0.1", "host": "127.0.0.1:18832", "origin": ORIGIN}


class ReviewSessionTests(unittest.TestCase):
    def gateway(self, limit=128):
        return HumanReviewGateway(object(), ORIGIN, max_sessions=limit)

    def session(self, gateway):
        return gateway.create_session("TEST_ONLY_SIMULATED_HUMAN", **BOUNDARY)

    def auth(self, issued, **extra):
        return {**BOUNDARY, "session_id": issued["sessionId"],
                "csrf_token": issued["csrfToken"], **extra}

    def error(self, code, call):
        with self.assertRaises(WorkspaceError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_default_capacity_is_bounded_without_evicting_live_sessions(self):
        gateway = self.gateway()
        with patch("extensions.architecture_workspace.review.time.time", return_value=100):
            first = self.session(gateway)
            for _ in range(127):
                self.session(gateway)
            before = copy.deepcopy(gateway.sessions)
            self.error("INVALID_INPUT", lambda: self.session(gateway))
            self.assertEqual(gateway.sessions, before)
            self.assertEqual(gateway._session(**self.auth(first))["actor"],
                             "TEST_ONLY_SIMULATED_HUMAN")

    def test_expired_entries_are_pruned_in_place_before_creation(self):
        gateway = self.gateway(2)
        with patch("extensions.architecture_workspace.review.time.time", return_value=100):
            old = self.session(gateway)
        with patch("extensions.architecture_workspace.review.time.time", return_value=200):
            live = self.session(gateway)
        reference = gateway.sessions
        with patch("extensions.architecture_workspace.review.time.time", return_value=3700):
            new = self.session(gateway)
            self.assertIs(gateway.sessions, reference)
            self.assertNotIn(old["sessionId"], reference)
            self.assertIn(live["sessionId"], reference)
            self.assertIn(new["sessionId"], reference)
            self.error("REQUEST_FORBIDDEN", lambda: gateway._session(**self.auth(old)))
            self.assertEqual(gateway._session(**self.auth(live))["expires"], 3800)

    def test_validation_cleans_other_expired_sessions(self):
        gateway = self.gateway()
        with patch("extensions.architecture_workspace.review.time.time", return_value=100):
            old = self.session(gateway)
        with patch("extensions.architecture_workspace.review.time.time", return_value=200):
            live = self.session(gateway)
        with patch("extensions.architecture_workspace.review.time.time", return_value=3701):
            gateway._session(**self.auth(live))
        self.assertEqual(set(gateway.sessions), {live["sessionId"]})
        self.assertNotIn(old["sessionId"], gateway.sessions)

    def test_exact_expiry_boundary_refuses_old_authority(self):
        gateway = self.gateway()
        with patch("extensions.architecture_workspace.review.time.time", return_value=100):
            issued = self.session(gateway)
        with patch("extensions.architecture_workspace.review.time.time", return_value=3699.999):
            gateway._session(**self.auth(issued))
        with patch("extensions.architecture_workspace.review.time.time", return_value=3700):
            self.error("REQUEST_FORBIDDEN", lambda: gateway._session(**self.auth(issued)))
        self.assertEqual(gateway.sessions, {})

    def test_wrong_csrf_and_unknown_session_do_not_change_live_authority(self):
        gateway = self.gateway()
        issued = self.session(gateway)
        before = copy.deepcopy(gateway.sessions)
        for extra in ({"csrf_token": "wrong"}, {"session_id": "unknown"},
                      {"csrf_token": None}, {"csrf_token": "非ASCII令牌"},
                      {"session_id": []}):
            with self.subTest(extra=extra):
                self.error("REQUEST_FORBIDDEN",
                           lambda: gateway._session(**self.auth(issued, **extra)))
        self.assertEqual(gateway.sessions, before)

    def test_returned_session_cannot_mutate_registry(self):
        gateway = self.gateway()
        issued = self.session(gateway)
        value = gateway._session(**self.auth(issued))
        value["actor"] = "forged"
        value["expires"] = 0
        self.assertEqual(gateway._session(**self.auth(issued))["actor"],
                         "TEST_ONLY_SIMULATED_HUMAN")

    def test_bad_boundary_cannot_allocate_or_reuse_a_session(self):
        gateway = self.gateway()
        issued = self.session(gateway)
        before = copy.deepcopy(gateway.sessions)
        for bad in ({"peer": "203.0.113.4"}, {"peer": "not-ip"},
                    {"host": "evil.example"}, {"origin": "https://evil.example"},
                    {"origin": None}):
            with self.subTest(bad=bad):
                self.error("REQUEST_FORBIDDEN", lambda: gateway.create_session(
                    "TEST_ONLY_SIMULATED_HUMAN", **{**BOUNDARY, **bad}))
                self.error("REQUEST_FORBIDDEN",
                           lambda: gateway._session(**self.auth(issued, **bad)))
        self.assertEqual(gateway.sessions, before)

    def test_invalid_actor_does_not_allocate(self):
        gateway = self.gateway()
        self.error("INVALID_INPUT", lambda: gateway.create_session("", **BOUNDARY))
        self.assertEqual(gateway.sessions, {})

    def test_limits_must_be_positive_integers(self):
        for value in (0, -1, True, 1.0, None):
            with self.subTest(value=value):
                self.error("INVALID_INPUT", lambda: self.gateway(value))

    def test_session_collision_never_replaces_existing_authority(self):
        gateway = self.gateway(2)
        with patch("extensions.architecture_workspace.review.secrets.token_urlsafe",
                   side_effect=["same-id", "first-csrf"]):
            issued = self.session(gateway)
        before = copy.deepcopy(gateway.sessions)
        with patch("extensions.architecture_workspace.review.secrets.token_urlsafe",
                   return_value="same-id"):
            self.error("INVALID_INPUT", lambda: self.session(gateway))
        self.assertEqual(gateway.sessions, before)
        gateway._session(**self.auth(issued))

    def test_concurrent_creates_never_exceed_capacity(self):
        gateway = self.gateway(7)
        start = threading.Barrier(24)

        def create(_):
            start.wait(timeout=10)
            try:
                return ("ok", self.session(gateway))
            except WorkspaceError as exc:
                return ("error", exc.code)

        with ThreadPoolExecutor(max_workers=24) as pool:
            results = list(pool.map(create, range(24)))
        accepted = [value for status, value in results if status == "ok"]
        errors = [value for status, value in results if status == "error"]
        self.assertEqual(len(accepted), 7)
        self.assertEqual(errors, ["INVALID_INPUT"] * 17)
        self.assertEqual(len(gateway.sessions), 7)
        self.assertEqual(len({item["sessionId"] for item in accepted}), 7)
        for issued in accepted:
            gateway._session(**self.auth(issued))

    def test_prune_is_idempotent_and_keeps_active_sessions(self):
        gateway = self.gateway()
        with patch("extensions.architecture_workspace.review.time.time", return_value=100):
            issued = self.session(gateway)
        self.assertEqual(gateway._prune_sessions(101), 0)
        self.assertEqual(gateway._prune_sessions(3700), 1)
        self.assertEqual(gateway._prune_sessions(3700), 0)
        self.assertNotIn(issued["sessionId"], gateway.sessions)


if __name__ == "__main__":
    unittest.main()

