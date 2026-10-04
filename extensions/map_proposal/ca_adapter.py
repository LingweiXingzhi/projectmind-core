# -*- coding: utf-8 -*-
"""Context Authority consumption for C (P01 port + R04 admission, W4).

Protocol:
- PIN: C validates with its own expected_revision (= target_revision).
- VALIDATE: the real CA validator runs first; any failure discards the whole
  pack (no partial use) and C degrades explicitly — independent diff/B/map
  candidates continue (S24).
- SELECT: only current_state.current_by_scope is read; stale/proposal/
  research/history partitions are never consumed (S20); conflict and
  verification-unavailable keys never become evidence (S23).
- EVIDENCE: no claim is attached to any proposal automatically (DROP L01/L02 —
  no keyword trust heuristics, no first-survivor supplement). C has no
  independent git/gh verifier in this build, so pack claims support nothing;
  they exist in the selection layer for typed consumers and conflict routing
  (S21/S22/S25).
- CONFLICTS: structural routing over key/scope and word-boundary path/node
  association (P08). A related conflict moves touching proposals to
  unresolved HUMAN_REQUIRED; unrelated candidates keep their valid proposals
  (S19/X14/X15/X18).
"""
from __future__ import annotations

import json
import re

from extensions.map_proposal.model import make_evidence

DEGRADED = "DEGRADED_NO_CONTEXT"
FULL = "FULL"

_EMPTY = {
    "claims": [],
    "conflict_keys": set(),
    "unavailable_keys": set(),
    "conflict_rows": [],
    "schema_version": None,
    "project_revision": None,
    "registry_hash": None,
}


def _empty_context():
    return {key: (set() if isinstance(value, set) else value) for key, value in _EMPTY.items()}


def _rows(pack, name):
    rows = pack.get(name)
    return rows if isinstance(rows, list) else []


def load_context(pack, target_revision):
    limits = []
    if pack is None:
        limits.append("context authority unavailable; running DEGRADED_NO_CONTEXT")
        return _empty_context(), DEGRADED, limits
    try:
        from extensions.context_authority.context_pack import validate_context_pack  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — CA not installed on this base
        limits.append("context authority extension unavailable; running DEGRADED_NO_CONTEXT")
        return _empty_context(), DEGRADED, limits
    try:
        validate_context_pack(pack, expected_revision=target_revision)
    except Exception as exc:  # noqa: BLE001 — any validation failure discards the whole pack
        limits.append(
            f"context pack rejected (validation failed: {type(exc).__name__}); "
            "pack discarded entirely, running DEGRADED_NO_CONTEXT"
        )
        return _empty_context(), DEGRADED, limits

    state = pack.get("current_state") or {}
    rows = state.get("current_by_scope")
    rows = rows if isinstance(rows, list) else []
    conflict_keys = {row.get("key") for row in _rows(pack, "known_conflicts") if isinstance(row, dict)}
    unavailable_keys = {
        row.get("key") for row in _rows(pack, "verification_unavailable") if isinstance(row, dict)
    }
    claims = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        if key in conflict_keys or key in unavailable_keys:
            continue
        claim_ids = row.get("claim_ids") if isinstance(row.get("claim_ids"), list) else []
        claims.append(
            {
                "key": key,
                "scope": row.get("scope"),
                "value": row.get("value"),
                "freshness": row.get("freshness", "unverified"),
                "claim_id": claim_ids[0] if claim_ids else None,
                "evidence": [ref for ref in (row.get("evidence") or []) if isinstance(ref, dict)],
            }
        )
    return {
        "claims": claims,
        "conflict_keys": conflict_keys,
        "unavailable_keys": unavailable_keys,
        "conflict_rows": [row for row in _rows(pack, "known_conflicts") if isinstance(row, dict)],
        "schema_version": pack.get("schema_version"),
        "project_revision": pack.get("project_revision"),
        "registry_hash": state.get("registry_hash"),
    }, FULL, limits


