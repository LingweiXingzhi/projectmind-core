"""Regression tests for this round's integration repairs.

Covers, one test class per finding family:
- GEN-01 (BATCH-4 P1): abbreviated camelCase credential keys must be filtered
  before a real model call; ordinary configuration must still pass.
- ACCEPTANCE-01 (BATCH-4 P2): T24 proves the revision under audit by reading
  this checkout's HEAD with Git, not by echoing the service response.
- D-A-02: the public write seam requires a live server-side session and its
  anti-forgery token (machine codes FORBIDDEN_SESSION / FORBIDDEN_CSRF).
- D-A-03: C's candidate engine and D's fix-task service register as the real
  adapter capabilities, and the A→D request adaptation is server-bound.
- D-C-01/02/03: deviation evidence identity, content-bound proposalIds and a
  self-candidate whose evidence exists at its pinned commit.
- D-BC-01: the frozen C→B adapter is accepted by B's real validator.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import app as app_module
from archloop import backend_c
from archloop.backend_d import _derive_scope, _normalize_evidence, _normalize_expected_process_ref
from archloop.contract import ContractError
from archloop.context_pack import _key_name_is_secret, _looks_like_secret
from archloop.web_session import SESSION_COOKIE, WriteSessionRegistry, parse_session_cookie


class GodKeyAcronymTests(unittest.TestCase):
    """GEN-01: acronym camelCase keys are credentials, ordinary keys are not."""

    def test_abbreviated_camel_case_credential_keys_are_detected(self) -> None:
        for name in ("clientAPIKey", "APIKey", "apiKey", "CLIENTAPIKEY", "clientSecretKey",
                     "APIToken", "apiToken", "clientSECRET", "ACCESS_TOKEN", "idToken"):
            self.assertTrue(_key_name_is_secret(name), name)

    def test_ordinary_names_still_pass(self) -> None:
        for name in ("monkey", "donkey", "turkey", "keynote", "keyboard", "key_path",
                     "service_name", "client_id", "APIEndpoint", "APIBase"):
            self.assertFalse(_key_name_is_secret(name), name)

    def test_content_detection_catches_dict_forms(self) -> None:
        self.assertTrue(_looks_like_secret(
            'SETTINGS = {"clientAPIKey": "SYNTHETIC_TEST_CREDENTIAL_1234567890"}'))
        self.assertTrue(_looks_like_secret(
            "CONFIG = {'APIKey': 'SYNTHETIC_TEST_CREDENTIAL_1234567890'}"))
        self.assertTrue(_looks_like_secret(
            'A = {"clientAPIKey": "SYNTHETIC_TEST_CREDENTIAL_1234567890"}'))
        self.assertFalse(_looks_like_secret('SETTINGS = {"APIEndpoint": "https://api.example.invalid/v1"}'))
        self.assertFalse(_looks_like_secret('SETTINGS = {"monkey": "LongNonSensitiveAnimalName"}'))


class AcceptanceIndependentHeadTests(unittest.TestCase):
    """ACCEPTANCE-01: the T24 verdict uses the independently read HEAD."""

    def test_response_echo_of_another_commit_fails(self) -> None:
        from archloop.acceptance import self_coverage_verdict
        # a service that echoes a *different but existing* commit must fail when
        # the independently read local HEAD disagrees
        status, evidence = self_coverage_verdict(
            200, {"graph": {"nodes": [{"id": "n"}]},
                  "contextCoverage": {"codeRevision": "a" * 40, "trackedFiles": 10, "pythonFiles": 3}},
            str(REPO_ROOT), identity={"repoPath": str(REPO_ROOT), "codeRevision": "a" * 40},
            revision_exists=True, expected_revision="b" * 40,
            expected_tracked=10, expected_python=3)
        self.assertEqual(status, "FAIL")
        self.assertFalse(evidence["revisionMatchesCoverage"])

    def test_independent_head_matches_are_pass(self) -> None:
        from archloop.acceptance import self_coverage_verdict
        head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, encoding="utf-8").stdout.strip()
        tracked = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "-z", "--name-only", head],
                                 capture_output=True, text=True, encoding="utf-8").stdout.split("\0")
        tracked_count = len([p for p in tracked if p])
        python_count = len([p for p in tracked if p.endswith(".py")])
        status, _ = self_coverage_verdict(
            200, {"graph": {"nodes": [{"id": "n"}]},
                  "contextCoverage": {"codeRevision": head, "trackedFiles": tracked_count,
                                      "pythonFiles": python_count}},
            str(REPO_ROOT), identity={"repoPath": str(REPO_ROOT), "codeRevision": head},
            revision_exists=True, expected_revision=head,
            expected_tracked=tracked_count, expected_python=python_count)
        self.assertEqual(status, "PASS")


class WriteSessionRegistryTests(unittest.TestCase):
    """D-A-02: the registry refuses missing, foreign and expired credentials."""

    def test_issue_and_verify(self) -> None:
        registry = WriteSessionRegistry()
        issued = registry.issue("张三")
        session = registry.verify(issued["sessionId"], issued["csrfToken"])
        self.assertEqual(session["operator"], "张三")

    def test_missing_session_and_csrf_are_refused(self) -> None:
        registry = WriteSessionRegistry()
        with self.assertRaises(ContractError) as missing:
            registry.verify(None, None)
        self.assertEqual(missing.exception.code, "FORBIDDEN_SESSION")
        issued = registry.issue("")
        with self.assertRaises(ContractError) as csrf:
            registry.verify(issued["sessionId"], "not-the-token")
        self.assertEqual(csrf.exception.code, "FORBIDDEN_CSRF")

    def test_expired_session_is_refused(self) -> None:
        registry = WriteSessionRegistry(ttl_seconds=0)
        issued = registry.issue("")
        registry._sessions[issued["sessionId"]]["lastSeen"] -= 10
        with self.assertRaises(ContractError) as expired:
            registry.verify(issued["sessionId"], issued["csrfToken"])
        self.assertEqual(expired.exception.code, "FORBIDDEN_SESSION")

    def test_cookie_parsing(self) -> None:
        self.assertEqual(parse_session_cookie(f"a=1; {SESSION_COOKIE}=xyz; b=2"), "xyz")
        self.assertIsNone(parse_session_cookie(None))
        self.assertIsNone(parse_session_cookie("other=1"))


class WriteSessionHTTPTests(unittest.TestCase):
    """D-A-02 over real HTTP: missing protection refused, legal path works."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(cls.tmp.name)
        service = app_module.WorkbenchService(tmp_path / "archloop-data", app_module.AdapterRegistry())
        cls.handler = app_module.make_handler(app_module.ROOT, None, archloop_service=service)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def _post(self, payload, headers=None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/archloop/workspaces",
            data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json",
                     "Origin": f"http://127.0.0.1:{self.port}", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _session(self, operator=""):
        url = f"http://127.0.0.1:{self.port}/api/archloop/session"
        if operator:
            url += "?operator=" + operator
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
            raw = response.headers.get("Set-Cookie") or ""
        jar = SimpleCookie()
        jar.load(raw)
        cookie = jar[SESSION_COOKIE].value if SESSION_COOKIE in jar else None
        return cookie, body.get("csrfToken")

    def test_write_without_session_is_refused(self) -> None:
        status, payload = self._post({"context": "planning", "title": "x", "goals": "y"})
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "FORBIDDEN_SESSION")

    def test_write_with_wrong_csrf_is_refused(self) -> None:
        cookie, _ = self._session()
        status, payload = self._post({"context": "planning", "title": "x", "goals": "y"},
                                     {"Cookie": f"{SESSION_COOKIE}={cookie}", "X-CSRF-Token": "wrong"})
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "FORBIDDEN_CSRF")

    def test_write_with_live_session_works(self) -> None:
        cookie, csrf = self._session()
        status, payload = self._post({"context": "planning", "title": "会话内写入", "goals": "y"},
                                     {"Cookie": f"{SESSION_COOKIE}={cookie}", "X-CSRF-Token": csrf})
        self.assertEqual(status, 200)
        self.assertTrue(payload["workspace"]["workspaceId"])

    def test_read_paths_do_not_need_a_session(self) -> None:
        with urllib.request.urlopen(
                urllib.request.Request(f"http://127.0.0.1:{self.port}/api/archloop", method="GET"),
                timeout=10) as response:
            self.assertEqual(response.status, 200)


