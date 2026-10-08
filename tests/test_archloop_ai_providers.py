"""Provider-agnostic AI transport tests (real HTTP against a local stand-in).

These tests prove the "market API" path without any external network or key:
a local thread answers exactly like an OpenAI-compatible `/chat/completions`
provider (DeepSeek/DashScope/Moonshot/GLM/OpenRouter/vLLM/Ollama shape), and
the real workbench generation endpoint is driven against it. The Responses
protocol keeps its own shape, configuration is refused when malformed, and the
returned graph is validated in-process so a provider that ignores
`response_format` cannot smuggle a non-conforming object into a draft.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import app as app_module
from archloop import ai_transport
from archloop.ai_transport import AIError, ai_config, ai_status, call_model
from archloop.generate import GENERATION_SCHEMA

VALID_GRAPH = {
    "nodes": [
        {
            "id": "node_workbench",
            "title": "架构工作台",
            "summary": "起草候选、纠正并人审发布",
            "entryPoints": ["/api/archloop/workspaces"],
            "interfaces": ["WorkspaceService"],
            # planning workspaces refuse code_fact evidence: a design candidate
            # cites the requirement, not a code path (the guard rejects the
            # former outright, which is itself covered by the graph contract)
            "evidence": [{"path": "用户目标", "reason": "来自本次目标与约束", "kind": "requirement"}],
            "process": [
                {"stepId": "s1", "title": "起草", "detail": "生成候选",
                 "inputs": ["情况说明"], "outputs": ["候选图"], "branches": [], "next": []}
            ],
            "assumptions": [],
        }
    ],
    "edges": [],
    "unknowns": [],
    "openQuestions": [],
}


class _ProviderHandler(BaseHTTPRequestHandler):
    """A minimal OpenAI-compatible provider stand-in."""

    mode = "chat"
    reject_response_format = False
    payload_text = json.dumps(VALID_GRAPH, ensure_ascii=False)
    calls: list[dict] = []

    def log_message(self, *args):  # keep the test output quiet
        pass

    def _send(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        type(self).calls.append({"path": self.path, "auth": self.headers.get("Authorization", ""),
                                 "body": body})
        if self.path.endswith("/chat/completions"):
            if type(self).reject_response_format and "response_format" in body:
                return self._send(400, {"error": {"message": "response_format is not supported"}})
            return self._send(200, {"choices": [{"message": {"role": "assistant",
                                                             "content": type(self).payload_text}}]})
        if self.path.endswith("/responses"):
            return self._send(200, {"status": "completed",
                                    "output": [{"type": "message",
                                                "content": [{"type": "output_text",
                                                             "text": type(self).payload_text}]}]})
        return self._send(404, {"error": {"message": "not found"}})


class _Provider:
    def __init__(self, mode="chat", reject_response_format=False, payload_text=None):
        handler = type("H", (_ProviderHandler,), {"mode": mode,
                                                 "reject_response_format": reject_response_format,
                                                 "calls": []})
        if payload_text is not None:
            handler.payload_text = payload_text
        self.handler = handler
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}/v1"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class ChatCompletionsProviderTests(unittest.TestCase):
    """A real OpenAI-compatible provider drives the real generation path."""

    def setUp(self) -> None:
        self.provider = _Provider()
        self.addCleanup(self.provider.stop)
        self.env = unittest.mock.patch.dict(os.environ, {
            "PROJECTMIND_AI_API_KEY": "sk-test-not-a-real-key",
            "PROJECTMIND_AI_BASE_URL": self.provider.base,
            "PROJECTMIND_AI_MODEL": "deepseek-chat",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_config_and_status_show_provider_without_the_key(self) -> None:
        config = ai_config()
        self.assertEqual(config["protocol"], "chat_completions")
        self.assertEqual(config["model"], "deepseek-chat")
        status = ai_status()
        self.assertTrue(status["configured"])
        self.assertEqual(status["provider"], "127.0.0.1")
        self.assertNotIn("sk-test", json.dumps(status))

    def test_call_model_returns_a_schema_valid_graph(self) -> None:
        result = call_model("起草", {"goals": ["让下一个人接着做"]}, "projectmind_arch_candidate",
                            GENERATION_SCHEMA)
        self.assertEqual(result["nodes"][0]["id"], "node_workbench")
        call = self.provider.handler.calls[-1]
        self.assertTrue(call["path"].endswith("/v1/chat/completions"))
        self.assertEqual(call["auth"], "Bearer sk-test-not-a-real-key")
        self.assertEqual(call["body"]["response_format"], {"type": "json_object"})

    def test_real_generation_endpoint_produces_an_ai_candidate(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        service = app_module.WorkbenchService(tmp / "data", app_module.AdapterRegistry())
        handler = app_module.make_handler(app_module.ROOT, None, archloop_service=service)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)

        import urllib.request
        from tests.archloop_http_session import establish_session
        cookie, csrf = establish_session(f"http://127.0.0.1:{port}")

        def post(path, payload):
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json", "Cookie": cookie,
                         "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))

        workspace = post("/api/archloop/workspaces",
                         {"context": "planning", "title": "厂商路径", "goals": "让下一个人接着做"})
        workspace_id = workspace["workspace"]["workspaceId"]
        generated = post(f"/api/archloop/workspaces/{workspace_id}/generate", {"mode": "production"})
        self.assertEqual(generated["status"], "ai_generated")
        self.assertEqual(generated["origin"], "ai_generated")
        self.assertTrue(all(node["provenance"] == "ai_candidate" for node in generated["graph"]["nodes"]))

    def test_provider_without_response_format_still_works(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"PROJECTMIND_AI_BASE_URL": self.provider.base}):
            self.provider.handler.reject_response_format = True
            result = call_model("起草", {}, "s", GENERATION_SCHEMA)
        self.assertEqual(result["nodes"][0]["id"], "node_workbench")
        paths = [call["body"].get("response_format") for call in self.provider.handler.calls]
        self.assertIn({"type": "json_object"}, paths)
        self.assertIn(None, paths, "400 后应有一次不带 response_format 的重试")
        self.provider.handler.reject_response_format = False

    def test_non_conforming_output_is_refused(self) -> None:
        bad = _Provider(payload_text=json.dumps({"nodes": [{"id": "x"}]}, ensure_ascii=False))
        self.addCleanup(bad.stop)
        with unittest.mock.patch.dict(os.environ, {"PROJECTMIND_AI_BASE_URL": bad.base}):
            with self.assertRaises(AIError) as refused:
                call_model("起草", {}, "s", GENERATION_SCHEMA)
        self.assertIn("不符合约定结构", str(refused.exception))

    def test_unreadable_output_is_refused(self) -> None:
        bad = _Provider(payload_text="这不是 JSON")
        self.addCleanup(bad.stop)
        with unittest.mock.patch.dict(os.environ, {"PROJECTMIND_AI_BASE_URL": bad.base}):
            with self.assertRaises(AIError):
                call_model("起草", {}, "s", GENERATION_SCHEMA)


class ResponsesProtocolTests(unittest.TestCase):
    """api.openai.com keeps the Responses shape; other bases switch."""

    def test_auto_protocol_selection(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"PROJECTMIND_AI_MODEL": "gpt-4o-mini",
                                                   "OPENAI_API_KEY": "k"}, clear=False):
            os.environ.pop("PROJECTMIND_AI_BASE_URL", None)
            os.environ.pop("PROJECTMIND_AI_PROTOCOL", None)
            config = ai_config()
        self.assertEqual(config["protocol"], "responses")
        self.assertEqual(config["base"], ai_transport.DEFAULT_BASE_URL)

    def test_responses_endpoint_shape(self) -> None:
        provider = _Provider(mode="responses")
        self.addCleanup(provider.stop)
        with unittest.mock.patch.dict(os.environ, {
                "OPENAI_API_KEY": "sk-test", "PROJECTMIND_AI_MODEL": "gpt-4o-mini",
                "PROJECTMIND_AI_PROTOCOL": "responses",
                "PROJECTMIND_AI_BASE_URL": provider.base}, clear=False):
            os.environ.pop("PROJECTMIND_AI_API_KEY", None)
            result = call_model("起草", {}, "s", GENERATION_SCHEMA)
        self.assertEqual(result["nodes"][0]["id"], "node_workbench")
        self.assertTrue(provider.handler.calls[-1]["path"].endswith("/v1/responses"))


class ConfigurationRefusalTests(unittest.TestCase):
    """Server-side configuration is validated; nothing comes from the client."""

    def test_bad_base_url_and_protocol_are_refused(self) -> None:
        for bad in ({"PROJECTMIND_AI_BASE_URL": "ftp://example.invalid/v1"},
                    {"PROJECTMIND_AI_BASE_URL": "https://user:pass@example.invalid/v1"},
                    {"PROJECTMIND_AI_BASE_URL": "not-a-url"},
                    {"PROJECTMIND_AI_PROTOCOL": "grpc"}):
            with self.subTest(bad):
                with unittest.mock.patch.dict(os.environ, bad):
                    with self.assertRaises(AIError):
                        ai_config()
                status = ai_status()
                self.assertFalse(status["configured"])

    def test_unconfigured_status_is_honest(self) -> None:
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            status = ai_status()
        self.assertFalse(status["configured"])
        self.assertIn("尚未配置", status["note"])


if __name__ == "__main__":
    unittest.main()