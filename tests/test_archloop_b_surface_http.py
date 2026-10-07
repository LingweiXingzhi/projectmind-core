"""Real HTTP sockets for the fixture transport; no A application/UI claims."""
from __future__ import annotations

from contextlib import redirect_stderr
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from io import StringIO
import json
from pathlib import Path
import stat
import tempfile
import time
import unittest

from extensions.architecture_workspace.errors import WorkspaceError
from extensions.architecture_workspace.fixture_http import (
    FixtureHTTPServer, FIXTURE_ORIGIN, FIXTURE_BRANCH, COOKIE, MAX_BODY, SOCKET_TIMEOUT)
from extensions.architecture_workspace.proposals import API_VERSION
from extensions.architecture_workspace.git_publication import GitPublisher, read_git
from extensions.architecture_workspace.smoke import init, git, graph


class FixtureSurfaceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archloop-b-http-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.code, self.arch = self.root / "code", self.root / "architecture"
        init(self.code, "main"); init(self.arch, FIXTURE_BRANCH)
        git(self.code, "remote", "add", "origin", FIXTURE_ORIGIN)
        (self.code / "demo.py").write_text("def demo():\n    return 1\n")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "Actual fixture code")
        self.code_before = self.code_state()
        self.arch_before = git(self.arch, "rev-parse", "HEAD")
        self.server = FixtureHTTPServer(self.root / "state", self.code, self.arch,
                                        test_fixture_only=True).start()
        self.addCleanup(self.server.close)
        self.responses = []

    def tearDown(self):
        self.server.close()
        self.temporary.cleanup()

    def code_state(self):
        return {"head": git(self.code, "rev-parse", "HEAD"),
                "tree": git(self.code, "rev-parse", "HEAD^{tree}"),
                "status": git(self.code, "status", "--porcelain"),
                "files": {name: (self.code / name).read_bytes()
                          for name in git(self.code, "ls-files").splitlines()}}

    def request(self, path, body=None, *, headers=None, method="POST", raw=None,
                origin=True, host=None):
        payload = raw if raw is not None else json.dumps(body or {
            "apiVersion": API_VERSION, "requestId": "request-fixture"}).encode()
        base = {"Host": self.server.host if host is None else host,
                "Content-Type": "application/json"}
        if origin:
            base["Origin"] = self.server.origin if origin is True else origin
        base.update(headers or {})
        connection = HTTPConnection("127.0.0.1", self.server.port, timeout=SOCKET_TIMEOUT + 3)
        try:
            connection.request(method, path, body=payload, headers=base)
            response = connection.getresponse()
            contents = response.read()
            result = json.loads(contents)
            self.responses.append(contents)
            return response.status, dict(response.getheaders()), result
        finally:
            connection.close()

    def session(self):
        status, headers, result = self.request("/session")
        self.assertEqual(status, 200)
        cookie = SimpleCookie(); cookie.load(headers["Set-Cookie"])
        return {"Cookie": COOKIE + "=" + cookie[COOKIE].value,
                "X-CSRF-Token": result["data"]["csrfToken"]}, result["context"]

    def user(self, action, auth, **data):
        return self.request("/user/" + action, {"apiVersion": API_VERSION,
            "requestId": "request-" + action, **data}, headers=auth)

    def prepare(self, auth, context):
        candidate = graph(context["codeRepoId"], context["codeRevision"])
        status, _, result = self.user("prepareDraft", auth, context=context,
                                      graph=candidate, origin="manual")
        self.assertEqual(status, 200, result)
        return candidate, result["context"]

    def approved(self, auth, context, candidate):
        coverage = {"scope": "all", **{key: [obj["id"] for obj in candidate[key]]
            for key in ("nodes", "edges", "processes", "evidence")}}
        status, _, preview = self.user("previewReview", auth, context=context,
            reason="TEST ONLY simulated operator", coverage=coverage,
            limits=["FIXTURE ONLY: not a project owner approval"], verifyCode=False)
        self.assertEqual(status, 200, preview)
        status, _, reviewed = self.user("confirmReview", auth, context=context,
            previewId=preview["data"]["previewId"], previewDigest=preview["data"]["previewDigest"],
            decision="accept")
        self.assertEqual(status, 200, reviewed)
        return preview, reviewed

    def assert_error(self, status, result, expected_status, code):
        self.assertEqual(status, expected_status, result)
        self.assertEqual(result["error"]["code"], code)
        self.assertEqual(result["apiVersion"], API_VERSION)

    def test_session_cookie_is_http_only_strict_and_operator_is_hardcoded(self):
        status, headers, result = self.request("/session")
        self.assertEqual(status, 200)
        cookie = SimpleCookie(); cookie.load(headers["Set-Cookie"])
        self.assertTrue(cookie[COOKIE]["httponly"])
        self.assertEqual(cookie[COOKIE]["samesite"], "Strict")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Connection"], "close")
        self.assertEqual(result["data"]["operator"], "TEST_ONLY_SIMULATED_HUMAN")
        self.assertTrue(result["data"]["fixtureOnly"])
        self.assertNotIn("sessionId", result["data"])
        status, _, result = self.request("/session", {"apiVersion": API_VERSION,
            "requestId": "forge-actor", "actor": "Project Owner"})
        self.assert_error(status, result, 400, "INVALID_INPUT")

    def test_session_rejects_missing_cross_origin_and_wrong_host(self):
        for options in ({"origin": False}, {"origin": "https://untrusted.example"},
                        {"origin": "http://localhost:" + str(self.server.port)},
                        {"host": "localhost:" + str(self.server.port)},
                        {"host": "127.0.0.1:1"}):
            with self.subTest(options=options):
                status, _, result = self.request("/session", **options)
                self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")
        self.assertEqual(self.server.gateway.sessions, {})

    def test_unauthenticated_write_and_body_auth_forgery_are_denied(self):
        auth, context = self.session()
        body = {"apiVersion": API_VERSION, "requestId": "body-forgery", "context": context,
                "graph": graph(context["codeRepoId"], context["codeRevision"]), "origin": "manual",
                "auth": {"session_id": auth["Cookie"].split("=", 1)[1],
                         "csrf_token": auth["X-CSRF-Token"], "peer": "127.0.0.1",
                         "host": self.server.host, "origin": self.server.origin}}
        for headers in ({}, {"Cookie": auth["Cookie"]}):
            status, _, result = self.request("/user/prepareDraft", body, headers=headers)
            self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")
        status, _, result = self.request("/user/prepareDraft", body, headers=auth)
        self.assert_error(status, result, 400, "INVALID_INPUT")
        with self.server.service.store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM documents WHERE kind='draft'").fetchone()[0], 0)

    def test_invalid_csrf_and_duplicate_session_cookie_do_not_authorize(self):
        auth, context = self.session()
        for changes in ({"X-CSRF-Token": "wrong"},
                        {"Cookie": auth["Cookie"] + "; " + auth["Cookie"]}):
            status, _, result = self.user("readView", {**auth, **changes})
            self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")

    def test_cross_origin_request_with_valid_cookie_and_csrf_is_denied(self):
        auth, _ = self.session()
        status, _, result = self.request("/user/readView", headers=auth,
                                       origin="https://untrusted.example")
        self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")
        self.assertNotIn("currentContext", result)

    def test_real_http_prepare_review_publish_never_exports_private_grants(self):
        auth, context = self.session()
        candidate, context = self.prepare(auth, context)
        _, approved = self.approved(auth, context, candidate)
        status, _, published = self.user("publishVersion", auth, context=context,
                                        reviewId=approved["data"]["reviewId"])
        self.assertEqual(status, 200, published)
        self.assertEqual(published["status"], "published")
        envelope = published["data"]["versionEnvelope"]
        self.assertEqual(envelope["version"]["codeRevision"], self.code_before["head"])
        self.assertIsNone(envelope["version"]["verifiedCodeRevision"])
        self.assertEqual(published["context"]["baseMapRevision"], context["baseMapRevision"])
        self.assertNotEqual(git(self.arch, "rev-parse", "HEAD"), self.arch_before)
        self.assertEqual(git(self.arch, "rev-list", "--count", self.arch_before + "..HEAD"), "1")
        self.assertEqual(self.code_state(), self.code_before)
        status, _, read = self.user("readView", auth)
        self.assertEqual(status, 200)
        self.assertEqual(read["data"]["versionEnvelope"], envelope)
        private_fields = {"confirmationToken", "confirmation_token", "publicationToken",
                          "publication_token", "sessionId"}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(private_fields & set(value))
                for item in value.values(): check(item)
            elif isinstance(value, list):
                for item in value: check(item)
        for response in self.responses:
            check(json.loads(response))
        raw_grants = [item["result"]["confirmationToken"] for item in self.server.api._previews.values()]
        raw_grants += [item["result"]["publicationToken"] for item in self.server.api._reviews.values()]
        version_bytes = read_git(self.arch, "show", envelope["provenance"]["mapSourceRevision"] + ":" +
            GitPublisher.relative_path(envelope["version"]["mapId"], envelope["version"]["mapRevision"]))
        public_bytes = self.responses + [version_bytes] + list(self.code_state()["files"].values())
        for grant in raw_grants:
            self.assertTrue(all(grant.encode() not in artifact for artifact in public_bytes))
        # V1 stores original review replay responses, including publicationToken,
        # in private SQLite intentionally. This HTTP sample does not alter that
        # storage algorithm or recover session authority from it after restart.
        self.assertEqual(stat.S_IMODE(self.server.service.store.path.stat().st_mode), 0o600)
        # Cookie / CSRF credentials belong only to this live transport. The CSRF
        # value is deliberately issued once in the session JSON response.
        private_values = [auth["Cookie"].split("=", 1)[1], auth["X-CSRF-Token"]]
        persisted = [file.read_bytes() for file in (self.root / "state").rglob("*") if file.is_file()]
        for value in private_values:
            self.assertTrue(all(value.encode() not in data for data in persisted))
            self.assertNotIn(value.encode(), version_bytes)
            self.assertTrue(all(value.encode() not in data for data in self.code_state()["files"].values()))

    def test_transport_does_not_log_session_headers_or_request_failures(self):
        captured = StringIO()
        with redirect_stderr(captured):
            auth, _ = self.session()
            status, _, result = self.user("readView", auth)
            self.assertEqual(status, 200, result)
            status, _, result = self.user("readView", {**auth, "X-CSRF-Token": "wrong"})
            self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")
        self.assertEqual(captured.getvalue(), "")

    def test_other_valid_session_cannot_publish_original_human_review(self):
        auth, context = self.session()
        candidate, context = self.prepare(auth, context)
        _, approved = self.approved(auth, context, candidate)
        other_auth, _ = self.session()
        status, _, result = self.user("publishVersion", other_auth, context=context,
                                    reviewId=approved["data"]["reviewId"])
        self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), self.arch_before)
        status, _, result = self.user("publishVersion", auth, context=context,
                                    reviewId=approved["data"]["reviewId"])
        self.assertEqual(status, 200, result)
        self.assertEqual(self.code_state(), self.code_before)

    def test_other_valid_session_cannot_confirm_original_preview(self):
        auth, context = self.session()
        candidate, context = self.prepare(auth, context)
        coverage = {"scope": "all", **{key: [obj["id"] for obj in candidate[key]]
            for key in ("nodes", "edges", "processes", "evidence")}}
        status, _, preview = self.user("previewReview", auth, context=context,
            reason="TEST ONLY", coverage=coverage, limits=["Fixture only"], verifyCode=False)
        self.assertEqual(status, 200)
        other_auth, _ = self.session()
        status, _, result = self.user("confirmReview", other_auth, context=context,
            previewId=preview["data"]["previewId"], previewDigest=preview["data"]["previewDigest"],
            decision="accept")
        self.assert_error(status, result, 403, "REQUEST_FORBIDDEN")
        self.assertEqual(self.server.service.get_draft(context["draftId"])["status"], "unconfirmed")

    def test_strict_json_rejects_duplicates_nonfinite_invalid_utf8_and_types(self):
        for raw in (b'{"apiVersion":"b-surfaces-v2-candidate","requestId":"a","requestId":"b"}',
                    b'{"apiVersion":"b-surfaces-v2-candidate","requestId":NaN}',
                    b'{"apiVersion":"b-surfaces-v2-candidate","requestId":Infinity}',
                    b'{"x":"\xff"}', b'[]', b'null', b'{'):
            with self.subTest(raw=raw):
                status, _, result = self.request("/session", raw=raw)
                self.assert_error(status, result, 400, "INVALID_INPUT")
        self.assertEqual(self.server.gateway.sessions, {})

    def test_oversize_chunked_and_unsupported_content_type_rejected(self):
        for headers in ({"Content-Length": str(MAX_BODY + 1)}, {"Transfer-Encoding": "chunked"},
                        {"Content-Type": "text/plain"}, {"Content-Length": "-1"}):
            status, _, result = self.request("/session", headers=headers)
            self.assert_error(status, result, 400, "INVALID_INPUT")
        self.assertEqual(self.server.gateway.sessions, {})

    def test_duplicate_content_length_or_boundary_headers_are_rejected(self):
        for duplicated, status_expected, code in (("Content-Length", 400, "INVALID_INPUT"),
                ("Origin", 403, "REQUEST_FORBIDDEN"), ("Host", 403, "REQUEST_FORBIDDEN")):
            payload = json.dumps({"apiVersion": API_VERSION, "requestId": "duplicate"}).encode()
            connection = HTTPConnection("127.0.0.1", self.server.port, timeout=SOCKET_TIMEOUT + 3)
            try:
                connection.putrequest("POST", "/session", skip_host=True, skip_accept_encoding=True)
                base = {"Host": self.server.host, "Origin": self.server.origin,
                        "Content-Type": "application/json", "Content-Length": str(len(payload))}
                for key, value in base.items():
                    connection.putheader(key, value)
                    if key == duplicated:
                        connection.putheader(key, value)
                connection.endheaders(payload)
                response = connection.getresponse()
                self.assert_error(response.status, json.loads(response.read()), status_expected, code)
            finally:
                connection.close()

    def test_incomplete_body_gets_controlled_error_after_socket_timeout(self):
        connection = HTTPConnection("127.0.0.1", self.server.port, timeout=SOCKET_TIMEOUT + 3)
        started = time.monotonic()
        try:
            connection.request("POST", "/session", body=b"{", headers={
                "Host": self.server.host, "Origin": self.server.origin,
                "Content-Type": "application/json", "Content-Length": "100"})
            response = connection.getresponse()
            self.assert_error(response.status, json.loads(response.read()), 400, "INVALID_INPUT")
            self.assertLess(time.monotonic() - started, SOCKET_TIMEOUT + 2)
        finally:
            connection.close()

    def test_unknown_endpoint_and_methods_return_json_errors(self):
        for path in ("/other", "/user/notAnAction", "/session?actor=Owner"):
            status, _, result = self.request(path)
            self.assert_error(status, result, 404, "NOT_FOUND")
        for method in ("GET", "PUT", "OPTIONS", "UNREGISTERED"):
            status, _, result = self.request("/session", method=method)
            self.assert_error(status, result, 405, "REQUEST_FORBIDDEN")

