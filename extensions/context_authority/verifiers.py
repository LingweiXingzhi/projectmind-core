"""Live verifiers for volatile VERIFIED_FACT keys.

A verifier answers for ONE claim key. It returns
  {"status": "ok", "value": <live value>, ...}
or {"status": "unavailable", "reason": "..."}.
Unavailable is REPORTED in the resolved state; it never fakes a value.
All verification is read-only (local git / gh api).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

GIT_TIMEOUT = 15


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=GIT_TIMEOUT,
                          cwd=cwd)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _gh_json(endpoint: str):
    code, out, err = _run(["gh", "api", endpoint, "--jq", "."])
    if code != 0:
        return None, f"gh api failed: {err[:120]}"
    try:
        return json.loads(out), ""
    except json.JSONDecodeError:
        return None, "gh api returned non-JSON"


def make_pr_head_verifier(pr_number: int):
    """Live PR head via gh api. Unavailable (e.g. offline) is reported, and
    the stored claim then simply stays unverified — no silent acceptance."""

    def verify(claim: dict) -> dict:
        data, err = _gh_json(
            f"repos/LingweiXingzhi/projectmind-core/pulls/{pr_number}")
        if data is None:
            return {"status": "unavailable", "reason": err}
        if not isinstance(data.get("head"), dict) or "sha" not in data["head"]:
            return {"status": "unavailable", "reason": "PR payload missing head.sha"}
        value = {"status": data["state"].upper(),
                 "pr": pr_number,
                 "head": data["head"]["sha"]}
        if data["state"] == "open":
            value["status"] = "PR_OPEN"
        return {"status": "ok", "value": value,
                "verified_at": _now(), "source_kind": "gh_api"}

    return verify


def make_main_head_verifier(repo: str):
    """main head from the LOCAL clone (origin/main remote-tracking ref)."""

    def verify(claim: dict) -> dict:
        code, out, err = _run(["git", "rev-parse", "refs/remotes/origin/main"],
                              cwd=repo)
        if code != 0:
            code2, out2, _ = _run(["git", "rev-parse", "main"], cwd=repo)
            if code2 != 0:
                return {"status": "unavailable",
                        "reason": f"local git failed: {err[:100]}"}
            out = out2
        return {"status": "ok", "value": {"sha": out},
                "verified_at": _now(), "source_kind": "repo"}

    return verify


def build_default_verifiers(repo: str) -> dict:
    return {
        "implementation.main_head": make_main_head_verifier(repo),
        "implementation.pr_21_head": make_pr_head_verifier(21),
        "implementation.pr_22_head": make_pr_head_verifier(22),
    }