class RegisteredBackendTests(unittest.TestCase):
    """D-A-03: registered capabilities are the modules the service calls."""

    def test_c_descriptor_is_registered_and_callable(self) -> None:
        service = app_module.WorkbenchService(Path(tempfile.mkdtemp()) / "data",
                                              app_module.AdapterRegistry())
        service.bind_backend_c()
        registered = service.adapter.listing()["registered"]
        self.assertEqual(registered.get("correction"), "extension:map_proposal")
        context = {"mode": "planning", "workspaceId": "ws_test",
                   "goals": [{"id": "req-1", "title": "登录", "description": "用户登录"}]}
        record = {"workspaceId": "ws_test",
                  "identity": {"codeRepoId": None, "codeRevision": None},
                  "goals": "支持登录与自然语言纠正"}
        reply = service._c_call("bootstrap_candidate", {"context": "planning", "record": record})
        self.assertTrue(reply["graph"]["nodes"])  # A projection of C's canonical candidate

    def test_d_backend_registers_when_available(self) -> None:
        from extensions.continuity.fix_tasks import FixTaskService
        from extensions.continuity.store import Store
        from archloop.backend_d import BackendD
        tmp = Path(tempfile.mkdtemp())
        service = app_module.WorkbenchService(tmp / "data", app_module.AdapterRegistry())
        fix_service = FixTaskService(Store(tmp / "continuity" / "records.sqlite3"),
                                     architecture_repo=tmp / "arch",
                                     code_repositories=[REPO_ROOT])
        backend = BackendD(service, fix_service, architecture_repo=tmp / "arch",
                           code_repositories={str(REPO_ROOT): str(REPO_ROOT)})
        self.assertTrue(backend.available)
        service.bind_backend_d(backend)
        self.assertEqual(service.adapter.listing()["registered"].get("handoff"),
                         "d_architecture_handoff_v1")
        status = service.backend_status()
        self.assertTrue(status["fixTasks"]["available"])


