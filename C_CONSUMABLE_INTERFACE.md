# C-facing Context Authority interface v0.1

STATUS: validation verdict is recorded in CONTEXT_AUTHORITY_FINAL_REPORT.md.
This freezes the review branch's consumer contract, not formal team approval.

## FROZEN_FOR_C_V0_1

| Field/interface | C may rely on | Required boundary |
|---|---|---|
| schema_version | `"0.1"`; reject other versions | Legacy unversioned packs require regeneration |
| project_revision | Full lowercase Git commit SHA resolved in requested repo | Compare with C's independently pinned revision; does not version the map |
| current_state.current_by_scope | Current-eligible rows keyed by `(key,scope)` | Select intended scope; empty/missing means UNKNOWN |
| current_state.current | Convenience map for unambiguous keys only | Never infer a scope winner from absence or key order |
| verified_facts / human_decisions / relevant_contracts | Typed projections of scoped current | Fact freshness and human/source authority need evidence checks |
| known_conflicts | Explicit HUMAN_REQUIRED; no automatic winner | Invalid replacement graph may have one/equal alternatives plus diagnostic |
| known_stale_sources | STALE/SUPERSEDED values and original provenance | Never use as current; unavailable facts retained here |
| proposals / research_notes / historical_sources | Non-current authority classes | Candidate or historical content cannot become confirmed architecture |
| verification_unavailable / registry_problems | Failed checks or invalid graph | Stop dependent action, resolve through evidence/human review |
| do_not_assume | Consumer caveats | Meaning is binding; exact prose/order is provisional |
| evidence | Per-claim identity, type, value, source and revision metadata | Trace every relevant claim to its own exact source, including collapsed IDs |
| current_state.registry_hash / integrity | Deterministic registry hash and unkeyed pack checksum | Structural consistency only; neither authenticates source or truth |
| build_context_pack / validate_context_pack | Python generation + validation | Pass expected_revision; exception means reject pack |
| POST action=context / validate_context | Same semantics through extension route | Host body cap 65,536 bytes; larger validation uses Python callable |

Evidence revision axes: `claim_revision` is an explicit applicability binding;
`source_revision` identifies evidence provenance; `revision` is the effective
evidence locator. An OPEN PR document's revision is not a guarantee that the
contract is implemented on main or the selected code revision. Repo code
claims bound to another commit are demoted from current. `freshness=unverified`
means no live check, `local_reference` means cached origin/main only, and live
verification metadata records the exact read-only endpoint/time.

Several retained legacy `source.ref` labels use `repos/...` shorthand. Use
the exact per-claim `live_verification.source` locator or independently
retrieved original capture, not the shorthand as a literal API URL. The main
check uses this CA worktree's cached ref; CA/Core are linked worktrees of the
same verified origin. That check does not authenticate arbitrary project
identity or prove live GitHub freshness. C must verify its repository identity.

The final expanded live seed pack is **71,822 compact UTF-8 bytes**, exceeding
the host POST cap. Its context request remains small and its response is
readable, but uploading the entire pack to HTTP validate_context exceeds the
cap. For this seed C MUST use the Python validator. The earlier 19-claim
review fixture fit the HTTP cap; that result is historical, not the final size.

## PROVISIONAL

Task keyword/domain routing, current seed key set, UI layout, exact warning
prose, auto-claim IDs, performance bounds, default GitHub project identity,
additional evidence metadata, and future tooling append/review workflow.
Use task `map proposal` for C's full authority/contract/research caveats.
Read source docs/code for details outside the seed; fallback is part of use.

## DO_NOT_DEPEND_ON

Historical report conclusions as today's implementation state; pack-only
absence as proof of absent code; OPEN/MERGEABLE as merge or approval; checksum
as human signature; source revision as map applicability; timestamps as
authority priority; global type priority; keyword routing as semantic search;
claim IDs as a stable business API; snapshots as statements about all future
commits/branches; a cached remote-tracking ref as live GitHub main.

Preflight completion criteria and evidence fallback are in AGENT_BOOTSTRAP.md.
C implementation, main merge, formal Project Model changes, B/D integration
and shared UI integration remain separate human-authorized work.
