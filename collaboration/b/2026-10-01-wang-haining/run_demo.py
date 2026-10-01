"""Standalone local harness. Not a replacement for the team's app.py."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "reference"))
from extension_host import ExtensionContext, ExtensionError, ExtensionHost
from extensions.code_facts.facts import collect_code_facts, current_revision, repository_root


def create_demo_repo(root: Path) -> str:
    """The only Git writes are in a newly created disposable demo directory."""
    (root / "user.py").write_text(
        '# 演示代码：用于检查名称和行号\n'
        'def login(username):\n    return bool(username)\n\n'
        'class UserService:\n'
        '    def save(self, user):\n        return user\n\n'
        '    async def fetch(self, user_id):\n        return user_id\n', encoding="utf-8",
    )
    (root / "utils.py").write_text(
        'def normalize_name(value):\n    return value.strip()\n\n'
        'def outer():\n    def inner():\n        return 1\n    return inner\n', encoding="utf-8",
    )
    (root / "empty.py").write_text('VERSION = "1.0"\n', encoding="utf-8")
    (root / "broken.py").write_text('def unfinished(\n', encoding="utf-8")
    (root / "notes.md").write_text('人工演示文件，不是 Python。\n', encoding="utf-8")
    (root / "image.bin").write_bytes(b"\x00\x01demo")
    commands = [("init", "-q"), ("add", "--", "."),
                ("-c", "user.name=Local Demo", "-c", "user.email=demo@example.invalid",
                 "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                 "commit", "-qm", "Local code facts demo")]
    for command in commands:
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(["git", "-C", str(root), *command], check=True, capture_output=True,
                       env=env, timeout=10)
    return current_revision(root)


def make_server(repo: Path, port: int = 8876) -> ThreadingHTTPServer:
    context = ExtensionContext(
        repo=repo, map_path=repo / "unused-demo-map.json",
        snapshot=lambda: {"repository": repo.name, "revision": current_revision(repo)},
        compare=lambda *_: {},
    )
    host = ExtensionHost(ROOT / "extensions", context)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_content(self, status, body: bytes, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def respond(self, status, value: dict):
            self.send_content(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))

        def dispatch(self, method):
            url = urlsplit(self.path)
            try:
                if method == "GET" and url.path in ("/", "/ext/code_facts"):
                    self.send_content(200, host.page("code_facts", ROOT / "extensions/code_facts/index.html"),
                                      "text/html; charset=utf-8")
                    return
                if method == "GET" and url.path == "/api/snapshot":
                    self.respond(200, context.snapshot())
                    return
                if method == "GET" and url.path == "/api/extensions":
                    self.respond(200, host.listing())
                    return
                if url.path != "/api/extensions/code_facts":
                    raise ExtensionError(HTTPStatus.NOT_FOUND, "页面或接口不存在")
                if method == "GET":
                    data = {key: values[0] for key, values in parse_qs(url.query, keep_blank_values=True).items()}
                else:
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                        raise ExtensionError(HTTPStatus.BAD_REQUEST, "POST 必须使用 application/json")
                    if self.headers.get("Transfer-Encoding"):
                        raise ExtensionError(HTTPStatus.BAD_REQUEST, "不支持分块请求")
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                    except ValueError:
                        raise ExtensionError(HTTPStatus.BAD_REQUEST, "请求长度无效")
                    if not 0 < length <= 65536:
                        raise ExtensionError(HTTPStatus.BAD_REQUEST, "JSON 请求须在 1–65,536 字节之间")
                    try:
                        data = json.loads(self.rfile.read(length))
                    except (ValueError, UnicodeError):
                        raise ExtensionError(HTTPStatus.BAD_REQUEST, "JSON 无效")
                    if not isinstance(data, dict):
                        raise ExtensionError(HTTPStatus.BAD_REQUEST, "JSON 必须是对象")
                self.respond(200, host.run("code_facts", method, data))
            except ExtensionError as exc:
                self.respond(exc.status, {"error": str(exc)})
            except Exception:
                self.respond(500, {"error": "本地服务读取失败"})

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description="B 代码事实本地首版")
    parser.add_argument("--repo", type=Path, help="只读分析现有仓库；省略则创建临时演示仓库")
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--export-example", type=Path, help="导出实际演示结果后退出")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="projectmind-b-demo-") as directory:
        repo = repository_root(args.repo) if args.repo else Path(directory)
        revision = current_revision(repo) if args.repo else create_demo_repo(repo)
        if args.export_example:
            args.export_example.write_text(
                json.dumps(collect_code_facts(repo, revision), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("已生成真实示例：", args.export_example)
            return
        server = make_server(repo, args.port)
        print(f"B 本地首版：http://127.0.0.1:{server.server_port}/ext/code_facts", flush=True)
        print(f"演示来源：{repo}\n提交：{revision}", flush=True)
        print("Ctrl+C 停止。临时演示仓库在停止后清理。", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
