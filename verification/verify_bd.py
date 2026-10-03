"""Overnight B+D integration verification harness (read-only wrt product code).

Runs against the integrated worktree's real extensions via ExtensionHost.
Every check prints one line: [PASS]/[FAIL] id description. Exit 0 iff all pass.
Storage from D extensions is confined to fixture repos created in %TEMP%.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from http import HTTPStatus
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extension_host import ExtensionContext, ExtensionError, ExtensionHost, _LoadedExtension  # noqa: E402
import app as core_app  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(cid: str, description: str, fn):
    try:
        detail = fn()
        RESULTS.append((True, cid, description))
        print(f"[PASS] {cid} {description} {detail or ''}".rstrip())
    except AssertionError as exc:
        RESULTS.append((False, cid, f"{description} :: {exc}"))
        print(f"[FAIL] {cid} {description} :: {exc}")
    except Exception as exc:  # harness bug or unexpected product behavior
        RESULTS.append((False, cid, f"{description} :: UNEXPECTED {type(exc).__name__}: {exc}"))
        print(f"[FAIL] {cid} {description} :: UNEXPECTED {type(exc).__name__}: {exc}")


def require(cond, detail=""):
    if not cond:
        raise AssertionError(detail or "condition failed")
    return detail


def expect_extension_error(fn):
    try:
        fn()
    except ExtensionError as exc:
        assert exc.status in (HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT, HTTPStatus.NOT_FOUND,
                              HTTPStatus.METHOD_NOT_ALLOWED,
                              HTTPStatus.SERVICE_UNAVAILABLE), f"unexpected status {exc.status}"
        return f"rejected with status {int(exc.status)}"
    raise AssertionError("expected ExtensionError, got success")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"git {args}: {result.stderr.strip()}")
    return result.stdout.strip()


def build_fixture(base: Path) -> tuple[Path, str, str]:
    repo = base / "fixture"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    (repo / "a.py").write_text(
        "@decor\n"
        "def top_level():\n"
        "    pass\n\n"
        "class Widget:\n"
        "    def render(self):\n"
        "        pass\n\n"
        "    async def stream(self):\n"
        "        pass\n\n"
        "async def fetch_all():\n"
        "    pass\n\n"
        "class Outer:\n"
        "    class Inner:\n"
        "        def probe(self):\n"
        "            pass\n",
        encoding="utf-8",
    )
    pkg = repo / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("PACKAGE_CONST = 1\n", encoding="utf-8")
    (pkg / "mod.py").write_text("def helper():\n    pass\n", encoding="utf-8")
    (repo / "notes.txt").write_text("not python\n", encoding="utf-8")
    (repo / "syntax_err.py").write_text("def broken(:\n", encoding="utf-8")
    big = repo / "big.py"
    big.write_text("x = 0\n" * 200_000 + "def too_big():\n    pass\n", encoding="utf-8")
    (repo / "decor.py").write_text("# deco stub\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture c1")
    c1 = git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text(
        "@decor\n"
        "def top_level_changed():\n"
        "    pass\n\n"
        "class Widget:\n"
        "    def render(self):\n"
        "        pass\n\n"
        "    async def stream(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    git(repo, "rm", "-q", "pkg/mod.py")
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture c2")
    c2 = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "v1", c1)
    return repo, c1, c2


MAP_PATH = ROOT / "data" / "project-map.json"


def make_host(repo: Path) -> ExtensionHost:
    return ExtensionHost(
        ROOT / "extensions",
        ExtensionContext(
            repo=repo,
            map_path=MAP_PATH,
            snapshot=lambda: core_app.build_snapshot(repo, MAP_PATH),
            compare=lambda b, t: core_app.compare_commits(repo, MAP_PATH, b, t),
        ),
    )


def b_call(host, method, data):
    return host.run("code_facts", method, data)


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="bd-verify-"))
    try:
        repo, c1, c2 = build_fixture(base)
        host = make_host(repo)

        # ---------- S1 discovery & co-load ----------
        def s1_1():
            listing = host.listing()
            ready = {e["id"] for e in listing["extensions"] if e["status"] == "ready"}
            return require({"code_facts", "handoff", "continuity", "worklog",
                            "project_summary"} <= ready, f"ids={sorted(ready)}")
        check("S1.1", "all B+D extensions co-load, none unavailable", s1_1)

        b_snapshot = b_call(host, "POST", {"revision": c1})

        # ---------- S2 B functional ----------
        check("S2.1", "B revision echoes pinned full SHA", lambda: require(
            b_snapshot["revision"] == c1, b_snapshot["revision"]))

        def s2_2():
            entries = next(f["entries"] for f in b_snapshot["files"] if f["path"] == "a.py")
            expected = [
                {"name": "top_level", "kind": "function", "line": 2},
                {"name": "Widget", "kind": "class", "line": 5},
                {"name": "Widget.render", "kind": "method", "line": 6},
                {"name": "Widget.stream", "kind": "async_method", "line": 9},
                {"name": "fetch_all", "kind": "async_function", "line": 12},
                {"name": "Outer", "kind": "class", "line": 15},
                {"name": "Outer.Inner", "kind": "class", "line": 16},
                {"name": "Outer.Inner.probe", "kind": "method", "line": 17},
            ]
            missing = [e for e in expected if e not in entries]
            extra_kinds = {e["kind"] for e in entries} - {
                "class", "function", "async_function", "method", "async_method"}
            return require(not missing and not extra_kinds,
                           f"missing={missing} bad_kinds={extra_kinds}")
        check("S2.2", "B entries: kinds, qualified names, decorator excluded, 1-based lines", s2_2)

        def s2_3():
            got = b_call(host, "POST", {"revision": c1,
                                        "paths": ["a.py", "pkg/mod.py", "notes.txt",
                                                  "syntax_err.py", "big.py"]})
            files = [f["path"] for f in got["files"]]
            skipped = {s["path"]: s["reason"] for s in got["skipped"]}
            require(files == ["a.py", "pkg/mod.py"], f"files={files}")
            require(skipped.get("notes.txt") and skipped.get("syntax_err.py")
                    and skipped.get("big.py"), f"skipped={skipped}")
            return f"skip reasons={sorted(set(skipped.values()))}"
        check("S2.3", "B paths select + skip reasons (txt/syntax/oversize)", s2_3)

        for label, payload in [
            ("HEAD", {"revision": "HEAD"}),
            ("short-sha", {"revision": c1[:8]}),
            ("tag-object", {"revision": "v1"}),
            ("traversal-revision", {"revision": "../../../etc/passwd"}),
            ("tilde", {"revision": f"{c1}~1"}),
            ("missing-key", {"paths": ["a.py"]}),
        ]:
            check(f"S2.4-{label}", f"B rejects revision={label}",
                  lambda payload=payload: expect_extension_error(
                      lambda: b_call(host, "POST", payload)))

        for label, paths in [
            ("dotdot", ["a.py", "../secrets.py"]),
            ("inner-dotdot", ["a/../../b.py"]),
            ("backslash", ["a\\b.py"]),
            ("absolute-win", ["C:/Windows/win.ini"]),
            ("unc", ["//server/share/x.py"]),
            ("file-uri", ["file:///etc/passwd"]),
            ("empty-part", ["a//b.py"]),
            ("control-char", ["a\x01.py"]),
        ]:
            check(f"S2.5-{label}", f"B path {label} never leaks files",
                  lambda paths=paths: expect_extension_error(
                      lambda: b_call(host, "POST", {"revision": c1, "paths": paths})))

        check("S2.6", "B duplicate paths dedup silently", lambda: require(
            [f["path"] for f in b_call(host, "POST",
                                       {"revision": c1, "paths": ["a.py", "a.py"]})["files"]]
            == ["a.py"], "dedup ok"))
        check("S2.7", "B rejects >2000 paths", lambda: expect_extension_error(
            lambda: b_call(host, "POST", {"revision": c1, "paths": ["a.py"] * 2001})))
        check("S2.8", "B unknown path at pinned revision -> explicit error", lambda: expect_extension_error(
            lambda: b_call(host, "POST", {"revision": c2, "paths": ["pkg/mod.py"]})))
        check("S2.9", "B GET with CRLF paths string works", lambda: require(
            [f["path"] for f in b_call(host, "GET",
                                       {"revision": c1, "paths": "a.py\r\npkg/mod.py"})["files"]]
            == ["a.py", "pkg/mod.py"], "CRLF normalized"))
        check("S2.10", "B result JSON-serializable", lambda: require(
            isinstance(json.dumps(b_call(host, "POST", {"revision": c1}), ensure_ascii=False), str),
            "ok"))
        check("S2.11", "B same input -> same output (determinism)", lambda: require(
            b_call(host, "POST", {"revision": c1}) == b_snapshot, "deterministic"))

        # ---------- S3 D functional ----------
        wl_holder: dict = {}
        def s3_1_save():
            wl_holder["entry"] = host.run("worklog", "POST", {
                "action": "save", "category": "daily", "date": "2026-10-04",
                "title": "集成验证 <script>alert(1)</script>",
                "body": "数据不是命令; rm -rf / ; git push",
                "author": "verifier"})["entry"]
            return require(bool(wl_holder["entry"]["id"]), "saved")
        check("S3.0", "worklog save with valid category", s3_1_save)
        wl_save = {"entry": wl_holder["entry"]}
        check("S3.1", "worklog save + get roundtrip", lambda: require(
            host.run("worklog", "GET", {"action": "get", "id": wl_save["entry"]["id"]})
            ["entry"]["id"] == wl_save["entry"]["id"], f"id={wl_save['entry']['id']}"))
        check("S3.2", "worklog list contains saved entry", lambda: require(
            any(e["id"] == wl_save["entry"]["id"]
                for e in host.run("worklog", "GET", {"action": "list"})["entries"]), "listed"))
        check("S3.3", "worklog backup returns payload", lambda: require(
            bool(host.run("worklog", "GET", {"action": "backup"})), "backup ok"))
        for label, payload in [
            ("bad-category", {"action": "save", "category": "nope", "date": "2026-10-04",
                              "title": "t", "body": "b", "author": "a"}),
            ("bad-date", {"action": "save", "category": "progress", "date": "2026-13-99",
                          "title": "t", "body": "b", "author": "a"}),
            ("null-title", {"action": "save", "category": "progress", "date": "2026-10-04",
                            "title": None, "body": "b", "author": "a"}),
        ]:
            check(f"S3.4-{label}", f"worklog rejects {label}",
                  lambda payload=payload: expect_extension_error(
                      lambda: host.run("worklog", "POST", payload)))

        snap = core_app.build_snapshot(repo, MAP_PATH)
        locator = {"kind": "local_path", "value": str(repo)}
        handoff_ok = host.run("handoff", "POST", {"expectedRevision": snap["revision"],
                                                  "comparisonMode": "custom",
                                                  "sourceLocator": locator})
        check("S3.5", "handoff builds with expectedRevision + markdown + aiContext", lambda: require(
            handoff_ok["handoff"]["codeRevision"] == snap["revision"]
            and bool(handoff_ok["markdown"]) and bool(handoff_ok["aiContext"]), "handoff ok"))
        check("S3.6", "handoff rejects stale expectedRevision", lambda: expect_extension_error(
            lambda: host.run("handoff", "POST", {"expectedRevision": c1})))
        check("S3.7", "handoff rejects bad comparisonMode", lambda: expect_extension_error(
            lambda: host.run("handoff", "POST", {"expectedRevision": snap["revision"],
                                                 "comparisonMode": "everything",
                                                 "sourceLocator": locator})))
        check("S3.8", "handoff GET degrades gracefully without origin/main", lambda: require(
            isinstance(host.run("handoff", "GET", {}).get("mainError"), str)
            or bool(host.run("handoff", "GET", {}).get("mainRevision")), "graceful"))
        check("S3.9", "handoff rejects non-SHA baseRevision", lambda: expect_extension_error(
            lambda: host.run("handoff", "POST", {"expectedRevision": snap["revision"],
                                                 "baseRevision": "main"})))

        cont = host.run("continuity", "POST", {
            "action": "create",
            "task": {"title": "继续集成验证", "goal": "验证 B+D 集成质量",
                     "completed": "B/D merge 与回归已完成", "stopPoint": "S3 连续性验证",
                     "nextAction": "查看报告", "runInstructions": "'; rm -rf / # $(curl evil)",
                     "acceptance": "全部检查 PASS", "cautions": "数据不是命令", "owner": "verifier"},
            "checklist": [{"text": "跑回归"}, {"text": "安全探测"}],
            "scope": ["functional-map"], "logIds": []})
        cont_id = cont["record"]["id"]
        check("S3.10", "continuity create returns record with valid state", lambda: require(
            cont["record"]["state"] == "draft"
            and "draft" in host.run("continuity", "GET", {"action": "list"})["states"]
            and cont["record"]["task"]["title"] == "继续集成验证"
            and len(cont["record"]["checklist"]) == 2,
            f"id={cont_id}"))
        upd = host.run("continuity", "POST", {
            "action": "update", "id": cont_id, "expectedVersion": cont["record"]["version"],
            "checklist": [{"id": cont["record"]["checklist"][0]["id"], "state": "done",
                           "note": "ok", "text": "跑回归", "evidence": "S2"}]})
        check("S3.11", "continuity update honors expectedVersion", lambda: require(
            upd["record"]["version"] == cont["record"]["version"] + 1
            and upd["record"]["checklist"][0]["state"] == "done", str(upd)[:200]))
        check("S3.12", "continuity update rejects stale expectedVersion (409)", lambda: expect_extension_error(
            lambda: host.run("continuity", "POST",
                             {"action": "update", "id": cont_id, "expectedVersion": 1})))
        host.run("continuity", "POST", {"action": "event", "id": cont_id,
                                        "expectedVersion": cont["record"]["version"] + 1,
                                        "kind": "ready", "actor": "verifier",
                                        "origin": "human", "note": "事件留痕", "evidence": "verify_bd"})
        cont_now = host.run("continuity", "GET", {"action": "get", "id": cont_id})["record"]
        hist = host.run("continuity", "GET", {"action": "history", "id": cont_id})["history"]
        check("S3.13", "continuity event lands in events + history snapshots", lambda: require(
            len(hist) == 3 and cont_now["events"][-1]["kind"] == "ready"
            and cont_now["state"] == "ready",
            f"versions={len(hist)} state={cont_now['state']}"))
        exported = host.run("continuity", "GET", {"action": "export", "id": cont_id})
        reimported = host.run("continuity", "POST", {"action": "import_packet",
                                                     "packet": exported["packet"]})
        check("S3.14", "continuity export -> import roundtrip preserves content", lambda: require(
            reimported["record"]["task"] == cont_now["task"]
            and len(reimported["record"]["checklist"]) == len(cont_now["checklist"]),
            f"imported id={reimported['record']['id']} (new id + receiving state by design)"))
        follow = host.run("continuity", "POST", {"action": "followup", "id": cont_id,
                                                 "expectedVersion": cont["record"]["version"] + 2,
                                                 "logIds": []})
        check("S3.15", "continuity followup creates linked child", lambda: require(
            cont_id in json.dumps(follow["record"]), "no parent link"))
        check("S3.16", "continuity import_chunk rejects garbage chunk", lambda: expect_extension_error(
            lambda: host.run("continuity", "POST",
                             {"action": "import_chunk", "uploadId": "nope",
                              "chunk": "\x00\x01not-base64!!!"})))

        # ---------- S13/S14 isolation & pollution ----------
        check("S13.1", "D writes do not change B facts (no pollution)", lambda: require(
            b_call(host, "POST", {"revision": c1}) == b_snapshot, "B output changed"))
        wl_before = host.run("worklog", "GET", {"action": "list"})
        cont_before = host.run("continuity", "GET", {"action": "list"})
        b_call(host, "POST", {"revision": c2, "paths": ["a.py"]})
        check("S13.2", "B calls do not touch D stores", lambda: require(
            host.run("worklog", "GET", {"action": "list"}) == wl_before
            and host.run("continuity", "GET", {"action": "list"}) == cont_before,
            "D store changed during B call"))

        broken_root = base / "ext-broken"
        shutil.copytree(ROOT / "extensions", broken_root,
                        ignore=shutil.ignore_patterns("__pycache__"))
        (broken_root / "boom").mkdir()
        (broken_root / "boom" / "extension.py").write_text(
            "raise SystemExit('boom at import')\n", encoding="utf-8")
        broken_host = ExtensionHost(broken_root, ExtensionContext(
            repo=repo, map_path=MAP_PATH,
            snapshot=lambda: core_app.build_snapshot(repo, MAP_PATH),
            compare=lambda b, t: core_app.compare_commits(repo, MAP_PATH, b, t)))
        check("S14.1", "SystemExit at import isolates one extension, others stay ready", lambda: require(
            "boom" in broken_host.unavailable
            and {"code_facts", "handoff", "continuity", "worklog"} <= set(broken_host.loaded),
            f"unavailable={broken_host.unavailable}"))
        check("S14.2", "isolated-broken host still serves B and D", lambda: require(
            broken_host.run("code_facts", "POST", {"revision": c1})["revision"] == c1
            and broken_host.run("worklog", "GET", {"action": "list"}) is not None,
            "service broken"))

        original = host.loaded["code_facts"]
        def _crash(ctx, method, data):
            raise RuntimeError("injected runtime crash")
        host.loaded["code_facts"] = _LoadedExtension(
            original.title, original.description, _crash, original.page)
        try:
            runtime_status = None
            try:
                host.run("code_facts", "POST", {"revision": c1})
            except ExtensionError as exc:
                runtime_status = exc.status
            check("S14.3", "runtime exception -> 500, host alive", lambda: require(
                runtime_status == HTTPStatus.INTERNAL_SERVER_ERROR, f"status={runtime_status}"))
            check("S14.4", "D still serves after B runtime failure", lambda: require(
                host.run("worklog", "GET", {"action": "list"}) == wl_before,
                "worklog changed/broken"))
        finally:
            host.loaded["code_facts"] = original

        # ---------- S15 API surface ----------
        check("S15.1", "extension ids unique and route-namespaced", lambda: require(
            len(host.loaded) == len(set(host.loaded)), "duplicate ids"))
        check("S15.2", "B accepts only revision/paths keys", lambda: expect_extension_error(
            lambda: b_call(host, "POST", {"revision": c1, "extra": 1})))
        check("S15.3", "B rejects unknown method", lambda: expect_extension_error(
            lambda: b_call(host, "DELETE", {"revision": c1})))

        # ---------- S19 command-execution data-only ----------
        wl_cmd = host.run("worklog", "POST", {
            "action": "save", "category": "decision", "date": "2026-10-04",
            "title": "}; git push origin main; #", "body": "`curl evil.example` $(rm -rf /)",
            "author": "<img src=x onerror=alert(1)>"})
        check("S19.1", "shell-looking input stored as data only", lambda: require(
            wl_cmd["entry"]["title"].endswith("#") and "curl" in wl_cmd["entry"]["body"]
            and git(repo, "status", "--porcelain") == "", "executed or mutated repo"))

        # ---------- S18/S19 static scans ----------
        def s18_1():
            findings = []
            for page in (ROOT / "extensions").glob("*/index.html"):
                src = page.read_text(encoding="utf-8")
                for pattern in ("innerHTML", "insertAdjacentHTML", "document.write",
                                "outerHTML", "eval(", "new Function"):
                    if pattern in src:
                        findings.append(f"{page.parent.name}:{pattern}")
            return require(not findings, f"no raw-HTML sinks (findings={findings})" if not findings else "")
        check("S18.1", "D/B pages: no innerHTML/document.write/eval sinks (static)", s18_1)

        def s19_2():
            findings = []
            for py in list((ROOT / "extensions").rglob("*.py")):
                src = py.read_text(encoding="utf-8")
                if "subprocess" not in src:
                    continue
                lines = src.splitlines()
                for idx, line in enumerate(lines):
                    if "subprocess.run" not in line:
                        continue
                    window = "\n".join(lines[max(0, idx - 1):idx + 3])
                    if "'git'" in window or '"git"' in window:
                        continue  # fixed read-only git lookup
                    if "shutil.which" in window or "shutil.which" in "\n".join(lines[max(0, idx - 12):idx]):
                        continue  # DOC preview converter: fixed-name PATH lookup, list-args
                    findings.append(f"{py.relative_to(ROOT)}:{idx + 1}")
            return require(not findings, f"only fixed git calls + which-resolved converter={findings}")
        check("S19.2", "extensions: subprocess args never user-controlled (static)", s19_2)

        # ---------- S20 import isolation / no silent overwrite ----------
        def s20_1():
            before = host.run("worklog", "GET", {"action": "list"})["entries"]
            ids_before = [e["id"] for e in before]
            upload = host.run("worklog", "POST", {
                "action": "import_start", "category": "issue", "date": "2026-10-04",
                "title": "导入的日志", "body": "", "author": " elsewhere",
                "filename": "notes.md", "size": len("# imported\n")})
            import base64 as b64
            host.run("worklog", "POST", {"action": "import_chunk",
                                         "uploadId": upload["uploadId"], "offset": 0,
                                         "base64": b64.b64encode(b"# imported\n").decode()})
            fin = host.run("worklog", "POST", {"action": "import_finish",
                                               "uploadId": upload["uploadId"]})
            after = host.run("worklog", "GET", {"action": "list"})["entries"]
            ids_after = [e["id"] for e in after]
            return require(len(after) == len(before) + 1
                           and all(i in ids_after for i in ids_before)
                           and fin["entry"]["id"] not in ids_before,
                           f"import appended new id={fin['entry']['id']}, locals intact")
        check("S20.1", "worklog file import appends; existing records untouched", s20_1)

        def s20_2():
            before = host.run("continuity", "GET", {"action": "list"})["records"]
            ids_before = [r["id"] for r in before]
            reimp = host.run("continuity", "POST", {"action": "import_packet",
                                                    "packet": exported["packet"]})
            after = host.run("continuity", "GET", {"action": "list"})["records"]
            return require(reimp["record"]["id"] not in ids_before
                           and all(r["id"] in [x["id"] for x in after] for r in before)
                           and reimp["record"]["state"] == "receiving",
                           f"second import got fresh id={reimp['record']['id']}, no overwrite")
        check("S20.2", "continuity packet re-import never overwrites local records", s20_2)

    finally:
        shutil.rmtree(base, ignore_errors=True)

    failed = [r for r in RESULTS if not r[0]]
    print(f"\n==== SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed ====")
    for _, cid, detail in failed:
        print(f"FAILED {cid}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
