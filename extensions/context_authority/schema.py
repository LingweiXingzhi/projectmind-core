"""Context Authority claim schema: types, domains, validation.

Design rules (see CONTEXT_AUTHORITY_MVP_REPORT.md):
  - STALE / SUPERSEDED / CONFLICTED are RESOLVER-DERIVED states, never stored
    in claims.jsonl; stored claims carry no state field.
  - There is no global type precedence. Authority is decided per domain.
  - All validation errors are explicit ClaimValidationError; nothing is
    silently dropped or defaulted.
"""
from __future__ import annotations

import json
import re
from http import HTTPStatus

from extension_host import ExtensionError

CLAIM_TYPES = ("VERIFIED_FACT", "HUMAN_DECISION", "CONTRACT",
               "PROPOSAL", "RESEARCH", "HISTORICAL")

# Domains decide which types may answer for them (CURRENT authority).
# There is deliberately no ordering between types inside a set: if two
# different-type claims both qualify for CURRENT and their values differ,
# the result is CONFLICT / HUMAN_REQUIRED, not a silent winner.
DOMAIN_AUTHORITY = {
    "team": ("HUMAN_DECISION", "CONTRACT"),
    "implementation": ("VERIFIED_FACT",),
    "contract": ("CONTRACT", "HUMAN_DECISION"),
    "architecture": ("HUMAN_DECISION", "CONTRACT", "PROPOSAL"),
    "research": ("RESEARCH",),
}

# Types that may appear in CURRENT_STATE.current once resolved.
CURRENT_ELIGIBLE = ("VERIFIED_FACT", "HUMAN_DECISION", "CONTRACT")

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
ID_PATTERN = re.compile(r"^claim-[a-z0-9][a-z0-9._-]{0,79}$")
SCOPE_PATTERN = re.compile(r"^[\w.\-/:@ ]{0,120}$")

REQUIRED_FIELDS = ("id", "key", "value", "type", "scope", "source")
OPTIONAL_FIELDS = ("supersedes", "created_at", "verified_at", "revision", "notes")
KNOWN_SOURCES = ("repo", "gh_api", "doc", "human", "report", "research_artifact")


class ClaimValidationError(ValueError):
    """Registry data problem; must fail explicitly, never be swallowed."""


def as_extension_error(exc: ClaimValidationError) -> Exception:
    return ExtensionError(HTTPStatus.BAD_REQUEST, f"claim registry invalid: {exc}")


def validate_key_domain_match(key: str, ctype: str) -> None:
    domain = key.split(".", 1)[0]
    allowed = DOMAIN_AUTHORITY.get(domain)
    if allowed is None:
        raise ClaimValidationError(
            f"unknown domain {domain!r} in key {key!r}; known domains: "
            f"{sorted(DOMAIN_AUTHORITY)}")
    # HISTORICAL is provenance-only and loadable on any domain; the resolver
    # guarantees it can never enter CURRENT_STATE.current.
    if ctype != "HISTORICAL" and ctype not in allowed:
        raise ClaimValidationError(
            f"type {ctype} is not an authority for domain {domain!r} "
            f"(allowed: {list(allowed)}); key={key!r}")


def validate_claim(claim: object) -> dict:
    """Validate one registry entry; returns the normalized dict."""
    if not isinstance(claim, dict):
        raise ClaimValidationError("claim must be a JSON object")
    unknown = set(claim) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if unknown:
        raise ClaimValidationError(f"unknown fields {sorted(unknown)}; "
                                   f"claim id={claim.get('id')!r}")
    missing = [f for f in REQUIRED_FIELDS if f not in claim]
    if missing:
        raise ClaimValidationError(f"missing fields {missing}; id={claim.get('id')!r}")
    cid = claim["id"]
    if not isinstance(cid, str) or not ID_PATTERN.fullmatch(cid):
        raise ClaimValidationError(f"bad claim id {cid!r}")
    key = claim["key"]
    if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
        raise ClaimValidationError(f"bad key {key!r} (want dotted lowercase domain.name)")
    ctype = claim["type"]
    if ctype not in CLAIM_TYPES:
        raise ClaimValidationError(f"unknown claim type {ctype!r} (id={cid})")
    validate_key_domain_match(key, ctype)
    scope = claim["scope"]
    if not isinstance(scope, str) or not SCOPE_PATTERN.fullmatch(scope):
        raise ClaimValidationError(f"bad scope {scope!r} (id={cid})")
    validate_json_value(claim["value"], cid)
    src = claim["source"]
    if not isinstance(src, dict) or not src:
        raise ClaimValidationError(f"source must be a non-empty object; id={cid}")
    bad_src = set(src) - {"kind", "ref", "revision"}
    if bad_src:
        raise ClaimValidationError(f"source has unknown fields {sorted(bad_src)}; id={cid}")
    if src.get("kind") not in KNOWN_SOURCES:
        raise ClaimValidationError(
            f"source.kind must be one of {KNOWN_SOURCES}; id={cid}")
    if src["kind"] == "research_artifact" and ctype in CURRENT_ELIGIBLE:
        raise ClaimValidationError(
            f"research_artifact cannot establish current authority for {ctype}; "
            f"record distinct human confirmation with a human source; id={cid}")
    if not isinstance(src.get("ref"), str) or not src["ref"].strip():
        raise ClaimValidationError(f"source.ref must be a non-empty string; id={cid}")
    if "revision" in src and not (isinstance(src["revision"], str) and src["revision"]):
        raise ClaimValidationError(f"source.revision must be a non-empty string; id={cid}")
    sup = claim.get("supersedes", [])
    if not isinstance(sup, list) or any(not isinstance(x, str) for x in sup):
        raise ClaimValidationError(f"supersedes must be a list of claim ids; id={cid}")
    for field in ("created_at", "verified_at"):
        if field in claim and not isinstance(claim[field], str):
            raise ClaimValidationError(f"{field} must be an ISO string; id={cid}")
    if "revision" in claim and not (
            isinstance(claim["revision"], str) and claim["revision"]):
        raise ClaimValidationError(f"revision must be a non-empty string; id={cid}")
    return claim


def validate_json_value(value, cid: str = "live") -> None:
    """Reject Python-only structures and non-finite numbers, including nested ones."""
    pending = [value]
    seen = set()
    while pending:
        item = pending.pop()
        if isinstance(item, (dict, list)):
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, dict):
                if any(not isinstance(k, str) for k in item):
                    raise ClaimValidationError(f"JSON object keys must be strings; id={cid}")
                pending.extend(item.values())
            else:
                pending.extend(item)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ClaimValidationError(f"value must contain only JSON values; id={cid}")
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ClaimValidationError(f"value must be finite, acyclic JSON; id={cid}") from exc


def normalize_claim(claim: dict) -> dict:
    """Return a copy with deterministic field order and defaults applied."""
    out = {f: claim[f] for f in REQUIRED_FIELDS}
    if "supersedes" in claim:
        out["supersedes"] = list(claim["supersedes"])
    for f in ("created_at", "verified_at", "revision", "notes"):
        if f in claim:
            out[f] = claim[f]
    return out
