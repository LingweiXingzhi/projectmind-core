"""build_context_pack(task, revision=None) -> Canonical Context Pack.

Deterministic: same registry + same task + same verification results
=> same pack. Every item carries claim_id + source; nothing is a summary
without provenance.
"""
from __future__ import annotations

from extensions.context_authority.registry import RegistryProblems, load_registry
from extensions.context_authority.resolver import resolve
from extensions.context_authority.verifiers import build_default_verifiers

# deterministic task->domain routing; unknown tasks default to "all"
TASK_KEYWORDS = {
    "role": ("team",), "分工": ("team",), "职责": ("team",), "responsib": ("team",),
    "code facts": ("implementation", "contract"), "pr": ("implementation",),
    "merge": ("implementation",), "revision": ("implementation",),
    "head": ("implementation",), "contract": ("contract",), "接口": ("contract",),
    "map": ("architecture", "implementation"), "架构": ("architecture",),
    "architecture": ("architecture",), "proposal": ("architecture",),
    "research": ("research",), "性能": ("research",), "performance": ("research",),
}


def _domains_for(task: str) -> tuple[str, ...] | None:
    low = (task or "").lower()
    hits: list[str] = []
    for kw, domains in TASK_KEYWORDS.items():
        if kw in low:
            hits.extend(domains)
    return tuple(dict.fromkeys(hits)) or None


def _relevant(key: str, domains: tuple[str, ...] | None) -> bool:
    return domains is None or key.split(".", 1)[0] in domains


def build_do_not_assume(state: dict) -> list[str]:
    rules = []
    impl = state["current"].get("implementation.code_facts", {})
    if impl.get("value", {}).get("status") == "PR_OPEN":
        rules.append(f"PR #{impl['value']['pr']} is OPEN - OPEN does not mean merged; "
                     "its branch content is not main content")
    if state["proposals"]:
        rules.append("PROPOSAL entries exist - a proposal is not accepted architecture")
    if state["research"]:
        rules.append("RESEARCH entries exist - research findings and suggestions "
                     "are not contract and must not be restated as requirements")
    if state["historical"]:
        rules.append("HISTORICAL material exists - historical reports/mappings "
                     "describe a past state, never the current one")
    if state["stale"]:
        rules.append(f"{len(state['stale'])} stale/superseded claims exist - "
                     "do not use them as current facts")
    if state["conflicts"]:
        rules.append(f"{len(state['conflicts'])} unresolved conflicts exist - "
                     "treat them as HUMAN_REQUIRED, do not pick a side yourself")
    rules.append("CodeFacts provides declarations (def/class, path, line) only - "
                 "no dependency graph, signatures, or entry points")
    rules.append("the curated map currently has no version identity - "
                 "Snapshot.revision never proves the map applies to that commit")
    return rules


def build_context_pack(task: str, repo_root: str, registry_path,
                       revision: str | None = None,
                       run_verifiers: bool = True) -> dict:
    problems = RegistryProblems()
    claims = load_registry(registry_path, problems)
    verifiers = build_default_verifiers(repo_root) if run_verifiers else {}
    state = resolve(claims, verifiers=verifiers, problems=problems,
                    run_verifiers=run_verifiers)
    domains = _domains_for(task)

    current = {k: v for k, v in state["current"].items()
               if _relevant(k, domains)}
    human_decisions = [
        {"key": k, **v} for k, v in sorted(state["current"].items())
        if v["type"] == "HUMAN_DECISION" and _relevant(k, domains)]
    verified_facts = [
        {"key": k, **v} for k, v in sorted(state["current"].items())
        if v["type"] == "VERIFIED_FACT" and _relevant(k, domains)]
    relevant_contracts = [
        {"key": k, **v} for k, v in sorted(state["current"].items())
        if v["type"] == "CONTRACT" and _relevant(k, domains)]
    conflicts = [c for c in state["conflicts"] if _relevant(c["key"], domains)]
    stale = [s for s in state["stale"] if _relevant(s["key"], domains)]
    proposals = [p for p in state["proposals"] if _relevant(p["key"], domains)]
    research = [r for r in state["research"] if _relevant(r["key"], domains)]

    pack = {
        "task": task,
        "task_domains": list(domains) if domains else "all",
        "project_revision": revision,
        "current_state": {
            "current": current,
            "counts": state["counts"],
            "registry_hash": state["registry_hash"],
        },
        "relevant_contracts": relevant_contracts,
        "human_decisions": human_decisions,
        "verified_facts": verified_facts,
        "known_conflicts": conflicts,
        "known_stale_sources": stale,
        "proposals": proposals,
        "research_notes": research,
        "do_not_assume": build_do_not_assume(state),
        "verification_unavailable": state["verification_unavailable"],
        "registry_problems": state["registry_problems"],
        "evidence": [],
    }
    seen: set[str] = set()
    for item in (human_decisions + verified_facts + relevant_contracts):
        for cid in item.get("claim_ids", []):
            if cid not in seen:
                seen.add(cid)
                pack["evidence"].append({
                    "claim_id": cid, "source": item.get("source"),
                    "revision": item.get("revision"),
                })
    for conflict in conflicts:
        for row in conflict["claims"]:
            cid = row.get("claim_id")
            if cid not in seen:
                seen.add(cid)
                pack["evidence"].append({
                    "claim_id": cid, "source": row.get("source"),
                    "revision": row.get("revision"),
                })
    return pack
