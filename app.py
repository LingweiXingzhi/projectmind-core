"""Local first slice of ProjectMind: a curated map with Git-pinned evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
MAP_PATH = ROOT / "data" / "project-map.json"
WEB_PATH = ROOT / "web"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


class GitError(Exception):
    """Git could not provide the requested repository fact."""


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(message or f"git {' '.join(args)} failed")
    return result.stdout


def commit_id(repo: Path, ref: str = "HEAD") -> str:
    if ref != "HEAD" and not SHA_PATTERN.fullmatch(ref):
        raise ValueError("Commit must be a full Git SHA")
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def files_at_commit(repo: Path, commit: str) -> set[str]:
    raw = git(repo, "ls-tree", "-r", "-z", "--name-only", commit)
    return {part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part}


def load_map(map_path: Path) -> dict:
    with map_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_snapshot(repo: Path, map_path: Path, revision: str = "HEAD") -> dict:
    commit = commit_id(repo, revision)
    tracked = files_at_commit(repo, commit)
    try:
        parent = git(repo, "rev-parse", "--verify", f"{commit}^").decode().strip()
    except GitError:
        parent = None
    curated = load_map(map_path)
    nodes = []
    for node in curated["nodes"]:
        evidence = [
            {**item, "existsAtCommit": item["path"] in tracked}
            for item in node["evidence"]
        ]
        nodes.append({**node, "evidence": evidence})
    try:
        branch = git(repo, "symbolic-ref", "--short", "HEAD").decode().strip()
    except GitError:
        branch = "detached HEAD"
    return {
        "repository": repo.name,
        "revision": commit,
        "parentRevision": parent,
        "branch": branch,
        "mapOrigin": "curated_demo",
        "mapNote": curated["note"],
        "nodes": nodes,
        "edges": curated["edges"],
    }


def compare_commits(repo: Path, map_path: Path, base_ref: str, target_ref: str) -> dict:
    base = commit_id(repo, base_ref)
    target = commit_id(repo, target_ref)
    raw = git(repo, "diff", "--name-status", "-z", "-M", base, target, "--")
    parts = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
    changes = []
    index = 0
    while index < len(parts):
        code = parts[index]
        index += 1
        if code.startswith(("R", "C")):
            old_path, path = parts[index:index + 2]
            index += 2
            changes.append({"code": code, "oldPath": old_path, "path": path})
        else:
            path = parts[index]
            index += 1
            changes.append({"code": code, "path": path})

    changed_paths = {path for change in changes for path in (change["path"], change.get("oldPath")) if path}
    curated = load_map(map_path)
    candidates = []
    for node in curated["nodes"]:
        matching = sorted({item["path"] for item in node["evidence"] if item["path"] in changed_paths})
        if matching:
            candidates.append({"nodeId": node["id"], "changedEvidencePaths": matching})
    return {
        "baseRevision": base,
        "targetRevision": target,
        "changes": changes,
        "reviewCandidates": candidates,
        "note": "待复核仅表示节点声明的来源文件出现在 Git 差异中；它不证明功能或架构发生变化。",
    }


def export_markdown(snapshot: dict, comparison: dict | None = None) -> str:
    titles = {node["id"]: node["title"] for node in snapshot["nodes"]}
    lines = [
        f"# {snapshot['repository']} · 功能地图演示",
        "",
        f"Git 提交：{snapshot['revision']}",
        "",
        f"> {snapshot['mapNote']}",
        "",
    ]
    for node in snapshot["nodes"]:
        lines.extend([f"## {node['title']}", "", node["summary"], "", f"关键入口：{node['entryPoint']}", "", "来源："])
        for item in node["evidence"]:
            state = "该提交中存在" if item["existsAtCommit"] else "该提交中缺失"
            lines.append(f"- {item['path']} — {state}；{item['reason']}")
        lines.append("")
    lines.extend(["## 关系", ""])
    for edge in snapshot["edges"]:
        lines.append(f"- {titles.get(edge['from'], edge['from'])} → {titles.get(edge['to'], edge['to'])}：{edge['label']}")
    if comparison:
        lines.extend(["", "## Git 变化与待复核候选", "", f"基准提交：{comparison['baseRevision']}", f"目标提交：{comparison['targetRevision']}", "", f"> {comparison['note']}", ""])
        for change in comparison["changes"]:
            display_path = f"{change['oldPath']} → {change['path']}" if "oldPath" in change else change["path"]
            lines.append(f"- {change['code']} {display_path}")
        lines.extend(["", "待复核节点："])
        for candidate in comparison["reviewCandidates"]:
            lines.append(f"- {titles.get(candidate['nodeId'], candidate['nodeId'])}：{', '.join(candidate['changedEvidencePaths'])}")
    return "\n".join(lines) + "\n"


def read_evidence(repo: Path, map_path: Path, path: str, revision: str) -> dict:
    curated = load_map(map_path)
    allowed = {item["path"] for node in curated["nodes"] for item in node["evidence"]}
    if path not in allowed:
        raise ValueError("Evidence path is not declared in this map")
    commit = commit_id(repo, revision)
    if path not in files_at_commit(repo, commit):
        raise FileNotFoundError(f"{path} is absent at this commit")
    content = git(repo, "show", f"{commit}:{path}").decode("utf-8", errors="replace")
    return {
        "path": path,
        "revision": commit,
        "content": content[:12000],
        "truncated": len(content) > 12000,
    }


def make_handler(repo: Path, map_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, status: HTTPStatus, data: bytes, content_type: str, filename: str | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status: HTTPStatus, value: dict) -> None:
            self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            request = urlparse(self.path)
            try:
                if request.path == "/api/snapshot":
                    self.send_json(HTTPStatus.OK, build_snapshot(repo, map_path))
                    return
                if request.path == "/api/evidence":
                    query = parse_qs(request.query)
                    path = query.get("path", [""])[0]
                    revision = query.get("revision", [""])[0]
                    self.send_json(HTTPStatus.OK, read_evidence(repo, map_path, path, revision))
                    return
                if request.path == "/api/compare":
                    query = parse_qs(request.query)
                    base = query.get("base", [""])[0]
                    target = query.get("target", [""])[0]
                    self.send_json(HTTPStatus.OK, compare_commits(repo, map_path, base, target))
                    return
                if request.path == "/api/export":
                    query = parse_qs(request.query)
                    revision = query.get("revision", [""])[0]
                    base = query.get("base", [""])[0]
                    snapshot = build_snapshot(repo, map_path, revision)
                    comparison = compare_commits(repo, map_path, base, snapshot["revision"]) if base else None
                    filename = f"projectmind-map-{snapshot['revision'][:8]}.md"
                    self.send_bytes(
                        HTTPStatus.OK,
                        export_markdown(snapshot, comparison).encode("utf-8"),
                        "text/markdown; charset=utf-8",
                        filename,
                    )
                    return
                assets = {
                    "/": ("index.html", "text/html; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                }
                if request.path in assets:
                    filename, content_type = assets[request.path]
                    self.send_bytes(HTTPStatus.OK, (WEB_PATH / filename).read_bytes(), content_type)
                    return
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            except (ValueError, KeyError) as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except (GitError, OSError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local ProjectMind map demo")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(ROOT, MAP_PATH))
    print(f"ProjectMind demo: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
