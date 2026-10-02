"""Deterministic, fail-closed resolution with scope and evidence preserved.

Invalid replacement graphs require a human. Live verification failures
withhold volatile claims from current. No timestamp or type majority wins.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from extensions.context_authority.registry import RegistryProblems, validate_registry_claims
from extensions.context_authority.schema import CURRENT_ELIGIBLE, validate_json_value

STATES = ("ACTIVE", "STALE", "SUPERSEDED", "CONFLICTED")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def registry_hash(claims: list[dict]) -> str:
    payload = "".join(canonical(c) for c in sorted(claims, key=lambda c: c["id"]))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _auto_claim_id(key: str) -> str:
    safe = key.replace(".", "-").replace("_", "-")
    return f"claim-auto-{safe}"[:85]


def _group(claim: dict) -> tuple[str, str]:
    return claim["key"], claim["scope"]


def _replacement_graph(claims, by_id, problems):
    edges = defaultdict(list)
    invalid = set()
    for c in claims:
        for target in sorted(set(c.get("supersedes", []))):
            other = by_id.get(target)
            kind = None
            if other is None:
                kind = "BROKEN_SUPERSEDES"
            elif target == c["id"]:
                kind = "SELF_SUPERSEDES"
            elif c["key"] != other["key"]:
                kind = "CROSS_KEY_SUPERSEDES"
            elif other["type"] in CURRENT_ELIGIBLE and c["type"] not in CURRENT_ELIGIBLE:
                kind = "INVALID_AUTHORITY_SUPERSEDES"
            elif other["type"] in CURRENT_ELIGIBLE and c["scope"] != other["scope"]:
                kind = "CROSS_SCOPE_SUPERSEDES"
            if kind:
                invalid.add(_group(c))
                if other:
                    invalid.add(_group(other))
                problems.add(kind, f"{c['id']} has invalid supersedes target {target!r}",
                             claim_id=c["id"], target=target, resolution="HUMAN_REQUIRED")
            else:
                edges[c["id"]].append(target)
    # DFS frames avoid recursion failure for large replacement chains.
    colors, cycles = {}, set()
    for start in sorted(by_id):
        if colors.get(start):
            continue
        path, positions = [start], {start: 0}
        colors[start] = 1
        frames = [(start, iter(edges[start]))]
        while frames:
            node, neighbors = frames[-1]
            target = next(neighbors, None)
            if target is None:
                frames.pop()
                colors[node] = 2
                positions.pop(node)
                path.pop()
            elif colors.get(target) == 1:
                cycles.update(path[positions[target]:])
            elif not colors.get(target):
                colors[target] = 1
                positions[target] = len(path)
                path.append(target)
                frames.append((target, iter(edges[target])))
    if cycles:
        invalid.update(_group(by_id[cid]) for cid in cycles)
        problems.add("CYCLIC_SUPERSEDES", "supersedes graph contains a cycle",
                     claim_ids=sorted(cycles), resolution="HUMAN_REQUIRED")
    replaced_by = defaultdict(list)
    for cid in sorted(edges):
        for target in edges[cid]:
            if _group(by_id[cid]) not in invalid and _group(by_id[target]) not in invalid:
                replaced_by[target].append(cid)
    return replaced_by, invalid


def _verify(verifier, claim):
    try:
        outcome = verifier(claim)
        if not isinstance(outcome, dict) or outcome.get("status") not in ("ok", "unavailable"):
            raise ValueError("invalid verifier response")
        if outcome["status"] == "ok":
            if "value" not in outcome:
                raise ValueError("verifier response missing value")
            validate_json_value(outcome["value"])
            if outcome.get("source_kind", "gh_api") not in ("repo", "gh_api", "doc", "human", "report", "research_artifact"):
                raise ValueError("invalid verifier source kind")
            if not isinstance(outcome.get("source_ref", "live verification"), str):
                raise ValueError("invalid verifier source ref")
            if not isinstance(outcome.get("verified_at", ""), str):
                raise ValueError("invalid verifier timestamp")
        elif not isinstance(outcome.get("reason"), str) or not outcome["reason"]:
            raise ValueError("unavailable verifier response missing reason")
        return outcome
    except Exception as exc:
        return {"status": "unavailable", "reason": f"verifier failed: {type(exc).__name__}: {str(exc)[:160]}"}


def resolve(claims: list[dict], verifiers: dict | None = None,
            problems: RegistryProblems | None = None,
            run_verifiers: bool = True) -> dict:
    claims = sorted(validate_registry_claims(claims), key=lambda c: c["id"])
    verifiers = verifiers or {}
    problems = problems if problems is not None else RegistryProblems()
    by_id = {c["id"]: c for c in claims}
    replaced_by, invalid_groups = _replacement_graph(claims, by_id, problems)
    groups = defaultdict(list)
    for c in claims:
        groups[_group(c)].append(c)
    current_by_scope, conflicts, stale, proposals, research, historical = [], [], [], [], [], []
    verification_unavailable = []
    active_scopes = defaultdict(set)
    generated_ids = {}

    def with_state(claim, state, extra=None):
        result = {"claim_id": claim["id"], "key": claim["key"], "scope": claim["scope"],
                  "type": claim["type"], "state": state, "value": claim["value"], "source": claim["source"]}
        for field in ("revision", "created_at", "verified_at", "notes", "supersedes",
                      "live_verification", "derived_from_ids", "derived_from_sources"):
            if field in claim:
                result[field] = claim[field]
        result.update(extra or {})
        return result

    def evidence(claim):
        item = {"claim_id": claim["id"], "key": claim["key"], "scope": claim["scope"],
                "value": claim["value"], "type": claim["type"], "source": claim["source"]}
        for field in ("revision", "verified_at", "live_verification", "derived_from_ids", "derived_from_sources"):
            if field in claim:
                item[field] = claim[field]
        return item

    def auto_id(key, scope, value):
        base = _auto_claim_id(key)
        identity = (key, scope, canonical(value))
        if base in by_id or base in generated_ids and generated_ids[base] != identity:
            digest = hashlib.sha256(canonical(identity).encode("utf-8")).hexdigest()[:16]
            base = base[:68] + "-" + digest
            while base in by_id or base in generated_ids and generated_ids[base] != identity:
                digest = hashlib.sha256((base + canonical(identity)).encode("utf-8")).hexdigest()[:16]
                base = _auto_claim_id(key)[:68] + "-" + digest
        generated_ids[base] = identity
        return base

    for (key, scope), members in sorted(groups.items()):
        current_pool = []
        for c in members:
            if c["id"] in replaced_by:
                stale.append(with_state(c, "SUPERSEDED", {"superseded_by": sorted(replaced_by[c["id"]])}))
                continue
            if c["type"] in ("HISTORICAL", "PROPOSAL", "RESEARCH"):
                {"HISTORICAL": historical, "PROPOSAL": proposals, "RESEARCH": research}[c["type"]].append(with_state(c, "ACTIVE"))
                continue
            active_scopes[key].add(scope)
            if (key, scope) in invalid_groups:
                current_pool.append(c)
                continue
            if c["type"] == "VERIFIED_FACT" and run_verifiers and key in verifiers:
                outcome = _verify(verifiers[key], c)
                if outcome["status"] != "ok":
                    verification_unavailable.append({"key": key, "scope": scope, "claim_id": c["id"],
                                                     "source": c["source"], "reason": outcome["reason"]})
                    stale.append(with_state(c, "STALE", {"stale_reason": "live verification unavailable",
                                                         "verification_status": "unavailable"}))
                    continue
                verification = {"source": {"kind": outcome.get("source_kind", "gh_api"),
                                            "ref": outcome.get("source_ref", "live verification")},
                                "verified_at": outcome.get("verified_at", "")}
                for field in ("verified_fields", "freshness"):
                    if field in outcome:
                        verification[field] = outcome[field]
                live = outcome["value"]
                if canonical(live) != canonical(c["value"]):
                    stale.append(with_state(c, "STALE", {"stale_reason": "live verification differs",
                                                         "live_value": live, "live_verification": verification}))
                    current_pool.append({"id": auto_id(key, scope, live), "key": key, "scope": scope,
                                         "type": "VERIFIED_FACT", "value": live,
                                         "source": verification["source"], "verified_at": verification["verified_at"],
                                         "live_verification": verification, "derived_from_ids": [c["id"]],
                                         "derived_from_sources": [evidence(c)]})
                    continue
                c = {**c, "verified_at": verification["verified_at"], "live_verification": verification}
            current_pool.append(c)
        if not current_pool:
            continue
        buckets = defaultdict(list)
        for c in current_pool:
            buckets[canonical(c["value"])].append(c)
        if len(buckets) > 1 or (key, scope) in invalid_groups:
            conflicts.append({"key": key, "scope": scope, "status": "CONFLICT",
                              "claims": [with_state(c, "CONFLICTED") for c in current_pool],
                              "resolution": "HUMAN_REQUIRED",
                              **({"reason": "invalid supersedes graph"} if (key, scope) in invalid_groups else {})})
            continue
        winners = buckets[next(iter(buckets))]
        winner = winners[0]
        all_evidence = {}
        for c in winners:
            item = evidence(c)
            if c["id"] in all_evidence and "derived_from_ids" in item:
                prior = all_evidence[c["id"]]
                prior["derived_from_ids"] = sorted(set(prior["derived_from_ids"] + item["derived_from_ids"]))
                sources = {s["claim_id"]: s for s in prior["derived_from_sources"] + item["derived_from_sources"]}
                prior["derived_from_sources"] = [sources[cid] for cid in sorted(sources)]
            else:
                all_evidence[c["id"]] = item
        verified_freshness = {w.get("live_verification", {}).get("freshness", "verified") for w in winners}
        freshness = (next(iter(verified_freshness)) if len(verified_freshness) == 1 else "mixed")
        if not all("live_verification" in w for w in winners):
            freshness = "unverified"
        resolved = {"key": key, "scope": scope, "value": winner["value"], "type": winner["type"],
                    "types": sorted({w["type"] for w in winners}),
                    "claim_ids": sorted(all_evidence), "source": winner["source"],
                    "evidence": [all_evidence[cid] for cid in sorted(all_evidence)],
                    "freshness": freshness}
        for field in ("revision", "verified_at"):
            if field in winner:
                resolved[field] = winner[field]
        current_by_scope.append(resolved)
    current = {r["key"]: {k: v for k, v in r.items() if k != "key"}
               for r in current_by_scope if len(active_scopes[r["key"]]) == 1}
    return {
        "generated_at_note": "derived view - regenerate rather than hand-edit",
        "current": current, "current_by_scope": current_by_scope,
        "conflicts": conflicts, "stale": sorted(stale, key=lambda x: (x["key"], x["scope"], x["claim_id"])),
        "proposals": sorted(proposals, key=lambda x: x["claim_id"]),
        "research": sorted(research, key=lambda x: x["claim_id"]),
        "historical": sorted(historical, key=lambda x: x["claim_id"]),
        "verification_unavailable": sorted(verification_unavailable, key=lambda x: (x["key"], x["scope"], x["claim_id"])),
        "registry_problems": sorted(problems.items, key=canonical), "registry_hash": registry_hash(claims),
        "counts": {"current": len(current_by_scope), "conflicts": len(conflicts), "stale": len(stale),
                   "proposals": len(proposals), "research": len(research), "historical": len(historical)},
    }
