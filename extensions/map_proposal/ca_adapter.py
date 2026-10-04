"""Context Authority consumption for C — five-step protocol (C_CONTEXT_AUTHORITY_USAGE).

PIN: C pins its own expected_revision (= target_revision) before validation.
VALIDATE: failure → hard stop for the pack (RULE-1) → DEGRADED_NO_CONTEXT, no partial use.
SELECT: current_by_scope only (RULE-2); conflicts/unavailable keys never become evidence (RULE-7/8).
EVIDENCE: verified_fields checked for implementation.* claims (RULE-3); digest is not truth (RULE-6).
"""
from __future__ import annotations

import json

DEGRADED = "DEGRADED_NO_CONTEXT"
FULL = "FULL"


def _rows(pack, name):
    rows = pack.get(name)
    return rows if isinstance(rows, list) else []


def load_context(pack, target_revision):
    limits = []
    if pack is None:
        limits.append("context authority unavailable; running DEGRADED_NO_CONTEXT")
        return {"claims": [], "conflict_keys": set(), "unavailable_keys": set(),
                "conflict_rows": [], "schema_version": None, "project_revision": None,
                "registry_hash": None}, DEGRADED, limits
    try:
        from extensions.context_authority.context_pack import validate_context_pack  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — CA not installed
        limits.append("context authority extension unavailable; running DEGRADED_NO_CONTEXT")
        return {"claims": [], "conflict_keys": set(), "unavailable_keys": set(),
                "conflict_rows": [], "schema_version": None, "project_revision": None,
                "registry_hash": None}, DEGRADED, limits
    try:
        validate_context_pack(pack, expected_revision=target_revision)
    except Exception as exc:  # noqa: BLE001 — any validation failure rejects the whole pack
        limits.append(f"context pack rejected (validation failed: {type(exc).__name__}); "
                      "pack discarded entirely, running DEGRADED_NO_CONTEXT")
        return {"claims": [], "conflict_keys": set(), "unavailable_keys": set(),
                "conflict_rows": [], "schema_version": None, "project_revision": None,
                "registry_hash": None}, DEGRADED, limits
    state = pack.get("current_state") or {}
    rows = state.get("current_by_scope")
    rows = rows if isinstance(rows, list) else []
    conflict_keys = {row.get("key") for row in _rows(pack, "known_conflicts") if isinstance(row, dict)}
    unavailable_keys = {row.get("key") for row in _rows(pack, "verification_unavailable")
                        if isinstance(row, dict)}
    claims = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        if key in conflict_keys or key in unavailable_keys:
            continue
        claim_ids = row.get("claim_ids") if isinstance(row.get("claim_ids"), list) else []
        claims.append({"key": key, "scope": row.get("scope"), "value": row.get("value"),
                       "freshness": row.get("freshness", "unverified"),
                       "claim_id": claim_ids[0] if claim_ids else None,
                       "evidence": [ref for ref in (row.get("evidence") or [])
                                    if isinstance(ref, dict)]})
    return {"claims": claims, "conflict_keys": conflict_keys, "unavailable_keys": unavailable_keys,
            "conflict_rows": [row for row in _rows(pack, "known_conflicts") if isinstance(row, dict)],
            "schema_version": pack.get("schema_version"),
            "project_revision": pack.get("project_revision"),
            "registry_hash": state.get("registry_hash")}, FULL, limits


def claim_value_text(claim):
    value = claim.get("value")
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def verified_fields(claim):
    """RULE-3: row-level verified freshness ≠ every field verified.

    Returns None when no live_verification declares a field list → caller must
    treat every value field as UNVERIFIED.
    """
    for ref in claim.get("evidence", []):
        live = ref.get("live_verification")
        if isinstance(live, dict) and isinstance(live.get("verified_fields"), list):
            return set(live["verified_fields"])
    return None