def claim_value_text(claim):
    value = claim.get("value")
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def verified_fields(claim):
    """Row-level verified freshness ≠ every field verified: returns the
    declared field set, or None when no live_verification declares one (then
    every value field must be treated as UNVERIFIED, S22)."""
    for ref in claim.get("evidence", []):
        live = ref.get("live_verification")
        if isinstance(live, dict) and isinstance(live.get("verified_fields"), list):
            return set(live["verified_fields"])
    return None


def field_verification(claim):
    """Per-field support map for dict values (S22 diagnostics; never a licence
    to attach the claim itself)."""
    if not isinstance(claim.get("value"), dict):
        return None
    fields = verified_fields(claim)
    return {
        key: ("verified" if fields is not None and key in fields else "UNVERIFIED")
        for key in sorted(claim["value"])
    }


def mentions(text, token):
    """Word-boundary occurrence check (P08); avoids node-a/node-api substring
    false positives."""
    if not token or not text:
        return False
    return re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", text) is not None


def apply_context_admission(proposals, ca, ca_mode, changed_paths, node_ids,
                            limits, unresolved):
    """R04 admission over the canonical proposal list. Returns
    (proposals, limits, unresolved). Claims are never attached as evidence;
    conflicts are routed structurally; related proposals move to unresolved."""
    if ca_mode != FULL:
        return proposals, limits, unresolved

    if ca["unavailable_keys"]:
        limits.append(
            "context verification unavailable keys excluded from evidence (UNKNOWN): "
            + ", ".join(sorted(str(k) for k in ca["unavailable_keys"]))
        )
    if ca["conflict_keys"]:
        limits.append(
            "context claims excluded (known conflicts): "
            + ", ".join(sorted(str(k) for k in ca["conflict_keys"]))
        )

    kept = list(proposals)
    for row in ca["conflict_rows"]:
        if not isinstance(row, dict):
            continue
        row_text = " ".join(
            [str(row.get("scope") or ""), str(row.get("key") or ""),
             claim_value_text(row)] +
            [claim_value_text(c) for c in row.get("claims", []) if isinstance(c, dict)]
        )
        mentioned_paths = sorted(p for p in changed_paths if p and mentions(row_text, p))
        mentioned_nodes = sorted(n for n in node_ids if n and mentions(row_text, n))
        if not mentioned_paths and not mentioned_nodes:
            continue
        unresolved.append(
            {
                "subject": f"conflict:{row.get('key')}",
                "reason": "HUMAN_REQUIRED",
                "evidence": [
                    make_evidence(
                        "context_claim",
                        detail=row_text[:300],
                        claim_id=None,
                        claim_scope=row.get("scope"),
                        unverified=True,
                    )
                ],
                "note": "相关 CA conflict（paths: " + ", ".join(mentioned_paths)
                        + "; nodes: " + ", ".join(mentioned_nodes)
                        + "）；C 不选边，相关候选转人工",
            }
        )
        still_kept = []
        for proposal in kept:
            touched_nodes = set(proposal.get("node_ids") or [])
            change = proposal.get("proposed_change") or {}
            for key in ("node_id", "from", "to"):
                if change.get(key):
                    touched_nodes.add(change[key])
            evidence_paths = [e.get("path") for e in proposal.get("evidence", []) if e.get("path")]
            touches = (
                mentions(row_text, proposal["subject"])
                or any(mentions(row_text, node_id) for node_id in touched_nodes)
                or any(mentions(row_text, path) for path in evidence_paths)
            )
            if touches:
                unresolved.append(
                    {
                        "subject": proposal["subject"],
                        "reason": "HUMAN_REQUIRED",
                        "evidence": proposal["evidence"][:1],
                        "note": f"候选因相关 conflict {row.get('key')} 暂停，待人工裁决",
                    }
                )
                limits.append(
                    f"proposal moved to unresolved (related known conflict {row.get('key')}): "
                    f"{proposal['kind']}:{proposal['subject']}"
                )
            else:
                still_kept.append(proposal)
        kept = still_kept
    return kept, limits, unresolved