class AToDAdaptationTests(unittest.TestCase):
    """The A→D request adaptation refuses guesses and binds real values."""

    VERSION = {"codeRevision": "c" * 40, "codeRepoId": "repo-" + "d" * 64}

    def test_evidence_paths_become_code_observations(self) -> None:
        evidence = _normalize_evidence(["app.py", {"path": "a/b.py", "reason": "职责位置"}],
                                       version=self.VERSION)
        self.assertEqual([item["kind"] for item in evidence], ["code", "code"])
        self.assertEqual(evidence[0]["codeRepoId"], self.VERSION["codeRepoId"])
        self.assertEqual(evidence[1]["detail"], "职责位置")

    def test_free_text_evidence_is_refused(self) -> None:
        with self.assertRaises(ContractError) as bad:
            _normalize_evidence(["我觉得这里有问题"], version=self.VERSION)
        self.assertEqual(bad.exception.code, "VALIDATION_FAILED")

    def test_expected_process_shorthand_and_validation(self) -> None:
        graph = {"nodes": [{"id": "node-a", "steps": [{"stepId": "s1"}, {"stepId": "s2"}]}]}
        ref = _normalize_expected_process_ref("node-a/s1", graph=graph)
        self.assertEqual(ref, {"processId": "process-node-a", "stepIds": ["s1"]})
        with self.assertRaises(ContractError) as missing:
            _normalize_expected_process_ref("node-a/s9", graph=graph)
        self.assertEqual(missing.exception.code, "NOT_FOUND")

    def test_scope_derivation_and_unsafe_paths(self) -> None:
        from archloop.backend_d import _normalize_scope
        evidence = [{"kind": "code", "path": "app.py"}]
        self.assertEqual(_derive_scope({}, evidence), ["app.py"])
        with self.assertRaises(ContractError):
            _normalize_scope(_derive_scope({"scope": ["../outside/secret.py"]}, evidence))
        with self.assertRaises(ContractError):
            _normalize_scope(["C:/absolute/path.py"])


class CDeviationIdentityTests(unittest.TestCase):
    """D-C-01: evidence identity decides before any ALIGNED verdict."""

    GRAPH = {"mapRevision": "sha256:x", "codeRepoId": "repo-abc", "codeRevision": "a" * 40,
             "nodes": [{"nodeId": "node-B", "expectedProcesses": ["A", "B", "C"]}]}
    GOOD = {"called_steps": ["A", "B", "C"], "codeRepoId": "repo-abc", "codeRevision": "a" * 40}

    def _detect(self, traces):
        from extensions.map_proposal.candidates import detect_process_deviations
        return detect_process_deviations(json.loads(json.dumps(self.GRAPH)), traces)

    def test_bypass_is_detected_and_aligned_is_not_overclaimed(self) -> None:
        bypass = self._detect([{"called_steps": ["A", "B"], "codeRepoId": "repo-abc",
                                "codeRevision": "a" * 40}])
        self.assertEqual(bypass["verdict"], "DEVIATION_DETECTED")
        aligned = self._detect([self.GOOD])
        self.assertEqual(aligned["verdict"], "ALIGNED")
        self.assertEqual(aligned["coveredNodes"], ["node-B"])

    def test_wrong_repo_wrong_sha_unrelated_and_missing_are_unknown(self) -> None:
        wrong_repo = self._detect([{"called_steps": ["A", "B", "C"],
                                    "codeRepoId": "other-repo", "codeRevision": "a" * 40}])
        self.assertEqual(wrong_repo["verdict"], "UNKNOWN")
        self.assertTrue(wrong_repo["rejectedTraces"])
        wrong_sha = self._detect([{"called_steps": ["A", "B", "C"],
                                   "codeRepoId": "repo-abc", "codeRevision": "b" * 40}])
        self.assertEqual(wrong_sha["verdict"], "UNKNOWN")
        unrelated = self._detect([{"called_steps": ["X"], "codeRepoId": "repo-abc",
                                   "codeRevision": "a" * 40}])
        self.assertEqual(unrelated["verdict"], "UNKNOWN")
        missing = self._detect([{"called_steps": [], "codeRepoId": "repo-abc",
                                 "codeRevision": "a" * 40}])
        self.assertEqual(missing["verdict"], "UNKNOWN")


