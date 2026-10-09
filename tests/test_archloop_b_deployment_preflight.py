"""Deployment diagnostics exercise real loopback reads, never fake public access."""
from contextlib import contextmanager
from http.client import BadStatusLine
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from extensions.architecture_workspace.deployment_preflight import (
    MAX_RESPONSE, _probe, collect, run, validate_origin)
from extensions.architecture_workspace.errors import WorkspaceError


@contextmanager
def local_server(reply):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append({"method": self.command, "path": self.path,
                          "host": self.headers.get("Host"),
                          "origin": self.headers.get("Origin")})
            status, body = reply(calls[-1])
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class DeploymentPreflightTests(unittest.TestCase):
    def test_base_rejects_remote_hosts_credentials_and_url_components(self):
        for value in (None, "", "http://localhost:8765", "http://example.invalid:8765",
                      "https://127.0.0.1:8765", "http://127.0.0.1", "http://127.0.0.1:0",
                      "http://127.0.0.1:65536", "http://@127.0.0.1:8765",
                      "http://user:pass@127.0.0.1:8765", "http://127.0.0.1:8765/",
                      "http://127.0.0.1:8765?x", "http://127.0.0.1:8765#x",
                      "http://127.0.0.1:8765\r\nOrigin: evil", " http://127.0.0.1:8765"):
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                validate_origin(value)

    def test_public_origin_requires_https_domain_without_credential_or_path(self):
        for value in ("http://demo.example.invalid", "https://localhost", "https://a.local",
                      "https://127.0.0.1", "https://[::1]", "https://demo.example.invalid:443",
                      "https://demo.example.invalid:bad", "https://@demo.example.invalid",
                      "https://key:secret@demo.example.invalid", "https://demo.example.invalid/",
                      "https://demo.example.invalid?x", "https://demo.example.invalid#x",
                      "https://demo..example.invalid", "https://-demo.example.invalid",
                      "https://demo_.example.invalid", "https://例子.example.invalid"):
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                validate_origin(value, public=True)
        self.assertEqual(validate_origin("https://demo.example.invalid:8443", public=True).port, 8443)
        self.assertEqual(validate_origin("http://127.0.0.1:8765").port, 8765)

    def test_ambiguous_origin_spelling_is_rejected(self):
        for value, public in (("https://Demo.example.invalid", True),
                              ("https://demo.example.invalid:", True),
                              ("https://demo.example.invalid:08443", True),
                              ("http://127.0.0.1:08765", False)):
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                validate_origin(value, public=public)

    def test_eight_real_reads_preserve_host_and_origin_without_claiming_ready(self):
        def reply(call):
            if call["host"].startswith("demo.example.invalid"):
                return 403, {"error": {"code": "FORBIDDEN_HOST"}}
            if call["origin"] == "https://demo.example.invalid":
                return 403, {"error": {"code": "FORBIDDEN_ORIGIN"}}
            return 200, {"versionService": {"available": True}}

        with local_server(reply) as (base, calls):
            report = collect(base, "https://demo.example.invalid")
        self.assertEqual(len(calls), 8)
        self.assertTrue(all(c["method"] == "GET" for c in calls))
        self.assertEqual([c["origin"] for c in calls],
                         [base, base, None, None] + ["https://demo.example.invalid"] * 4)
        self.assertEqual([c["host"] for c in calls][4:6], ["demo.example.invalid"] * 2)
        self.assertEqual([o.get("errorCode") for o in report["observations"]][4:],
                         ["FORBIDDEN_HOST"] * 2 + ["FORBIDDEN_ORIGIN"] * 2)
        self.assertEqual(report["status"], "NOT_READY_FOR_PUBLIC_DEPLOYMENT")
        self.assertFalse(report["writePerformed"])
        self.assertFalse(report["publicDomainResolved"])

    def test_200_for_external_headers_never_proves_auth_tls_or_remote_access(self):
        with local_server(lambda _: (200, {})) as (base, _):
            report = collect(base, "https://demo.example.invalid")
        self.assertEqual(report["status"], "NOT_READY_FOR_PUBLIC_DEPLOYMENT")
        self.assertEqual({b["code"] for b in report["blockers"]}, {
            "PUBLIC_NETWORK_NOT_RUN", "INGRESS_AUTH_NOT_VERIFIED",
            "PROXY_TLS_NOT_VERIFIED", "PUBLIC_REVIEW_NOT_RUN"})

    def test_sanitized_report_discards_nested_private_response_fields(self):
        secret = "FIXTURE_ONLY_PRIVATE_VALUE"
        body = {"service": "architecture-workbench", "generation": {"configured": False, "model": secret},
                "versionService": {"available": True, "dataRoot": "/private/fixture", "reason": secret},
                "sessionId": secret, "csrfToken": secret, "deep": [{"key": secret}],
                "error": {"code": secret, "message": secret}}
        with local_server(lambda _: (200, body)) as (base, _):
            report = collect(base, "https://demo.example.invalid")
        serialized = json.dumps(report)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("/private/fixture", serialized)
        self.assertFalse(report["rawResponsesPersisted"])
        self.assertTrue(report["observations"][0]["bAvailableReported"])
        self.assertFalse(report["observations"][0]["aiConfiguredReported"])

    def test_oversized_and_non_json_responses_are_bounded_failures(self):
        for raw, code in ((b"x" * (MAX_RESPONSE + 1), "RESPONSE_TOO_LARGE"),
                          (b"redirect or non-JSON", "INVALID_JSON")):
            with self.subTest(code=code), local_server(lambda _: (200, raw)) as (base, _):
                report = collect(base, "https://demo.example.invalid")
                self.assertTrue(all(o["probeError"] == code for o in report["observations"]))
                self.assertIn("LOCAL_SERVICE_NOT_READY", {b["code"] for b in report["blockers"]})

    def test_redirect_is_observed_and_not_followed(self):
        with local_server(lambda _: (302, {"target": "https://elsewhere.example.invalid"})) as (base, calls):
            report = collect(base, "https://demo.example.invalid")
        self.assertEqual(len(calls), 8)
        self.assertTrue(all(o["httpStatus"] == 302 for o in report["observations"]))

    def test_invalid_http_and_connection_failure_are_controlled(self):
        for failure in (BadStatusLine("FIXTURE_ONLY_PRIVATE_VALUE"), OSError("fixture path")):
            with self.subTest(failure=type(failure).__name__), patch(
                    "extensions.architecture_workspace.deployment_preflight.HTTPConnection") as connection:
                connection.return_value.getresponse.side_effect = failure
                result = _probe(validate_origin("http://127.0.0.1:8765"), "/api/archloop",
                                host="127.0.0.1:8765", origin=None)
                self.assertEqual(result["probeError"], type(failure).__name__)
                self.assertNotIn(str(failure), json.dumps(result))
                connection.return_value.close.assert_called_once()

    def test_report_requires_new_non_git_output_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            existing = root / "existing"
            existing.mkdir()
            marker = existing / "marker"
            marker.write_text("keep")
            with self.assertRaises(WorkspaceError):
                run(existing, base_url="http://127.0.0.1:8765", public_origin="https://demo.example.invalid")
            self.assertEqual(marker.read_text(), "keep")
            checkout = root / "checkout"
            checkout.mkdir(); (checkout / ".git").mkdir()
            with self.assertRaises(WorkspaceError):
                run(checkout / "report", base_url="http://127.0.0.1:8765",
                    public_origin="https://demo.example.invalid")
            self.assertFalse((checkout / "report").exists())
            with self.assertRaises(WorkspaceError):
                run(root / "invalid", base_url="http://remote.example.invalid:8765",
                    public_origin="https://demo.example.invalid")
            self.assertFalse((root / "invalid").exists())

    def test_new_output_contains_sanitized_evidence(self):
        with tempfile.TemporaryDirectory() as temporary, local_server(lambda _: (200, {})) as (base, _):
            output = Path(temporary).resolve() / "evidence"
            report = run(output, base_url=base, public_origin="https://demo.example.invalid")
            self.assertEqual(json.loads((output / "DEPLOYMENT_PREFLIGHT.json").read_text()), report)
            self.assertEqual(sorted(p.name for p in output.iterdir()), ["DEPLOYMENT_PREFLIGHT.json"])

    def test_unwritable_evidence_is_controlled_and_does_not_expose_path(self):
        with patch("extensions.architecture_workspace.deployment_preflight._new_root",
                   side_effect=PermissionError("/private/fixture-only")):
            with self.assertRaises(WorkspaceError) as caught:
                run("/private/fixture-only", base_url="http://127.0.0.1:8765",
                    public_origin="https://demo.example.invalid")
        self.assertEqual(caught.exception.code, "STORAGE_FAILED")
        self.assertNotIn("/private/fixture-only", str(caught.exception.as_dict()))


if __name__ == "__main__":
    unittest.main()
