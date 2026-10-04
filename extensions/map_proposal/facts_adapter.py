"""B / Code Facts consumption for C (RULE-5, C_B_CODEFACTS_USAGE).

Only runtime assertion kept: CodeFacts.revision == target_revision.
skipped is never treated as facts; C never assumes dependencies/call-graph/
signatures/responsibility from B.
"""
from __future__ import annotations

FACTS_LIMITS = "code facts unavailable"


class FactsMismatch(ValueError):
    """code_facts.revision != target_revision — the whole request is rejected."""


def _normalize(facts):
    files = {}
    for entry in facts.get("files") or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            files[entry["path"]] = [d for d in (entry.get("entries") or [])
                                    if isinstance(d, dict) and isinstance(d.get("name"), str)]
    skipped = {s.get("path") for s in (facts.get("skipped") or []) if isinstance(s, dict)}
    return files, skipped


def load_code_facts(request_facts, repo, target_revision, wanted_paths):
    """Return {'files': {path: entries}, 'skipped': set, 'available': bool}, plus limits list.

    request_facts present + revision mismatch → FactsMismatch (hard reject, C-A26).
    request_facts present but malformed → tolerated as unavailable (RULE-5 contract drift, C-A28).
    request_facts absent → try in-process B; B missing/failing → unavailable (F1' degraded path).
    """
    limits = []
    if request_facts is not None:
        if not isinstance(request_facts, dict):
            limits.append("code facts in request malformed; treated as unavailable")
            return {"files": {}, "skipped": set(), "available": False}, limits
        revision = request_facts.get("revision")
        if not isinstance(revision, str) or revision != target_revision:
            raise FactsMismatch("code_facts.revision 必须等于 target_revision")
        try:
            files, skipped = _normalize(request_facts)
        except Exception:  # noqa: BLE001 — shape drift must not crash C
            limits.append("code facts shape drifted; treated as unavailable")
            return {"files": {}, "skipped": set(), "available": False}, limits
        return {"files": files, "skipped": skipped, "available": True}, limits
    try:
        from extensions.code_facts.facts import collect_code_facts  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — B not installed
        limits.append(FACTS_LIMITS)
        return {"files": {}, "skipped": set(), "available": False}, limits
    try:
        # Full-tree collection: a removed path inside changed_paths must not
        # poison the whole call (B rejects requests naming absent paths).
        raw = collect_code_facts(repo, target_revision, None)
    except Exception:  # noqa: BLE001 — B rejects (invalid inputs, missing objects) → degraded
        limits.append(FACTS_LIMITS)
        return {"files": {}, "skipped": set(), "available": False}, limits
    files, skipped = _normalize(raw)
    return {"files": files, "skipped": skipped, "available": True}, limits