class FixtureGuardTests(unittest.TestCase):
    """Fixture ownership checks run even when the sandbox blocks TCP binds."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archloop-b-http-guard-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.code, self.arch = self.root / "code", self.root / "architecture"
        init(self.code, "main"); init(self.arch, FIXTURE_BRANCH)
        git(self.code, "remote", "add", "origin", FIXTURE_ORIGIN)
        self.arch_before = git(self.arch, "rev-parse", "HEAD")

    def test_wrong_fixture_flag_origin_or_branch_fails_before_state_writes(self):
        candidate_root = self.root / "guard-state"
        for flag in (False, None, 1):
            with self.assertRaises(WorkspaceError):
                FixtureHTTPServer(candidate_root, self.code, self.arch, test_fixture_only=flag)
            self.assertFalse(candidate_root.exists())
        git(self.code, "remote", "set-url", "origin", "https://github.com/example/real-project.git")
        with self.assertRaises(WorkspaceError) as caught:
            FixtureHTTPServer(candidate_root, self.code, self.arch, test_fixture_only=True)
        self.assertEqual(caught.exception.code, "REQUEST_FORBIDDEN")
        self.assertFalse(candidate_root.exists())
        git(self.code, "remote", "set-url", "origin", FIXTURE_ORIGIN)
        git(self.arch, "checkout", "-b", "architecture/candidates/not-the-fixture")
        with self.assertRaises(WorkspaceError) as caught:
            FixtureHTTPServer(candidate_root, self.code, self.arch, test_fixture_only=True)
        self.assertEqual(caught.exception.code, "REQUEST_FORBIDDEN")
        self.assertFalse(candidate_root.exists())
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), self.arch_before)

    def test_existing_state_and_repository_inside_state_target_are_not_overwritten(self):
        existing = self.root / "another-state"
        existing.mkdir(); marker = existing / "keep.txt"; marker.write_text("Keep prior work")
        for root in (existing, self.code / "nested-state", self.arch / "nested-state"):
            with self.assertRaises(WorkspaceError):
                FixtureHTTPServer(root, self.code, self.arch, test_fixture_only=True)
        self.assertEqual(marker.read_text(), "Keep prior work")
        self.assertFalse((self.code / "nested-state").exists())
        self.assertFalse((self.arch / "nested-state").exists())


if __name__ == "__main__":
    unittest.main()
