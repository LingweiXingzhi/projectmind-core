"""Live verifiers for volatile VERIFIED_FACT keys.

A verifier answers for ONE claim key. It returns
  {"status": "ok", "value": <live value>, ...}
or {"status": "unavailable", "reason": "..."}.
Unavailable is REPORTED in the resolved state; it never fakes a value.
All verification is read-only (local git / gh api).
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone

GIT_TIMEOUT = 15


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=GIT_TIMEOUT, cwd=cwd)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _gh_json(endpoint: str):
    try:
        code, out, err = _run(["gh", "api", endpoint, "--jq", "."])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"gh api unavailable: {type(exc).__name__}"
    if code != 0:
        return None, f"gh api failed: {err[:120]}"
    try:
        return json.loads(out), ""
    except json.JSONDecodeError:
        return None, "gh api returned non-JSON"


def make_pr_head_verifier(pr_number: int):
    """Read GitHub head/status; merged and merely closed are distinct."""

    def verify(claim: dict) -> dict:
        stored = claim.get("value")
        if isinstance(stored, dict) and "pr" in stored and stored["pr"] != pr_number:
            return {"status": "unavailable", "reason": "claim PR does not match verifier"}
        endpoint = f"repos/LingweiXingzhi/projectmind-core/pulls/{pr_number}"
        data, err = _gh_json(
            endpoint)
        if data is None:
            return {"status": "unavailable", "reason": err}
        if not isinstance(data, dict) or not isinstance(data.get("head"), dict):
            return {"status": "unavailable", "reason": "PR payload missing head.sha"}
        sha = data["head"].get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            return {"status": "unavailable", "reason": "PR payload invalid head.sha"}
        if data.get("state") not in ("open", "closed") or not isinstance(data.get("merged"), bool):
            return {"status": "unavailable", "reason": "PR payload missing/invalid state or merged"}
        if data["state"] == "open" and data["merged"]:
            return {"status": "unavailable", "reason": "PR payload contradictory open/merged"}
        value = {"status": "MERGED" if data["merged"] else "CLOSED",
                 "pr": pr_number,
                 "head": sha}
        if data["state"] == "open":
            value["status"] = "PR_OPEN"
        return {"status": "ok", "value": value,
                "verified_at": _now(), "source_kind": "gh_api", "source_ref": endpoint,
                "verified_fields": ["status", "pr", "head"]}

    return verify


def make_main_head_verifier(repo: str):
    """main head from the LOCAL clone (origin/main remote-tracking ref)."""

    def verify(claim: dict) -> dict:
        try:
            code, out, err = _run(["git", "rev-parse", "refs/remotes/origin/main"], cwd=repo)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"status": "unavailable", "reason": f"local git unavailable: {type(exc).__name__}"}
        if code != 0:
            return {"status": "unavailable", "reason": f"local git failed: {err[:100]}"}
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", out):
            return {"status": "unavailable", "reason": "local git returned invalid commit SHA"}
        return {"status": "ok", "value": {"sha": out},
                "verified_at": _now(), "source_kind": "repo",
                "source_ref": f"{repo}::refs/remotes/origin/main", "freshness": "local_reference"}

    return verify


def build_default_verifiers(repo: str) -> dict:
    def verify_code_facts(claim):
        value = claim.get("value")
        number = value.get("pr") if isinstance(value, dict) else None
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            return {"status": "unavailable", "reason": "code_facts claim lacks a valid PR number"}
        result = make_pr_head_verifier(number)(claim)
        # Evaluation belongs to the recorded head, not every future PR revision.
        if result["status"] == "ok" and value.get("head") == result["value"]["head"]:
            result["value"].update({k: v for k, v in value.items() if k not in ("status", "pr", "head")})
        return result

    return {
        "implementation.main_head": make_main_head_verifier(repo),
        "implementation.pr_21_head": make_pr_head_verifier(21),
        "implementation.pr_22_head": make_pr_head_verifier(22),
        "implementation.code_facts": verify_code_facts,
    }
