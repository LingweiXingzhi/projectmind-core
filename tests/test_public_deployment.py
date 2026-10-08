"""Actual Waitress/socket tests; HTTPS headers and human choices are fixtures."""
import io
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import unittest

from deployment.access import AccessError, COOKIE, PublicAccess, add_account, create_account_file
from deployment.server import build_application

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_archloop_a_backend_b import tiny_code_repo, architecture_repo, run_git

ORIGIN = "https://projectmind.example.invalid"


@unittest.skipUnless(os.name == "posix", "Public deployment currently requires POSIX permissions")
class AccountBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.password = secrets.token_urlsafe(24)
        self.accounts = self.root / "accounts.json"
        create_account_file(self.accounts, "fixture", self.password)

    def test_account_file_is_private_hashed_and_not_overwritten(self):
        value = self.accounts.read_text()
        self.assertNotIn(self.password, value)
        self.assertEqual(self.accounts.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            create_account_file(self.accounts, "second", secrets.token_urlsafe(24))
        self.assertEqual(self.accounts.read_text(), value)

    def test_add_team_member_preserves_original_hash_and_rejects_duplicate(self):
        original = json.loads(self.accounts.read_text())["users"]["fixture"]
        add_account(self.accounts, "second", secrets.token_urlsafe(24))
        users = json.loads(self.accounts.read_text())["users"]
        self.assertEqual(users["fixture"], original); self.assertIn("second", users)
        with self.assertRaises(AccessError): add_account(self.accounts, "fixture", self.password)
        self.assertEqual(json.loads(self.accounts.read_text())["users"], users)
        self.assertEqual(self.accounts.stat().st_mode & 0o777, 0o600)

    def test_public_accounts_cannot_be_in_git_or_world_readable(self):
        repository = self.root / "repo"; repository.mkdir(); (repository / ".git").mkdir()
        with self.assertRaises(AccessError):
            create_account_file(repository / "accounts.json", "fixture", self.password)
        self.accounts.chmod(0o644)
        with self.assertRaises(AccessError):
            PublicAccess(ORIGIN, self.accounts)

    def test_session_csrf_expiry_capacity_and_logout(self):
        now = [1000]
        access = PublicAccess(ORIGIN, self.accounts, max_sessions=1, ttl=20, clock=lambda: now[0])
        sid, session = access.login("fixture", self.password)
        environ = {"HTTP_COOKIE": COOKIE + "=" + sid, "HTTP_X_PROJECTMIND_CSRF": session.csrf}
        self.assertEqual(access.session(environ, write=True).actor, "fixture")
        with self.assertRaises(AccessError): access.session({**environ, "HTTP_X_PROJECTMIND_CSRF": "wrong"}, write=True)
        with self.assertRaises(AccessError): access.login("fixture", self.password)
        now[0] = 1021
        with self.assertRaises(AccessError): access.session(environ)
        sid, session = access.login("fixture", self.password)
        environ.update(HTTP_COOKIE=COOKIE + "=" + sid, HTTP_X_PROJECTMIND_CSRF=session.csrf)
        access.logout(environ)
        with self.assertRaises(AccessError): access.session(environ)

    def test_real_peer_host_origin_ignore_forwarded_headers(self):
        access = PublicAccess(ORIGIN, self.accounts)
        valid = {"REMOTE_ADDR": "127.0.0.1", "HTTP_HOST": "projectmind.example.invalid", "HTTP_ORIGIN": ORIGIN}
        access.transport(valid, write=True)
        for change in ({"REMOTE_ADDR": "203.0.113.1", "HTTP_X_FORWARDED_FOR": "127.0.0.1"},
                       {"HTTP_HOST": "elsewhere.invalid"}, {"HTTP_ORIGIN": "https://elsewhere.invalid"},
                       {"HTTP_ORIGIN": None}):
            with self.subTest(change=change), self.assertRaises(AccessError):
                access.transport({**valid, **change}, write=True)

    def test_unknown_login_buckets_are_bounded_and_rate_limited(self):
        access = PublicAccess(ORIGIN, self.accounts)
        for i in range(10):
            with self.assertRaises(AccessError) as caught: access.login("unknown" + str(i), "wrong")
            self.assertEqual(caught.exception.code, "LOGIN_FAILED")
        with self.assertRaises(AccessError) as caught: access.login("another", "wrong")
        self.assertEqual(caught.exception.code, "LOGIN_RATE_LIMIT")
        self.assertEqual(len(access.attempts), 1)


@unittest.skipUnless(os.name == "posix", "Public deployment currently requires POSIX permissions")
class PublicHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from waitress import create_server
        except ImportError:
            raise unittest.SkipTest("Install requirements-deploy.txt for actual production HTTP tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="projectmind-public-fixture-")
        cls.root = Path(cls.temp.name).resolve()
        cls.password = secrets.token_urlsafe(24)
        cls.accounts = cls.root / "accounts.json"
        create_account_file(cls.accounts, "fixture", cls.password)
        cls.code = tiny_code_repo(cls.root)
        cls.arch = architecture_repo(cls.root)
        cls.config = cls.root / "deployment.json"
        cls.config.write_text(json.dumps({"schemaVersion": "projectmind_deploy_v1", "publicOrigin": ORIGIN,
            "accountsFile": str(cls.accounts), "dataRoot": str(cls.root / "state"),
            "codeRepositories": [str(cls.code)], "architectureRepo": str(cls.arch),
            "architectureBranch": "architecture/candidates/archloop-test"}))
        cls.application = build_application(cls.config)
        cls.registered_key = "registered:" + next(iter(cls.application.repositories))
        cls.server = create_server(cls.application, host="127.0.0.1", port=0, threads=4,
                                  max_request_body_size=1_048_576, clear_untrusted_proxy_headers=True)
        cls.port = int(cls.server.effective_port)
        cls.stopping = threading.Event(); cls.runtime_errors = []
        def serve():
            try:
                cls.server.run()
            except OSError as exc:
                if not cls.stopping.is_set(): cls.runtime_errors.append(type(exc).__name__)
        cls.thread = threading.Thread(target=serve, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.stopping.set()
        cls.server.task_dispatcher.shutdown(); cls.server.close()
        cls.thread.join(timeout=5); cls.temp.cleanup()
        if cls.runtime_errors: raise AssertionError(cls.runtime_errors)

    def request(self, method, path, body=None, *, auth=None, origin=ORIGIN, headers=None):
        values = {"Host": "projectmind.example.invalid", "Content-Type": "application/json"}
        if origin is not None: values["Origin"] = origin
        values.update(auth or {}); values.update(headers or {})
        raw = json.dumps(body or {}).encode() if method == "POST" else None
        connection = HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request(method, path, body=raw, headers=values)
            response = connection.getresponse(); data = response.read(); metadata = dict(response.getheaders())
            result = json.loads(data) if data and metadata.get("Content-Type", "").startswith("application/json") else data
            return response.status, metadata, result
        finally: connection.close()

    def login(self):
        status, headers, body = self.request("POST", "/api/auth/login", {"username": "fixture", "password": self.password})
        self.assertEqual(status, 200, body)
        cookie = SimpleCookie(); cookie.load(headers["Set-Cookie"])
        self.assertTrue(cookie[COOKIE]["secure"]); self.assertTrue(cookie[COOKIE]["httponly"])
        self.assertEqual(cookie[COOKIE]["samesite"], "Strict")
        return {"Cookie": COOKIE + "=" + cookie[COOKIE].value, "X-ProjectMind-CSRF": body["csrf"]}

    def workspace(self, auth, *, planning=False):
        payload = {"context": "planning" if planning else "existing_project", "title": "Fixture only",
                   "goals": "保存设计候选", "constraints": "不伪造实现", "description": "fixture"}
        if not planning: payload["repoPath"] = self.registered_key
        status, _, envelope = self.request("POST", "/api/archloop/workspaces", payload, auth=auth)
        self.assertEqual(status, 200, envelope)
        workspace = envelope["workspace"]["workspaceId"]
        path = "/api/archloop/workspaces/" + workspace
        status, _, candidate = self.request("POST", path + "/generate", {"mode": "rule_based"}, auth=auth)
        self.assertEqual(status, 200, candidate); self.assertEqual(candidate["origin"], "rule_based")
        status, _, applied = self.request("POST", path + "/apply-candidate", {
            "candidateId": candidate["candidateId"], "expectedDraftRevision": None}, auth=auth)
        self.assertEqual(status, 200, applied)
        return path, applied

    def preview(self, path, auth):
        status, _, body = self.request("POST", path + "/review-preview", {
            "actor": "FORGED_CLIENT_ACTOR", "reason": "FIXTURE simulated decision"}, auth=auth)
        self.assertEqual(status, 200, body)
        return body

    def test_unauthenticated_api_static_and_writes_are_blocked(self):
        for path in ("/api/archloop", "/api/repo-explorer/tree", "/web/styles.css"):
            self.assertEqual(self.request("GET", path)[0], 401)
        self.assertEqual(self.request("POST", "/api/archloop/workspaces", {})[0], 401)
        self.assertEqual(self.request("GET", "/", origin=None)[0], 303)
        self.assertEqual(self.request("GET", "/login", origin=None)[0], 200)

    def test_authenticated_ui_keeps_route_and_get_backend_without_private_paths(self):
        auth = self.login()
        status, _, page = self.request("GET", "/", auth=auth, origin=None)
        self.assertEqual(status, 200); self.assertIn(b"/auth-client.js", page)
        status, _, body = self.request("GET", "/api/archloop/backend", auth=auth, origin=None)
        self.assertEqual(status, 200, body); self.assertTrue(body["versionService"]["available"])
        self.assertNotIn(str(self.root), json.dumps(body))

    def test_csrf_cross_site_wrong_host_and_forged_identity_are_rejected(self):
        auth = self.login()
        for options in ({"auth": {"Cookie": auth["Cookie"]}}, {"auth": auth, "origin": None},
                        {"auth": auth, "origin": "https://evil.example.invalid"},
                        {"auth": auth, "headers": {"Host": "127.0.0.1:" + str(self.port)}},
                        {"headers": {"X-Forwarded-User": "fixture", "X-ProjectMind-Actor": "fixture"}}):
            self.assertIn(self.request("POST", "/api/archloop/workspaces", {}, **options)[0], (401, 403))

    def test_registry_prevents_arbitrary_server_repository_access(self):
        auth = self.login()
        for path in (str(self.code), "/private/fixture-only", "registered:missing"):
            status, _, body = self.request("POST", "/api/archloop/workspaces", {
                "context": "existing_project", "title": "fixture", "repoPath": path}, auth=auth)
            self.assertEqual(status, 403, body)

    def test_existing_project_real_review_publish_and_other_session_reads_version(self):
        auth, other = self.login(), self.login()
        code_before = (run_git(self.code, "rev-parse", "HEAD"), run_git(self.code, "status", "--porcelain"))
        path, _ = self.workspace(auth)
        preview = self.preview(path, auth)
        for second in (other,):
            status, _, body = self.request("POST", path + "/review-confirm", {
                "previewDigest": preview["previewDigest"], "decision": "accept"}, auth=second)
            self.assertEqual(status, 403, body)
        status, _, confirmation = self.request("POST", path + "/review-confirm", {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, auth=auth)
        self.assertEqual(status, 200, confirmation)
        self.assertEqual(self.request("POST", path + "/publish", {}, auth=other)[0], 403)
        status, _, published = self.request("POST", path + "/publish", {}, auth=auth)
        self.assertEqual(status, 200, published)
        self.assertEqual(published["envelope"]["lastPublish"]["actor"], "fixture")
        self.assertEqual(published["version"]["codeRevision"], code_before[0])
        self.assertEqual(published["provenance"]["mapSourceRevision"], run_git(self.arch, "rev-parse", "HEAD"))
        status, _, opened = self.request("GET", path, auth=other)
        self.assertEqual(status, 200); self.assertEqual(opened["identity"]["mapRevision"], published["version"]["mapRevision"])
        self.assertEqual(code_before, (run_git(self.code, "rev-parse", "HEAD"), run_git(self.code, "status", "--porcelain")))

    def test_planning_design_has_no_fake_code_sha_and_survives_new_instance(self):
        auth = self.login(); path, _ = self.workspace(auth, planning=True)
        preview = self.preview(path, auth)
        self.assertFalse(preview["verifyCode"])
        self.assertEqual(self.request("POST", path + "/review-confirm", {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, auth=auth)[0], 200)
        status, _, body = self.request("POST", path + "/publish", {}, auth=auth)
        self.assertEqual(status, 200, body)
        self.assertIsNone(body["version"]["codeRevision"]); self.assertIsNone(body["version"]["verifiedCodeRevision"])
        rebuilt = build_application(self.config)
        workspace = path.rsplit("/", 1)[1]
        reopened = rebuilt.service.open_workspace(workspace)
        self.assertEqual(reopened["identity"]["mapRevision"], body["version"]["mapRevision"])

    def test_logout_and_new_login_cannot_confirm_old_browser_preview(self):
        auth = self.login(); path, _ = self.workspace(auth); preview = self.preview(path, auth)
        self.assertEqual(self.request("POST", "/api/auth/logout", {}, auth=auth)[0], 200)
        self.assertEqual(self.request("GET", path, auth=auth)[0], 401)
        renewed = self.login()
        status, _, body = self.request("POST", path + "/review-confirm", {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, auth=renewed)
        self.assertEqual(status, 403, body)


    def test_malformed_deep_or_nonfinite_json_is_400_without_writing_workspace(self):
        auth = self.login()
        before = self.request('GET', '/api/archloop/workspaces', auth=auth)[2]
        cases = [b'{"context":"planning","title":"fixture","extra":'+b'['*1600+b'0'+b']'*1600+b'}',
                 b'{"context":"planning","title":"fixture","extra":'+b'['*65+b'0'+b']'*65+b'}',
                 b'{"context":"planning","title":"fixture","extra":NaN}',
                 b'{"context":"planning","title":"fixture","extra":Infinity}',
                 b'{"context":"planning","title":"fixture","extra":1e9999}']
        for raw in cases:
            with self.subTest(raw=raw[:50]):
                connection = HTTPConnection('127.0.0.1', self.port, timeout=10)
                try:
                    connection.request('POST', '/api/archloop/workspaces', body=raw, headers={
                        'Host': 'projectmind.example.invalid', 'Origin': ORIGIN,
                        'Content-Type': 'application/json', **auth})
                    response = connection.getresponse()
                    value = json.loads(response.read())
                    self.assertEqual(response.status, 400, value)
                    self.assertEqual(value['error']['code'], 'INVALID_INPUT')
                finally:
                    connection.close()
        self.assertEqual(before, self.request('GET', '/api/archloop/workspaces', auth=auth)[2])

    def test_review_mode_rejects_coercion_before_generating_preview(self):
        auth = self.login(); path, _ = self.workspace(auth)
        for value in ("false", "true", 0, 1, [], {}):
            with self.subTest(value=value):
                status, _, result = self.request('POST', path + '/review-preview',
                    {'reason': 'Fixture malformed review mode', 'verifyCode': value}, auth=auth)
                self.assertEqual(status, 400, result)
                self.assertEqual(result['error']['code'], 'VALIDATION_FAILED')
        for value in (True, False):
            status, _, result = self.request('POST', path + '/review-preview',
                {'reason': 'Fixture explicit review mode', 'verifyCode': value}, auth=auth)
            self.assertEqual(status, 200, result)
            self.assertIs(result['verifyCode'], value)

    def test_published_version_detail_accepts_encoded_and_literal_revision(self):
        from urllib.parse import quote
        auth = self.login()
        path, envelope = self.workspace(auth)
        status, _, preview = self.request('POST', path + '/review-preview',
            {'reason': 'FIXTURE ONLY scoped code evidence review', 'verifyCode': True}, auth=auth)
        self.assertEqual(status, 200, preview)
        self.assertEqual(self.request('POST', path + '/review-confirm',
            {'previewDigest': preview['previewDigest'], 'decision': 'accept'}, auth=auth)[0], 200)
        status, _, published = self.request('POST', path + '/publish', {}, auth=auth)
        self.assertEqual(status, 200, published)
        revision = published['version']['mapRevision']
        for segment in (revision, quote(revision, safe='')):
            status, _, detail = self.request('GET', path + '/versions/' + segment, auth=auth)
            self.assertEqual(status, 200, detail)
            self.assertEqual(detail['version']['mapRevision'], revision)

if __name__ == "__main__": unittest.main()
