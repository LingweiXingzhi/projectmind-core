# -*- coding: utf-8 -*-
"""B / Code Facts adaptation and the unified fact-availability gate (R02).

Every execution path verifies code_facts.revision == target_revision before any
early exit — supplied facts, installed B on normal requests, same-revision
requests and empty change sets all pass through this gate (F07, DROP L06).
skipped is never treated as facts; C never assumes dependencies / call-graph /
signatures / responsibility from B.
"""
from __future__ import annotations

from extensions.map_proposal.model import validate_path

FACTS_LIMITS = "code facts unavailable"


class FactsMismatch(ValueError):
    """code_facts.revision != target_revision — the whole request is rejected."""


def _normalize(facts):
    """Tolerate partial per-entry drift: C only reads name/kind/line and never
    crashes on B evolution, but the outer containers must be sound."""
    files_raw = facts.get("files") or []
    skipped_raw = facts.get("skipped") or []
    if not isinstance(files_raw, list) or not isinstance(skipped_raw, list):
        raise ValueError("code_facts files/skipped 须为列表")
    files = {}
    for entry in files_raw:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            # C-08: facts paths are a path source like every other (S28);
            # traversal-shaped declarations are a controlled input rejection.
            validate_path(entry["path"], "code fact path")
            if not isinstance(entry.get("entries") or [], list):
                raise ValueError("code_fact entries 须为列表")
            sanitized = []
            for item in (entry.get("entries") or []):
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    sanitized.append(
                        {
                            "name": item["name"],
                            "kind": item.get("kind") if isinstance(item.get("kind"), str) else "unknown",
                            "line": item.get("line") if isinstance(item.get("line"), int) else None,
                        }
                    )
            files[entry["path"]] = sanitized
    skipped = set()
    skipped_reasons = {}
    for row in skipped_raw:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            skipped.add(row["path"])
            if isinstance(row.get("reason"), str):
                skipped_reasons[row["path"]] = row["reason"]
    return files, skipped, skipped_reasons


def _check_revision(raw_revision, target_revision):
    if not isinstance(raw_revision, str) or raw_revision != target_revision:
        raise FactsMismatch("code_facts.revision 必须等于 target_revision")


def load_code_facts(request_facts, repo, target_revision, wanted_paths):
    """Return ({'files': {path: entries}, 'skipped': set, 'available': bool,
    'source': str}, limits).

    - request_facts present: revision equality enforced; malformed container is
      a controlled input rejection (S27); per-entry drift tolerated.
    - request_facts absent: try in-process B (if installed). The installed B
      return value is re-pinned against target_revision (F07/X06); B failure →
      unavailable + limits, never fabricated facts (S15).
    """
    limits = []
    if request_facts is not None:
        if not isinstance(request_facts, dict):
            raise FactsMismatch("code_facts 须为对象")
        _check_revision(request_facts.get("revision"), target_revision)
        try:
            files, skipped, skipped_reasons = _normalize(request_facts)
        except Exception:  # noqa: BLE001 — supplied shape drift is a controlled reject
            raise FactsMismatch("code_facts 形状异常")
        return (
            {"files": files, "skipped": skipped, "skipped_reasons": skipped_reasons,
             "available": True, "source": "supplied"},
            limits,
        )

    try:
        from extensions.code_facts.facts import collect_code_facts  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — B not installed on this base
        limits.append(FACTS_LIMITS)
        return (
            {"files": {}, "skipped": set(), "skipped_reasons": {},
                    "available": False, "source": "none"},
            limits,
        )

    try:
        # Preferred: only the paths needed at target; a removed path must not
        # poison the whole call, so B rejection on wanted paths falls back to a
        # full-tree collection once.
        raw = collect_code_facts(repo, target_revision, wanted_paths or None)
    except Exception:  # noqa: BLE001
        if wanted_paths:
            try:
                raw = collect_code_facts(repo, target_revision, None)
            except Exception:  # noqa: BLE001 — B rejects invalid inputs → degraded
                limits.append(FACTS_LIMITS)
                return (
                    {"files": {}, "skipped": set(), "skipped_reasons": {},
                    "available": False, "source": "none"},
                    limits,
                )
        else:
            limits.append(FACTS_LIMITS)
            return (
                {"files": {}, "skipped": set(), "skipped_reasons": {},
                    "available": False, "source": "none"},
                limits,
            )

    if not isinstance(raw, dict):
        limits.append("installed code facts shape drifted; treated as unavailable")
        return (
            {"files": {}, "skipped": set(), "skipped_reasons": {},
                    "available": False, "source": "none"},
            limits,
        )

    # The installed B return value is pinned again: same-revision requests and
    # empty diffs cannot bypass the gate (S14).
    try:
        _check_revision(raw.get("revision"), target_revision)
        files, skipped, skipped_reasons = _normalize(raw)
    except FactsMismatch:
        raise
    except Exception:  # noqa: BLE001 — installed dependency drift → degraded, not crash
        limits.append("installed code facts shape drifted; treated as unavailable")
        return (
            {"files": {}, "skipped": set(), "skipped_reasons": {},
                    "available": False, "source": "none"},
            limits,
        )
    return (
        {"files": files, "skipped": skipped, "skipped_reasons": skipped_reasons,
         "available": True, "source": "installed"},
        limits,
    )


def skipped_unresolved(skipped, target_revision):
    """HUMAN_REQUIRED unresolved entries for changed sources B skipped (K04).

    Only actually relevant (changed) skipped paths are reported; this is not a
    whole-tree diagnostic generator (DROP T06).
    """
    entries = []
    for path in sorted(skipped):
        entries.append(
            {
                "subject": path,
                "reason": "HUMAN_REQUIRED",
                "detail": "changed source was skipped by code facts; no candidate may rely on it",
                "evidence": [{"kind": "code_fact_skipped", "revision": target_revision, "path": path}],
            }
        )
    return entries


def path_eligibility(path, facts):
    """Unified eligibility for any candidate evidence domain (F04, DROP L04).

    Returns one of 'eligible', 'skipped', 'missing'. Every channel must ask
    this before turning a path into strong-candidate evidence; relation
    endpoints included.
    """
    if path in facts["skipped"]:
        return "skipped"
    if path in facts["files"]:
        return "eligible"
    return "missing"


def domain_gate(paths, facts):
    """C-02 centralized evidence-domain eligibility gate (A4/E-3): a strong
    proposal may only publish when EVERY member path it relies on is
    positively eligible in B facts — present AND not skipped. 'missing'
    (not collected: partial wanted_paths, stale map member) blocks exactly
    like 'skipped': a partial collection must never support a stronger
    conclusion than a full one. Every channel that turns file evidence into
    a strong candidate must pass its full relied-upon domain through this
    gate; violations surface as visible HUMAN_REQUIRED, never as a silent
    cancel.

    Returns (ok, violations); violations list (path, state, reason) with the
    B skip reason when available."""
    violations = []
    for path in sorted(set(paths)):
        state = path_eligibility(path, facts)
        if state == "eligible":
            continue
        violations.append(
            (path, state, facts.get("skipped_reasons", {}).get(path)))
    return (not violations, violations)


def domain_eligibility(paths, facts):
    """A whole evidence domain (e.g. all evidence paths of one map node) is
    eligible only when every path is eligible and at least one is present."""
    checked = [path_eligibility(p, facts) for p in paths]
    if not checked:
        return "missing"
    if any(state == "skipped" for state in checked):
        return "skipped"
    if all(state == "missing" for state in checked):
        return "missing"
    return "eligible"