class CProposalIdentityTests(unittest.TestCase):
    """D-C-02: proposalId binds the semantic candidate content."""

    def test_planning_identity_follows_content(self) -> None:
        from extensions.map_proposal.candidates import generate_bootstrap_proposal
        base = {"mode": "planning", "workspaceId": "ws-1",
                "goals": [{"id": "req-1", "title": "登录", "description": "登录"}]}
        changed = json.loads(json.dumps(base))
        changed["goals"][0]["description"] = "完全不同的职责"
        first = generate_bootstrap_proposal(base)
        other = generate_bootstrap_proposal(changed)
        self.assertNotEqual(first["proposalId"], other["proposalId"])
        stable = generate_bootstrap_proposal(json.loads(json.dumps(base)))
        self.assertEqual(first["proposalId"], stable["proposalId"])

    def test_code_identity_follows_content(self) -> None:
        from extensions.map_proposal.candidates import generate_bootstrap_proposal
        context = {"mode": "existing_project", "workspaceId": "ws-1",
                   "codeRepoId": "repo-" + "a" * 64, "codeRevision": "b" * 40,
                   "facts": {"symbols": [{"path": "pkg/a.py", "name": "run", "kind": "function",
                                          "qualified_name": "pkg.a.run"}]}}
        other = json.loads(json.dumps(context))
        other["facts"]["symbols"].append({"path": "pkg/b.py", "name": "serve", "kind": "function",
                                          "qualified_name": "pkg.b.serve"})
        self.assertNotEqual(generate_bootstrap_proposal(context)["proposalId"],
                            generate_bootstrap_proposal(other)["proposalId"])


class FrozenCToBExchangeTests(unittest.TestCase):
    """D-BC-01: the one documented adapter makes C acceptable to B."""

    BASIS = {"workspaceId": "workspace-probe", "mapId": "map-probe", "mode": "planning",
             "codeRepoId": None, "codeRevision": None, "baseMapRevision": None,
             "draftId": None, "draftRevision": None}

    def test_planning_candidate_is_accepted_after_the_frozen_adapter(self) -> None:
        from extensions.architecture_workspace.proposals import validate_proposal
        from extensions.map_proposal.candidates import generate_bootstrap_proposal
        candidate = generate_bootstrap_proposal(
            {"mode": "planning", "workspaceId": "workspace-probe",
             "goals": [{"id": "req-one", "title": "Authentication", "description": "Login"}]})
        adapted = backend_c.to_b_proposal(candidate, context=self.BASIS)
        accepted = validate_proposal(adapted, self.BASIS)
        self.assertEqual(accepted["proposalId"], candidate["proposalId"])

    def test_raw_candidate_is_not_b_shape(self) -> None:
        from extensions.architecture_workspace.proposals import validate_proposal
        from extensions.map_proposal.candidates import generate_bootstrap_proposal
        candidate = generate_bootstrap_proposal(
            {"mode": "planning", "workspaceId": "workspace-probe",
             "goals": [{"id": "req-one", "title": "Authentication", "description": "Login"}]})
        with self.assertRaises(Exception):
            validate_proposal(candidate, self.BASIS)


class SelfCandidateEvidenceTests(unittest.TestCase):
    """D-C-03: claimed evidence exists as blobs at the pinned revision."""

    def test_evidence_is_real_at_pinned_revision(self) -> None:
        candidate_path = REPO_ROOT / "extensions" / "map_proposal" / "PROJECTMIND_SELF_CANDIDATE.json"
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        pin = candidate["codeRevision"]
        exists = subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e", pin + "^{commit}"],
                                capture_output=True, text=True, encoding="utf-8")
        if exists.returncode != 0:
            self.skipTest(f"pinned revision {pin[:12]} 不在本 clone 中（浅克隆），无法本地核对")
        missing = []
        for node in candidate["graphCandidate"]["nodes"]:
            for item in node.get("evidence", []):
                path = item.get("path")
                if not path:
                    continue
                probe = subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-t", f"{pin}:{path}"],
                                       capture_output=True, text=True, encoding="utf-8")
                if probe.returncode != 0 or probe.stdout.strip() != "blob":
                    missing.append((node["nodeId"], path, probe.stdout.strip() or "MISSING"))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()