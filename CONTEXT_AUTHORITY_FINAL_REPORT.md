# Context Authority final adjudication

STATUS: C_CONSUMABLE_WITH_LIMITS
C_CONSUMABLE: YES_WITH_LIMITS
UNRESOLVED_PRODUCT_BLOCKERS: NONE
PROJECT_MODEL_IMPACT: MINOR — authority/consumer boundary hardening only.

The existing interrupted MVP was continued on `feat/context-authority-mvp`.
Registry, deterministic resolver, verifiers, Current State, Context Pack,
extension API, Inspector and consumer preflight are complete. No C development,
shared UI integration, B/D integration or formal team/model contract change was
performed. Historical MVP report/44-test figures remain original snapshots;
this report supersedes their readiness claims.

## Validation evidence

- Final complete regression: **172/172 PASS in three fresh processes**, identical
  test identities/results. Original32 CA +12 core/host +55 resolver adversarial
  +60 pack adversarial +4 live/seed +9 metrics tests. Exact logs/receipt retained.
- Two fresh independent red-team reviewers exposed resolver and pack defects,
  including initial31 resolver failures/11 errors. Findings→reproduction→minimal
  fix→regression→affected experiment are retained in reviewer reports and
  CONTEXT_AUTHORITY_FINDINGS.md, not replaced by author's PASS assertions.
- Same registry/task/revision/captured verifier outcomes:100 resolves equal,
  reverse registry equal,20 pack builds equal. Captured timestamps/network
  results are held fixed; this does not promise identical live clocks or remote
  state across different calls. Node Inspector injection/text/evidence smoke PASS.
- Frozen twenty-question experiment: Raw60/60 correct; original CA53 correct,
  1 partial,6 uncertain; post-fix fresh CA60/60 correct. Final disagreement0%
  for both, unsupported/stale-as-current0. Conflict detection rate N/A because
  the original truth contains no unresolved-conflict item. All originals kept.
- Independent poisoning review: original6 DETECTED/4 QUESTIONED; hardened10
  CORRECTED_FROM_EVIDENCE, no blind trust or propagated injection. Six attacks
  fail structural validation; four coherent attacks require original evidence.
  Both clean controls accepted correctly. One minor ancillary paraphrase error
  is recorded. Small fixed studies do not establish general safety rates.
- Fifteen development questions in three fresh independent conditions identify
  pack-only gaps. Source fallback is required for9/15; full answers/read logs
  and independent content adjudication are in CONTEXT_PACK_SUFFICIENCY_REPORT.
- Frozen inputs/GT were never rewritten. Active32 fingerprints are verified on
  disk and exact Git blobs; scoped attributes preserve bytes under Windows
  autocrlf. Normalized factual aggregation has meaningful negative/grid tests.

Validated product commit: `3e12fdfebc507ff1755f9f8bcb01e67a0eac14d6`.
The post-fix participant pack is pinned to that commit. Later documentation and
publication commits preserve those bytes. A consumer must generate/check a
pack for its actual independently selected commit, not relabel this fixture.

## C consumption gate

C may consume schema0.1, independently pinned project_revision, scoped current
rows, typed fact/decision/contract projections, conflict/stale/unavailable/graph
diagnostics, noncurrent proposal/research/history classes, do_not_assume and
per-claim evidence through the documented Python/API contract.

Before dependent work: run validate_context_pack(expected_revision=...), select
the intended key/scope, inspect relevant diagnostic lists, retrieve exact
independent source/revision and human authority, compare findings, and retain
UNKNOWN/HUMAN_REQUIRED where unresolved. Stop only dependent actions. The
consumer freeze does not supply team approval or permission to merge/write maps.

## KNOWN_LIMITS

1. A coherent false claim or entirely omitted conflict can pass an unkeyed
   checksum and structural validator. Independent evidence/human review is
   mandatory; a valid pack is not a trusted oracle.
2. Final live seed is71,822 compact UTF-8 bytes, beyond host POST65,536 cap.
   Use the Python validator for this seed. Context request/response still works;
   small packs may use HTTP validation. Shared host was not changed.
3. Main verification is cached `origin/main`, explicitly `local_reference`.
   Live GitHub freshness and repository identity require consumer recheck.
   Default GitHub project is fixed. Some legacy source labels use `repos/...`;
   use exact live metadata/original captures instead of shorthand URLs.
4. C/D negative implementation facts cover only named main/PR21/PR22 trees.
   Other/future branches are UNKNOWN. D candidate PR24/26/27 exists remotely;
   its source/readiness/approval was not inferred or integrated.
5. Keyword task routing, seed keys/IDs, warning prose and extra metadata are
   provisional. No semantic-alias solving, external append lock, multi-project
   provider configuration or broad performance SLA is claimed.
6. Full source docs remain necessary for paths, duplicate declarations, limits,
   skip/error behavior, extension integration and proposed C interface details.
   Formal blank-GET/adoption/baseline decisions remain human-owned.
7. Agents share a model family; isolation was instruction/read-log based, not
   OS-enforced. Small fixed cases are not statistical or causal proof of wider
   superiority. The failed original condition is preserved transparently.

## Publication and human decisions

Published only this own feature branch by normal push and created Draft PR
https://github.com/LingweiXingzhi/projectmind-core/pull/29 to main. Publication
receipt and final branch/PR are recorded in UNATTENDED_FINAL_REPORT.md.
The branch already inherits PR21
documentation; reviewers must account for that dependency. Own commits do not
modify PR21/22's branch/metadata or the formal team standards.

Benchmark remains a non-Git directory with no configured remote.34 selftests
and5 holdout regressions pass, all frozen hashes match, owned upload candidates
are audited, and third-party/team source copies are excluded. Its separate
owner/visibility/URL decision is documented; no repo was created or stuffed
into core. Other assets were inventoried without guessed publication targets.

HUMAN_DECISIONS_REQUIRED.md records formal interface/baseline decisions,
Benchmark remote ownership/visibility and merge permission. No main merge is
authorized until the user explicitly says:
**“已经人工审核通过，可以 merge 到 main。”**

DO NOT MERGE WITHOUT HUMAN REVIEW.
