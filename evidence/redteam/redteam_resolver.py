"""Independent red-team probes for Context Authority resolver/pack.

New angles NOT covered by the existing 172 tests (a01-a55, p01-p60, t/f):
  RT-A  multi-scope ACTIVE different values: does `current` silently omit the key,
        and does do_not_assume warn about it?
  RT-B  do_not_assume counts: whole-registry counts vs domain-filtered sections
  RT-C  code_facts partial verification: extra value fields pass through unverified
  RT-D  5000-node supersedes CYCLE (recursion/time)
  RT-E  5000 claims + one conflict (counts + HUMAN_REQUIRED + timing)
  RT-F  empty registry end-to-end pack build
  RT-G  verifier raising SystemExit / KeyboardInterrupt (BaseException containment)
  RT-H  live stale + two registered values -> three-way conflict, all preserved?
  RT-I  coherent forgery: inflated count numbers in do_not_assume pass validation?
  RT-J  duplicate supersedes target listed twice
  RT-K  CONTRACT vs HUMAN_DECISION different values same key/scope -> conflict

Run: python redteam_resolver.py  (from CA worktree root)
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "projectmind-context-authority"
sys.path.insert(0, str(ROOT))

from extensions.context_authority.context_pack import (  # noqa: E402
    build_context_pack, validate_context_pack)
from extensions.context_authority.registry import RegistryProblems  # noqa: E402
from extensions.context_authority.resolver import resolve  # noqa: E402

RESULTS = []


def record(rt_id, name, verdict, detail):
    RESULTS.append({"id": rt_id, "name": name, "verdict": verdict, "detail": detail})
    print(f"[{rt_id}] {name}: {verdict}")
    for line in detail:
        print("      " + line)


def claim(cid, key, value, ctype, *, scope="test", sup=None, source=None, **extra):
    if not cid.startswith("claim-"):
        cid = "claim-rt-" + cid
    if sup:
        sup = ["claim-rt-" + s if not s.startswith("claim-") else s for s in sup]
    row = {"id": cid, "key": key, "value": value, "type": ctype, "scope": scope,
           "source": source or {"kind": "human", "ref": "test"}}
    if sup is not None:
        row["supersedes"] = sup
    row.update(extra)
    return row


def find_rule(rules, needle):
    return [r for r in rules if needle in r]


# ---------------------------------------------------------------- RT-A
def rt_a():
    claims = [
        claim("h1", "team.roles.v1", {"a": "Core", "b": "Code Facts"}, "HUMAN_DECISION", scope="team"),
        claim("h2", "team.roles.v1", {"a": "Integration", "b": "Docs"}, "HUMAN_DECISION", scope="legacy-doc"),
    ]
    state = resolve(claims)
    key_in_current = "team.roles.v1" in state["current"]
    by_scope = len(state["current_by_scope"])
    conflicts = len(state["conflicts"])
    pack = build_context_pack("team roles and responsibilities", str(ROOT),
                              _write_registry(claims), run_verifiers=False)
    warnings = find_rule(pack["do_not_assume"], "team.roles")
    record("RT-A", "multi-scope ACTIVE key vanishes from `current`",
           "CONFIRMED-GAP" if (not key_in_current and by_scope == 2 and conflicts == 0 and not warnings) else "OK",
           [f"current contains key: {key_in_current}",
            f"current_by_scope rows: {by_scope} (both preserved)",
            f"conflicts: {conflicts} (different scopes never conflict)",
            f"do_not_assume rules mentioning the multi-scope key: {len(warnings)}",
            "=> consumer reading only current_state.current silently loses team.roles.v1"])


# ---------------------------------------------------------------- RT-B
def rt_b():
    claims = [
        claim("c1", "contract.a.shape", {"kind": "A"}, "CONTRACT", scope="s"),
        claim("c2", "contract.b.shape", {"kind": "B"}, "CONTRACT", scope="s"),
        claim("h1", "team.roles.v1", {"ok": True}, "HUMAN_DECISION", scope="team"),
    ]
    pack = build_context_pack("map", str(ROOT), _write_registry(claims), run_verifiers=False)
    # task "map" covers team+contract+architecture+implementation+research domains
    stale_rule = [r for r in pack["do_not_assume"] if "stale/superseded claims exist" in r]
    record("RT-B", "do_not_assume counts are whole-registry, sections domain-filtered",
           "CHECK",
           [f"registry: 0 stale, 0 conflicts; pack stale section: {len(pack['known_stale_sources'])}",
            f"stale rule text: {stale_rule}"])


def rt_b2():
    """Forged pack: inflated stale/conflict count numbers in do_not_assume text."""
    claims = [
        claim("c1", "contract.a.shape", {"kind": "A"}, "CONTRACT", scope="s"),
        claim("h1", "team.roles.v1", {"ok": True}, "HUMAN_DECISION", scope="team"),
    ]
    pack = build_context_pack("map", str(ROOT), _write_registry(claims), run_verifiers=False)
    forged = json.loads(json.dumps(pack))
    forged["do_not_assume"] = [
        "99 stale/superseded claims exist - do not use them as current facts",
        "99 unresolved conflicts exist - treat them as HUMAN_REQUIRED, do not pick a side yourself",
    ] + [r for r in pack["do_not_assume"]
         if "stale/superseded claims exist" not in r and "unresolved conflicts exist" not in r]
    # re-sign the forgery with a correct digest
    from extensions.context_authority.context_pack import context_pack_digest
    body = {k: v for k, v in forged.items() if k != "integrity"}
    import hashlib
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    forged["integrity"]["digest"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    try:
        validate_context_pack(forged)
        verdict = "CONFIRMED-GAP"
        detail = ["validator accepted inflated count numbers (99 vs 0)",
                  "count text in do_not_assume is NOT cross-checked against sections"]
    except Exception as exc:
        verdict = "OK"
        detail = [f"validator rejected: {type(exc).__name__}: {str(exc)[:120]}"]
    record("RT-I", "coherent forgery with inflated do_not_assume counts", verdict, detail)


# ---------------------------------------------------------------- RT-C
def rt_c():
    stored = {"status": "PR_OPEN", "pr": 22,
              "head": "a" * 40, "fabricated_field": "UNVERIFIED_CLAIM",
              "unit_count": 686}
    live = {"status": "PR_OPEN", "pr": 22, "head": "a" * 40}

    def verifier(c):
        return {"status": "ok", "value": live, "verified_at": "2026-01-01T00:00:00+00:00",
                "source_kind": "gh_api", "source_ref": "repos/x/pulls/22",
                "verified_fields": ["status", "pr", "head"]}

    claims = [claim("cf1", "implementation.code_facts", stored, "VERIFIED_FACT",
                    scope="repo", source={"kind": "gh_api", "ref": "repos/x/pulls/22"})]
    state = resolve(claims, verifiers={"implementation.code_facts": verifier})
    current = state["current"].get("implementation.code_facts", {})
    value = current.get("value", {})
    fresh = current.get("freshness")
    record("RT-C", "code_facts extra fields pass through unverified",
           "CONFIRMED-BEHAVIOR" if value.get("fabricated_field") == "UNVERIFIED_CLAIM" else "OK",
           [f"current value keys: {sorted(value)}",
            f"fabricated_field in current value: {value.get('fabricated_field')!r}",
            f"freshness: {fresh}",
            f"live_verification.verified_fields: {current.get('live_verification', {}).get('verified_fields')}",
            "=> only status/pr/head are live-verified; remaining fields are registry passthrough"])


# ---------------------------------------------------------------- RT-D
def rt_d():
    n = 5000
    claims = []
    for i in range(n):
        nxt = (i + 1) % n
        claims.append(claim(f"claim-c{i:04d}", "team.roles.v1", {"gen": i}, "HUMAN_DECISION",
                            scope="team", sup=[f"claim-c{nxt:04d}"]))
    t0 = time.time()
    try:
        state = resolve(claims)
        dt = time.time() - t0
        kinds = {p["kind"] for p in state["registry_problems"]}
        record("RT-D", "5000-node supersedes cycle",
               "OK" if ("CYCLIC_SUPERSEDES" in kinds and dt < 30 and len(state["conflicts"]) == 1) else "FAIL",
               [f"time: {dt:.2f}s", f"problems: {sorted(kinds)}",
                f"conflicts: {len(state['conflicts'])}, "
                f"resolution: {state['conflicts'][0]['resolution'] if state['conflicts'] else None}"])
    except Exception as exc:
        record("RT-D", "5000-node supersedes cycle", "FAIL",
               [f"raised {type(exc).__name__}: {str(exc)[:160]}"])


# ---------------------------------------------------------------- RT-E
def rt_e():
    claims = [claim(f"claim-e{i:04d}", f"team.key{i:04d}.x", {"v": i}, "HUMAN_DECISION", scope="team")
              for i in range(4999)]
    claims.append(claim("claim-x1", "team.conflict.key", {"v": "A"}, "HUMAN_DECISION", scope="team"))
    claims.append(claim("claim-x2", "team.conflict.key", {"v": "B"}, "HUMAN_DECISION", scope="team"))
    t0 = time.time()
    state = resolve(claims)
    dt = time.time() - t0
    conflict = state["conflicts"][0] if state["conflicts"] else None
    ok = (state["counts"]["current"] == 5000 and len(state["conflicts"]) == 1
          and conflict and conflict["resolution"] == "HUMAN_REQUIRED")
    record("RT-E", "5000 claims + one conflict",
           "OK" if ok else "FAIL",
           [f"time: {dt:.2f}s", f"counts: {state['counts']}",
            f"conflict claims preserved: {sorted(c['claim_id'] for c in conflict['claims']) if conflict else None}"])


# ---------------------------------------------------------------- RT-F
def rt_f():
    pack = build_context_pack("map", str(ROOT), _write_registry([]), run_verifiers=False)
    try:
        validate_context_pack(pack)
        ok = True
    except Exception as exc:
        ok = False
        print(exc)
    record("RT-F", "empty registry end-to-end pack build + validate",
           "OK" if ok else "FAIL",
           [f"current keys: {len(pack['current_state']['current'])}",
            f"do_not_assume rules: {len(pack['do_not_assume'])}",
            f"digest: {pack['integrity']['digest'][:24]}..."])


# ---------------------------------------------------------------- RT-G
def rt_g():
    def evil_verifier(c):
        raise SystemExit(1)

    claims = [claim("v1", "implementation.main_head", {"sha": "a" * 40}, "VERIFIED_FACT",
                    scope="repo", source={"kind": "repo", "ref": "x", "revision": "a" * 40})]
    try:
        state = resolve(claims, verifiers={"implementation.main_head": evil_verifier})
        record("RT-G", "verifier raising SystemExit", "LEAK",
               ["SystemExit escaped resolve()", f"current keys: {list(state['current'])}"])
    except SystemExit:
        record("RT-G", "verifier raising SystemExit", "LEAK",
               ["SystemExit propagated out of resolve() (caught Exception only in _verify)"])
    except Exception as exc:
        record("RT-G", "verifier raising SystemExit", "CONTAINED",
               [f"converted to {type(exc).__name__}"])
    # through the HTTP layer
    from extension_host import ExtensionHost, ExtensionContext
    host = ExtensionHost(Path("extensions"), ExtensionContext(ROOT, ROOT / "data" / "project-map.json", lambda: {}, lambda a, b: {}))
    try:
        host.run("context_authority", "POST", {"action": "resolve_state"})
        record("RT-G2", "SystemExit containment at extension host runtime", "NOTE",
               ["built-in verifiers never raise SystemExit; runtime path catches Exception only"])
    except SystemExit:
        record("RT-G2", "SystemExit containment at extension host runtime", "LEAK",
               ["SystemExit propagated through host.run()"])


# ---------------------------------------------------------------- RT-H
def rt_h():
    def live_old(c):
        return {"status": "unavailable", "reason": "simulated outage"}

    claims = [
        claim("r1", "implementation.pr_9_head", {"status": "PR_OPEN", "pr": 9, "head": "1" * 40},
              "VERIFIED_FACT", scope="repo", source={"kind": "gh_api", "ref": "p9"}),
        claim("r2", "implementation.pr_9_head", {"status": "MERGED", "pr": 9, "head": "2" * 40},
              "VERIFIED_FACT", scope="repo", source={"kind": "gh_api", "ref": "p9b"}),
        claim("r3", "implementation.pr_9_head", {"status": "CLOSED", "pr": 9, "head": "3" * 40},
              "VERIFIED_FACT", scope="repo", source={"kind": "gh_api", "ref": "p9c"}),
    ]
    state = resolve(claims, verifiers={"implementation.pr_9_head": live_old})
    conflicts = state["conflicts"]
    record("RT-H", "verifier outage + three registered values",
           "OK" if (len(conflicts) == 1 and len(conflicts[0]["claims"]) == 3
                    and conflicts[0]["resolution"] == "HUMAN_REQUIRED") else "FAIL",
           [f"conflicts: {len(conflicts)}",
            f"conflicted claim ids: {sorted(c['claim_id'] for c in conflicts[0]['claims']) if conflicts else None}",
            f"values preserved: {len({json.dumps(c['value'], sort_keys=True) for c in conflicts[0]['claims']}) if conflicts else 0}/3 distinct"])


# ---------------------------------------------------------------- RT-J
def rt_j():
    claims = [
        claim("j1", "team.roles.v1", {"old": True}, "HUMAN_DECISION", scope="team"),
        claim("j2", "team.roles.v1", {"new": True}, "HUMAN_DECISION", scope="team",
              sup=["j1", "j1"]),
    ]
    state = resolve(claims)
    dup_edge = [p for p in state["registry_problems"] if "DUPLICATE" in p.get("kind", "")]
    ok = (state["counts"]["current"] == 1 and not dup_edge
          and state["current"]["team.roles.v1"]["value"] == {"new": True}
          and state["current"]["team.roles.v1"]["claim_ids"] == ["j2"])
    record("RT-J", "duplicate supersedes target handled once",
           "OK" if ok else "FAIL",
           [f"current value: {state['current'].get('team.roles.v1', {}).get('value')}",
            f"problems: {[p['kind'] for p in state['registry_problems']] or 'none'}"])


# ---------------------------------------------------------------- RT-K
def rt_k():
    claims = [
        claim("k1", "contract.api.shape", {"v": "from-contract"}, "CONTRACT", scope="s"),
        claim("k2", "contract.api.shape", {"v": "from-human"}, "HUMAN_DECISION", scope="s"),
    ]
    state = resolve(claims)
    c = state["conflicts"]
    record("RT-K", "CONTRACT vs HUMAN_DECISION different values",
           "OK" if (len(c) == 1 and c[0]["resolution"] == "HUMAN_REQUIRED"
                    and {x["claim_id"] for x in c[0]["claims"]} == {"k1", "k2"}) else "FAIL",
           [f"conflict resolution: {c[0]['resolution'] if c else 'NONE'}",
            "=> no type-majority winner across equal-legitimacy types"])


def _write_registry(claims):
    d = Path(tempfile.mkdtemp())
    p = d / "claims.jsonl"
    p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims), encoding="utf-8")
    return p


if __name__ == "__main__":
    rt_a(); rt_b(); rt_b2(); rt_c(); rt_d(); rt_e(); rt_f(); rt_g(); rt_h(); rt_j(); rt_k()
    out = Path(__file__).parent / "redteam_results.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
