"""Deterministic claim resolver.

Rules (no exceptions, no hidden precedence, no timestamps-wins):
  1. supersedes edges mark the referenced claims SUPERSEDED (provenance kept).
  2. HISTORICAL and PROPOSAL and RESEARCH can never enter `current`.
  3. Within one (key, scope) group, ACTIVE current-eligible claims with the
     SAME value collapse deterministically; with DIFFERENT values they all
     become CONFLICTED -> resolution HUMAN_REQUIRED. Newer timestamps win
     nothing.
  4. VERIFIED_FACT claims whose key has a live verifier are checked: stored
     value != live value -> stored claim STALE, a deterministic auto-claim
     carrying the live value becomes ACTIVE. Verifier unavailable is REPORTED,
     never silently ignored.
Everything is sorted; registry line order cannot change the output.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from extensions.context_authority.registry import RegistryProblems
from extensions.context_authority.schema import CURRENT_ELIGIBLE

STATES = ("ACTIVE", "STALE", "SUPERSEDED", "CONFLICTED")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def registry_hash(claims: list[dict]) -> str:
    payload = "".join(canonical(c) for c in sorted(claims, key=lambda c: c["id"]))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _auto_claim_id(key: str) -> str:
    safe = key.replace(".", "-").replace("_", "-")
    return f"claim-auto-{safe}"[:88]


def resolve(claims: list[dict], verifiers: dict | None = None,
            problems: RegistryProblems | None = None,
            run_verifiers: bool = True) -> dict:
    verifiers = verifiers or {}
    problems = problems if problems is not None else RegistryProblems()
    by_id = {c["id"]: c for c in claims}

    superseded: set[str] = set()
    for c in claims:
        for target in c.get("supersedes", []):
            if target in by_id:
                superseded.add(target)
            else:
                problems.add("BROKEN_SUPERSEDES",
                             f"{c['id']} supersedes unknown claim {target!r}",
                             claim_id=c["id"], target=target)

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in claims:
        groups[(c["key"], c["scope"])].append(c)

    current: dict[str, dict] = {}
    conflicts: list[dict] = []
    stale: list[dict] = []
    proposals: list[dict] = []
    research: list[dict] = []
    historical: list[dict] = []
    verification_unavailable: list[dict] = []

    def with_state(claim: dict, state: str, extra: dict | None = None) -> dict:
        row = {"claim_id": claim["id"], "key": claim["key"], "scope": claim["scope"],
               "type": claim["type"], "state": state, "value": claim["value"],
               "source": claim["source"]}
        for f in ("revision", "created_at", "verified_at", "notes", "supersedes"):
            if f in claim:
                row[f] = claim[f]
        if extra:
            row.update(extra)
        return row

    for (key, scope) in sorted(groups):
        members = sorted(groups[(key, scope)], key=lambda c: c["id"])
        domain = key.split(".", 1)[0]
        current_pool: list[dict] = []
        for c in members:
            if c["id"] in superseded:
                stale.append(with_state(c, "SUPERSEDED",
                                        {"superseded_by": [x["id"] for x in members
                                                           if c["id"] in x.get("supersedes", [])]}))
                continue
            if c["type"] == "HISTORICAL":
                historical.append(with_state(c, "ACTIVE"))
                continue
            if c["type"] == "PROPOSAL":
                proposals.append(with_state(c, "ACTIVE"))
                continue
            if c["type"] == "RESEARCH":
                research.append(with_state(c, "ACTIVE"))
                continue
            if c["type"] == "VERIFIED_FACT" and run_verifiers and key in verifiers:
                outcome = verifiers[key](c)
                if outcome["status"] == "ok":
                    live = outcome["value"]
                    if canonical(live) != canonical(c["value"]):
                        stale.append(with_state(c, "STALE",
                                                {"stale_reason": "live verification differs",
                                                 "live_value": live}))
                        current_pool.append({
                            "id": _auto_claim_id(key), "key": key, "scope": scope,
                            "type": "VERIFIED_FACT", "value": live,
                            "source": {"kind": outcome.get("source_kind", "gh_api"),
                                       "ref": "live verification"},
                            "verified_at": outcome.get("verified_at", ""),
                        })
                        continue
                    current_pool.append(c)
                    continue
                verification_unavailable.append(
                    {"key": key, "claim_id": c["id"], "reason": outcome["reason"]})
            current_pool.append(c)

        if not current_pool:
            continue
        # same-value collapse; different values -> CONFLICT (no auto winner)
        buckets: dict[str, list[dict]] = defaultdict(list)
        for c in current_pool:
            buckets[canonical(c["value"])].append(c)
        if len(buckets) > 1:
            involved = [c for c in current_pool if c["type"] in CURRENT_ELIGIBLE]
            conflicts.append({
                "key": key, "scope": scope, "status": "CONFLICT",
                "claims": [with_state(c, "CONFLICTED") for c in involved],
                "resolution": "HUMAN_REQUIRED",
            })
            continue
        winners = buckets[next(iter(buckets))]
        winner = winners[0]
        if winner["type"] not in CURRENT_ELIGIBLE:
            continue
        current[key] = {
            "value": winner["value"], "type": winner["type"],
            "claim_ids": sorted(w["id"] for w in winners),
            "source": winner["source"],
            **({"revision": winner["revision"]} if "revision" in winner else {}),
            **({"verified_at": winner["verified_at"]} if "verified_at" in winner else {}),
            "scope": scope,
        }

    state = {
        "generated_at_note": "derived view - regenerate rather than hand-edit",
        "current": current,
        "conflicts": sorted(conflicts, key=lambda x: (x["key"], x["scope"])),
        "stale": sorted(stale, key=lambda x: (x["key"], x["claim_id"])),
        "proposals": sorted(proposals, key=lambda x: x["claim_id"]),
        "research": sorted(research, key=lambda x: x["claim_id"]),
        "historical": sorted(historical, key=lambda x: x["claim_id"]),
        "verification_unavailable": verification_unavailable,
        "registry_problems": list(problems.items),
        "registry_hash": registry_hash(claims),
        "counts": {
            "current": len(current), "conflicts": len(conflicts),
            "stale": len(stale), "proposals": len(proposals),
            "research": len(research), "historical": len(historical),
        },
    }
    return state
