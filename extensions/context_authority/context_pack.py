"""Versioned Context Pack and consumer validation.

Internal consistency is not source authentication or proof that a claim is true.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess

from extensions.context_authority.registry import RegistryProblems, load_registry
from extensions.context_authority.resolver import registry_hash, resolve
from extensions.context_authority.schema import (CLAIM_TYPES, CURRENT_ELIGIBLE, ID_PATTERN,
                                                KEY_PATTERN, SCOPE_PATTERN, validate_key_domain_match,
                                                validate_json_value)
from extensions.context_authority.verifiers import build_default_verifiers

SCHEMA_VERSION = "0.1"
REVISION_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
TASK_KEYWORDS = {
    "role": ("team",), "roles": ("team",), "team": ("team",),
    "分工": ("team",), "职责": ("team",), "responsib": ("team",),
    "code facts": ("implementation", "contract"), "pr": ("implementation",),
    "merge": ("implementation",), "revision": ("implementation",), "head": ("implementation",),
    "contract": ("contract",), "接口": ("contract",),
    # C consumes authority, input contracts, implementation status and caveats.
    "map": ("team", "contract", "architecture", "implementation", "research"),
    "架构": ("architecture",), "architecture": ("architecture",), "proposal": ("architecture",),
    "research": ("research",), "性能": ("research",), "performance": ("research",),
}
SECTION_TYPES = {"human_decisions": "HUMAN_DECISION", "verified_facts": "VERIFIED_FACT",
                 "relevant_contracts": "CONTRACT", "proposals": "PROPOSAL",
                 "research_notes": "RESEARCH", "historical_sources": "HISTORICAL"}


class ContextPackValidationError(ValueError):
    """Malformed or inconsistent pack; consumers must reject it."""


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def context_pack_digest(pack: dict) -> str:
    """Unkeyed checksum; does not authenticate a source or establish truth."""
    body = {k: v for k, v in pack.items() if k != "integrity"}
    return "sha256:" + hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _domains_for(task: str) -> tuple[str, ...] | None:
    hits = []
    for kw, domains in TASK_KEYWORDS.items():
        pattern = r"\b" + re.escape(kw) + r"\b" if kw.isascii() else re.escape(kw)
        if kw == "responsib":
            pattern = r"\bresponsib\w*\b"
        if re.search(pattern, task.lower()):
            hits.extend(domains)
    return tuple(dict.fromkeys(hits)) or None


def _relevant(key: str, domains: tuple[str, ...] | None) -> bool:
    return domains is None or key.split(".", 1)[0] in domains


def _project_revision(repo_root: str, revision: str | None) -> str:
    if revision is not None and (not isinstance(revision, str) or not REVISION_PATTERN.fullmatch(revision)):
        raise ValueError("revision must be a full lowercase 40/64-character Git commit SHA")
    # R48-05: the explicit repository wins. Inherited GIT_* (GIT_DIR /
    # GIT_WORK_TREE / GIT_COMMON_DIR / ...) is stripped so a Context Pack can
    # never be stamped with another repository's revision.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        result = subprocess.run(["git", "rev-parse", "--verify", (revision or "HEAD") + "^{commit}"],
                                cwd=repo_root, capture_output=True, text=True, timeout=10,
                                check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("cannot resolve project revision from repository") from exc
    resolved = result.stdout.strip()
    if result.returncode or not REVISION_PATTERN.fullmatch(resolved) or (revision and resolved != revision):
        raise ValueError("revision does not resolve directly to an existing Git commit")
    return resolved


def _evidence(claim: dict, aggregate: dict | None = None) -> dict:
    row = aggregate or claim
    source = copy.deepcopy(claim["source"])
    explicit = claim.get("revision")
    out = {"claim_id": claim.get("id", claim.get("claim_id")),
           "key": row["key"], "scope": row["scope"], "type": row["type"],
           "value": copy.deepcopy(row["value"]), "source": source,
           "revision": explicit or source.get("revision"), "claim_revision": explicit,
           "source_revision": source.get("revision")}
    for field in ("verified_at", "supersedes", "live_verification", "derived_from_ids", "derived_from_sources"):
        if field in claim:
            out[field] = copy.deepcopy(claim[field])
    return out


def _current_projection(rows, conflicts, unavailable):
    scopes = {}
    for row in [*rows, *conflicts, *unavailable]:
        scopes.setdefault(row["key"], set()).add(row["scope"])
    return {row["key"]: {k: v for k, v in row.items() if k != "key"}
            for row in rows if len(scopes[row["key"]]) == 1}


def _freshness(evidence):
    if not all("live_verification" in item for item in evidence):
        return "unverified"
    values = {item["live_verification"].get("freshness", "verified") for item in evidence}
    return next(iter(values)) if len(values) == 1 else "mixed"


def _binding_revision(claim: dict) -> str | None:
    if claim["type"] != "VERIFIED_FACT" or not claim["key"].startswith("implementation."):
        return None
    if claim.get("revision"):
        return claim["revision"]
    source = claim["source"]
    if source.get("kind") == "repo" and REVISION_PATTERN.fullmatch(source.get("revision", "")):
        return source["revision"]
    return None


def build_do_not_assume(state: dict) -> list[str]:
    rules = []
    rows = state.get("current_by_scope", [{"key": k, **v} for k, v in state["current"].items()])
    for row in rows:
        value = row.get("value")
        if isinstance(value, dict) and value.get("status") in ("PR_OPEN", "OPEN"):
            rules.append(f"PR #{value.get('pr', 'unknown')} is OPEN - OPEN does not mean merged; "
                         "its branch content is not main content")
    if state["proposals"]:
        rules.append("PROPOSAL entries exist - a proposal is not accepted architecture")
    if state["research"]:
        rules.append("RESEARCH entries exist - research findings and suggestions are not contract and must not be restated as requirements")
    if state["historical"]:
        rules.append("HISTORICAL material exists - historical reports/mappings describe a past state, never the current one")
    if state["stale"]:
        rules.append(f"{len(state['stale'])} stale/superseded claims exist - do not use them as current facts")
    if state["conflicts"]:
        rules.append(f"{len(state['conflicts'])} unresolved conflicts exist - treat them as HUMAN_REQUIRED, do not pick a side yourself")
    if state["verification_unavailable"]:
        rules.append("Verification is unavailable for some claims - stored values are not live verification")
    if any(row.get("freshness") in ("local_reference", "mixed") for row in rows):
        rules.append("Local Git references may be cached - origin/main is not proof of the remote HEAD")
    rules.extend([
        "CodeFacts provides declarations (def/class, path, line) only - no dependency graph, signatures, or entry points",
        "the curated map currently has no version identity - Snapshot.revision never proves the map applies to that commit",
        "Project revision pins the requested code context; source revisions identify provenance and do not confirm applicability",
        "Pack validation and an unkeyed digest establish structural consistency only; human authority and semantic truth require source review",
    ])
    return list(dict.fromkeys(rules))


def build_context_pack(task: str, repo_root: str, registry_path,
                       revision: str | None = None, run_verifiers: bool = True) -> dict:
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be a non-empty string")
    if not isinstance(run_verifiers, bool):
        raise ValueError("run_verifiers must be a boolean")
    project_revision = _project_revision(repo_root, revision)
    problems = RegistryProblems()
    claims = load_registry(registry_path, problems)
    # Resolve the complete graph first: filtering old revisions before resolution
    # would make a valid replacement edge appear to reference a missing claim.
    state = resolve(claims, verifiers=build_default_verifiers(repo_root) if run_verifiers else {},
                    problems=problems, run_verifiers=run_verifiers)
    state["registry_hash"] = registry_hash(claims)
    domains = _domains_for(task)
    by_id = {c["id"]: c for c in claims}
    rows = state.get("current_by_scope", [{"key": k, **v} for k, v in state["current"].items()])
    current_rows = []
    evidence = {}
    for original in rows:
        if not _relevant(original["key"], domains):
            continue
        row = copy.deepcopy(original)
        generated = {e["claim_id"]: e for e in row.get("evidence", [])}
        refs = []
        for cid in row["claim_ids"]:
            if cid in by_id:
                ref = _evidence({**by_id[cid], **generated.get(cid, {})})
            elif cid in generated:
                ref = _evidence(generated[cid], row)
            else:
                raise ValueError(f"resolved claim {cid!r} has no provenance")
            evidence[cid] = ref
            bindings = [_binding_revision({**ref, "revision": ref["claim_revision"]})]
            bindings.extend(_binding_revision(source) for source in ref.get("derived_from_sources", []))
            if any(binding and binding != project_revision for binding in bindings):
                state["stale"].append({"claim_id": cid, **{k: copy.deepcopy(ref[k])
                                      for k in ("key", "scope", "type", "value", "source")},
                                      "state": "STALE", "stale_reason": "claim revision differs from requested project revision",
                                      **({"revision": ref["claim_revision"]} if ref["claim_revision"] else {}),
                                      **{k: ref[k] for k in ("derived_from_ids", "derived_from_sources") if k in ref}})
            else:
                refs.append(ref)
        if not refs:
            continue
        row["claim_ids"] = [ref["claim_id"] for ref in refs]
        row["evidence"] = refs
        row["type"] = refs[0]["type"]
        row["types"] = sorted({ref["type"] for ref in refs})
        row["source"] = refs[0]["source"]
        row.pop("revision", None)
        row.pop("verified_at", None)
        if refs[0]["claim_revision"]:
            row["revision"] = refs[0]["claim_revision"]
        if "verified_at" in refs[0]:
            row["verified_at"] = refs[0]["verified_at"]
        row["freshness"] = _freshness(refs)
        current_rows.append(row)
    names = ("conflicts", "stale", "proposals", "research", "historical", "verification_unavailable")
    filtered = {name: [copy.deepcopy(row) for row in state[name] if _relevant(row["key"], domains)] for name in names}
    for name in ("stale", "proposals", "research", "historical"):
        for row in filtered[name]:
            prior = evidence.get(row["claim_id"])
            evidence[row["claim_id"]] = _evidence({**by_id.get(row["claim_id"], {}), **row}, row)
            if prior:
                evidence[row["claim_id"]].update({k: prior[k] for k in ("live_verification", "verified_at", "derived_from_ids", "derived_from_sources") if k in prior})
    for conflict in filtered["conflicts"]:
        for row in conflict["claims"]:
            evidence[row["claim_id"]] = _evidence(by_id.get(row["claim_id"], row), row)
    current = _current_projection(current_rows, filtered["conflicts"], filtered["verification_unavailable"])
    pack = {"schema_version": SCHEMA_VERSION, "task": task,
            "task_domains": list(domains) if domains else "all", "project_revision": project_revision,
            "current_state": {"current": current, "current_by_scope": current_rows,
                              "counts": {"current": len(current_rows), **{name: len(filtered[name])
                                         for name in ("conflicts", "stale", "proposals", "research", "historical")}},
                              "registry_hash": state["registry_hash"]},
            "known_conflicts": filtered["conflicts"], "known_stale_sources": filtered["stale"],
            "proposals": filtered["proposals"], "research_notes": filtered["research"],
            "historical_sources": filtered["historical"], "verification_unavailable": filtered["verification_unavailable"],
            "registry_problems": state["registry_problems"], "do_not_assume": build_do_not_assume(state),
            "evidence": [evidence[cid] for cid in sorted(evidence)]}
    for section, ctype in SECTION_TYPES.items():
        if section not in pack:
            pack[section] = [copy.deepcopy(row) for row in current_rows if row["type"] == ctype]
    pack["integrity"] = {"algorithm": "sha256", "digest": context_pack_digest(pack), "guarantee": "structural_consistency_only"}
    validate_context_pack(pack, expected_revision=project_revision)
    return pack


def validate_context_pack(pack: object, expected_revision: str | None = None) -> dict:
    """Reject inconsistent packs before C consumes them; return unchanged on success.

    An internally coherent forgery can pass. Sources and semantic truth still
    require independent review. expected_revision comes from the consumer.
    """
    try:
        return _validate_context_pack(pack, expected_revision)
    except ContextPackValidationError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError) as exc:
        raise ContextPackValidationError("malformed context pack structure") from exc


def _validate_context_pack(pack, expected_revision):
    def require(condition, detail):
        if not condition:
            raise ContextPackValidationError(detail)

    require(isinstance(pack, dict), "context pack must be an object")
    fields = {"schema_version", "task", "task_domains", "project_revision", "current_state", *SECTION_TYPES,
              "known_conflicts", "known_stale_sources", "do_not_assume", "verification_unavailable",
              "registry_problems", "evidence", "integrity"}
    require(set(pack) == fields, "context pack fields do not match schema 0.1")
    require(pack["schema_version"] == SCHEMA_VERSION, "unsupported context pack schema_version")
    require(isinstance(pack["task"], str) and bool(pack["task"].strip()), "invalid task")
    revision = pack["project_revision"]
    require(isinstance(revision, str) and bool(REVISION_PATTERN.fullmatch(revision)), "invalid project revision")
    if expected_revision is not None:
        require(isinstance(expected_revision, str) and bool(REVISION_PATTERN.fullmatch(expected_revision)), "invalid consumer revision")
        require(revision == expected_revision, "context pack revision differs from consumer revision")
    domains = _domains_for(pack["task"])
    require(pack["task_domains"] == (list(domains) if domains else "all"), "task domains contradict task")
    for name in (*SECTION_TYPES, "known_conflicts", "known_stale_sources", "do_not_assume",
                 "verification_unavailable", "registry_problems", "evidence"):
        require(isinstance(pack[name], list), f"{name} must be a list")
    require(bool(pack["do_not_assume"]) and all(isinstance(rule, str) and rule for rule in pack["do_not_assume"]), "invalid authority warnings")
    cs = pack["current_state"]
    require(isinstance(cs, dict) and set(cs) == {"current", "current_by_scope", "counts", "registry_hash"}, "invalid current_state")
    require(isinstance(cs["current"], dict) and isinstance(cs["current_by_scope"], list), "invalid current projections")
    require(isinstance(cs["registry_hash"], str) and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", cs["registry_hash"])), "invalid registry_hash")
    references = {}
    for item in pack["evidence"]:
        required = {"claim_id", "key", "scope", "type", "value", "source", "revision", "claim_revision", "source_revision"}
        require(isinstance(item, dict) and required <= set(item), "incomplete evidence")
        require(set(item) <= required | {"verified_at", "supersedes", "live_verification", "derived_from_ids", "derived_from_sources"}, "unknown evidence fields")
        cid = item["claim_id"]
        require(isinstance(cid, str) and bool(ID_PATTERN.fullmatch(cid)), "invalid evidence claim_id")
        require(cid not in references, "duplicate evidence claim_id")
        require(isinstance(item["key"], str) and bool(KEY_PATTERN.fullmatch(item["key"])) and
                isinstance(item["scope"], str) and bool(SCOPE_PATTERN.fullmatch(item["scope"])) and
                item["type"] in CLAIM_TYPES, "invalid evidence identity or type")
        validate_json_value(item["value"])
        try:
            validate_key_domain_match(item["key"], item["type"])
        except (ValueError, TypeError) as exc:
            raise ContextPackValidationError("evidence type/domain mismatch") from exc
        source = item["source"]
        require(isinstance(source, dict) and isinstance(source.get("ref"), str) and bool(source["ref"].strip()) and
                source.get("kind") in ("repo", "gh_api", "doc", "human", "report", "research_artifact"), "missing source locator")
        require(set(source) <= {"kind", "ref", "revision"}, "unknown source fields")
        require(source["kind"] != "research_artifact" or item["type"] not in CURRENT_ELIGIBLE,
                "research artifact cannot authorize a current fact, contract or human decision")
        if "supersedes" in item:
            require(isinstance(item["supersedes"], list) and all(isinstance(cid, str) and ID_PATTERN.fullmatch(cid)
                    for cid in item["supersedes"]), "invalid supersedes evidence")
        for value in (item["claim_revision"], item["source_revision"]):
            require(value is None or (isinstance(value, str) and bool(value)), "invalid evidence revision")
        require(item["source_revision"] == source.get("revision"), "evidence source revision mismatch")
        require(item["revision"] == (item["claim_revision"] or item["source_revision"]), "evidence revision mismatch")
        if "live_verification" in item:
            verification = item["live_verification"]
            require(isinstance(verification, dict) and {"source", "verified_at"} <= set(verification) and
                    set(verification) <= {"source", "verified_at", "verified_fields", "freshness"}, "invalid verification evidence")
            verifier_source = verification["source"]
            require(isinstance(verifier_source, dict) and set(verifier_source) == {"kind", "ref"} and
                    verifier_source.get("kind") in ("repo", "gh_api", "doc", "human", "report", "research_artifact") and
                    isinstance(verifier_source.get("ref"), str) and bool(verifier_source["ref"].strip()) and
                    isinstance(verification["verified_at"], str), "missing verifier locator")
            require(verification.get("freshness", "verified") in ("verified", "local_reference"), "invalid verification freshness")
            if "verified_fields" in verification:
                require(isinstance(verification["verified_fields"], list) and
                        all(isinstance(field, str) for field in verification["verified_fields"]), "invalid verified_fields")
        references[cid] = item
    for item in references.values():
        if "derived_from_ids" in item or "derived_from_sources" in item:
            ids, sources = item.get("derived_from_ids"), item.get("derived_from_sources")
            require(isinstance(ids, list) and ids and len(ids) == len(set(ids)) and isinstance(sources, list), "invalid derivation links")
            require([source.get("claim_id") for source in sources] == ids, "derivation sources contradict IDs")
            for source in sources:
                cid = source["claim_id"]
                require(cid in references and cid != item["claim_id"], "missing derivation source")
                converted = _evidence(source)
                require(all(converted[field] == references[cid][field] for field in
                            ("key", "scope", "type", "value", "source", "claim_revision", "source_revision")), "derivation provenance contradiction")
    used = set()

    def check_row(row, aggregate=False):
        require(isinstance(row, dict) and {"key", "scope", "type", "value", "source"} <= set(row), "incomplete claim row")
        require(isinstance(row["key"], str) and _relevant(row["key"], domains) and isinstance(row["scope"], str), "unrelated claim or invalid scope")
        ids = row.get("claim_ids") if aggregate else [row.get("claim_id")]
        require(isinstance(ids, list) and bool(ids) and all(isinstance(cid, str) for cid in ids) and len(ids) == len(set(ids)), "invalid claim references")
        for cid in ids:
            require(cid in references, f"missing evidence for {cid!r}")
            evidence = references[cid]
            require(all(evidence[f] == row[f] for f in ("key", "scope", "value")), "claim/evidence contradiction")
            require(evidence["type"] in CURRENT_ELIGIBLE if aggregate else evidence["type"] == row["type"], "claim/evidence authority contradiction")
            if not aggregate:
                require(evidence["source"] == row["source"] and evidence["claim_revision"] == row.get("revision"), "claim/evidence source contradiction")
            used.add(cid)
        if aggregate:
            require(set(row) <= {"key", "scope", "type", "types", "value", "source", "claim_ids", "evidence",
                                 "freshness", "revision", "verified_at"}, "unknown current fields")
            require(row.get("evidence") == [references[cid] for cid in ids], "aggregate provenance contradiction")
            require(row["source"] == references[ids[0]]["source"] and row["type"] == references[ids[0]]["type"] and
                    row.get("types") == sorted({references[cid]["type"] for cid in ids}) and
                    row.get("revision") == references[ids[0]]["claim_revision"] and
                    row.get("verified_at") == references[ids[0]].get("verified_at"), "aggregate authority/source contradiction")
            require(row.get("freshness") == _freshness([references[cid] for cid in ids]), "freshness contradicts verification evidence")
            for cid in ids:
                evidence = references[cid]
                binding = _binding_revision({**evidence, "revision": evidence["claim_revision"]})
                require(binding is None or binding == revision, "current code claim has wrong revision")
                require(all(_binding_revision(source) in (None, revision) for source in evidence.get("derived_from_sources", [])), "derived code claim has wrong revision")
        else:
            allowed = {"claim_id", "key", "scope", "type", "state", "value", "source", "revision", "created_at",
                       "verified_at", "notes", "supersedes", "superseded_by", "stale_reason", "live_value",
                       "verification_status", "live_verification", "derived_from_ids", "derived_from_sources"}
            require(set(row) <= allowed, "unknown claim row fields")
        return row["key"], row["scope"]

    current_pairs, current_ids = set(), set()
    for row in cs["current_by_scope"]:
        pair = check_row(row, True)
        require(row["type"] in CURRENT_ELIGIBLE and row.get("state", "ACTIVE") == "ACTIVE", "non-current claim promoted")
        require(pair not in current_pairs, "duplicate current key/scope")
        current_pairs.add(pair)
        current_ids.update(row["claim_ids"])
    projected = _current_projection(cs["current_by_scope"], pack["known_conflicts"], pack["verification_unavailable"])
    require(cs["current"] == projected, "current projection loses or invents a scope")
    excluded_ids = set()
    for section, ctype in SECTION_TYPES.items():
        if ctype in CURRENT_ELIGIBLE:
            require(pack[section] == [row for row in cs["current_by_scope"] if row["type"] == ctype], f"{section} contradicts current")
        else:
            for row in pack[section]:
                check_row(row)
                require(row["type"] == ctype and row.get("state") == "ACTIVE", f"wrong authority in {section}")
                require(row["claim_id"] not in current_ids | excluded_ids, "non-current claim duplicated/promoted")
                excluded_ids.add(row["claim_id"])
    for row in pack["known_stale_sources"]:
        check_row(row)
        require(row.get("state") in ("STALE", "SUPERSEDED"), "invalid stale state")
        require(row["claim_id"] not in current_ids | excluded_ids, "stale claim promoted/duplicated")
        if row["state"] == "SUPERSEDED":
            replacement_ids = row.get("superseded_by")
            require(isinstance(replacement_ids, list) and replacement_ids and len(replacement_ids) == len(set(replacement_ids)),
                    "superseded claim lacks replacement references")
            for cid in replacement_ids:
                require(cid in references and row["claim_id"] in references[cid].get("supersedes", []) and
                        row["key"] == references[cid]["key"], "superseded claim lacks a matching replacement edge")
        else:
            require(isinstance(row.get("stale_reason"), str) and bool(row["stale_reason"]), "stale claim lacks a reason")
        excluded_ids.add(row["claim_id"])
    conflict_pairs = set()
    for conflict in pack["known_conflicts"]:
        require(isinstance(conflict, dict) and conflict.get("status") == "CONFLICT" and conflict.get("resolution") == "HUMAN_REQUIRED", "conflict must require human resolution")
        require(set(conflict) <= {"key", "scope", "status", "resolution", "claims", "reason"}, "unknown conflict fields")
        pair = (conflict.get("key"), conflict.get("scope"))
        require(pair not in current_pairs and pair not in conflict_pairs, "conflict promoted/duplicated")
        conflict_pairs.add(pair)
        rows = conflict.get("claims")
        invalid_graph = conflict.get("reason") == "invalid supersedes graph"
        require(isinstance(rows, list) and len(rows) >= (1 if invalid_graph else 2), "conflict missing alternatives")
        values = set()
        for row in rows:
            require(check_row(row) == pair and row["type"] in CURRENT_ELIGIBLE and row.get("state") == "CONFLICTED", "invalid conflicted claim")
            require(row["claim_id"] not in current_ids | excluded_ids, "conflicted claim promoted/duplicated")
            excluded_ids.add(row["claim_id"])
            values.add(_canonical(row["value"]))
        if invalid_graph:
            require(any(problem.get("resolution") == "HUMAN_REQUIRED" and
                        (problem.get("claim_id") in {row["claim_id"] for row in rows} or
                         set(problem.get("claim_ids", [])) & {row["claim_id"] for row in rows})
                        for problem in pack["registry_problems"] if isinstance(problem, dict)), "invalid graph lacks diagnostic evidence")
        else:
            require(len(values) >= 2, "conflict alternatives do not differ")
    for item in pack["verification_unavailable"]:
        require(isinstance(item, dict) and set(item) == {"key", "scope", "claim_id", "source", "reason"} and
                isinstance(item["reason"], str) and bool(item["reason"]), "invalid unavailable record")
        require(item["claim_id"] not in current_ids, "unavailable verification promoted")
        require(_relevant(item["key"], domains), "unrelated verification record")
        require(item["claim_id"] in references and all(item[field] == references[item["claim_id"]][field]
                for field in ("key", "scope", "source")), "unavailable record lacks matching evidence")
    require(all(isinstance(item, dict) and isinstance(item.get("kind"), str) and isinstance(item.get("detail"), str)
                for item in pack["registry_problems"]), "invalid registry problem")
    expected_counts = {"current": len(cs["current_by_scope"]), "conflicts": len(pack["known_conflicts"]),
                       "stale": len(pack["known_stale_sources"]), "proposals": len(pack["proposals"]),
                       "research": len(pack["research_notes"]), "historical": len(pack["historical_sources"])}
    require(cs["counts"] == expected_counts and all(type(n) is int for n in cs["counts"].values()), "counts contradict sections")
    require(used == set(references), "orphan evidence or missing section")
    local_state = {"current": cs["current"], "current_by_scope": cs["current_by_scope"], "conflicts": pack["known_conflicts"],
                   "stale": pack["known_stale_sources"], "proposals": pack["proposals"], "research": pack["research_notes"],
                   "historical": pack["historical_sources"], "verification_unavailable": pack["verification_unavailable"]}
    for rule in build_do_not_assume(local_state):
        if " stale/superseded claims exist" in rule or " unresolved conflicts exist" in rule:
            require(any(rule.split(" ", 1)[1] in existing for existing in pack["do_not_assume"]), "missing authority warning")
        else:
            require(rule in pack["do_not_assume"], "missing authority warning")
    integrity = pack["integrity"]
    require(isinstance(integrity, dict) and set(integrity) == {"algorithm", "digest", "guarantee"} and
            integrity["algorithm"] == "sha256" and integrity["guarantee"] == "structural_consistency_only", "invalid integrity metadata")
    try:
        digest = context_pack_digest(pack)
    except (TypeError, ValueError) as exc:
        raise ContextPackValidationError("pack is not finite JSON") from exc
    require(integrity["digest"] == digest, "context pack checksum mismatch")
    return pack
