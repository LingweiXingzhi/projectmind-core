# S01-S30 ACCEPTANCE MATRIX (canonical, two-round stable, V-01 honest)

RESULT: 30/30 PASS | categories: PASS=30 | two-round stable: True
HEAD: acd81bc3c43491cd14199cef11cf89e16668ba82

## S01 — PASS
- ORACLE: real NODE_ADD exactly for uncovered path with eligible declarations
- CONTRACT: plan §8 S01/A01 + X19
- DEPS: FIXTURE facts + REAL git
- INPUT_HASH: 1035d8630f693c86
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S02 — PASS
- ORACLE: real RELATION_ADD incl. unchanged-declarations X01
- CONTRACT: plan §8 S02/A02 + X01
- DEPS: REAL git + REAL B
- INPUT_HASH: 21da3368a742573c
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S03 — PASS
- ORACLE: relation removal: last cross-domain import gone; multi-source residual; churn stays silent
- CONTRACT: plan §8 S03/A03 + X11/X13
- DEPS: REAL git
- INPUT_HASH: 10d62d15d05a86c7
- NOTES: C-01: multi-target residual proof bound
- EVIDENCE: 9 passed, 0 skipped, 0 failed of 9 mapped

## S04 — PASS
- ORACLE: rename/move → IMPLEMENTATION_LINK_CHANGE, never NODE_ADD; subdirectory variant
- CONTRACT: plan §8 S04/A04
- DEPS: FIXTURE
- INPUT_HASH: dc27d7f1d9504e11
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S05 — PASS
- ORACLE: node removal: all evidence gone; partial retention → no candidate
- CONTRACT: plan §8 S05/A05
- DEPS: FIXTURE + MOCK tree
- INPUT_HASH: 8df47196a9f1f595
- NOTES: 
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S06 — PASS
- ORACLE: responsibility change: entryPoint declaration gone, no first-symbol pick
- CONTRACT: plan §8 S06/A06
- DEPS: REAL B (installed collector)
- INPUT_HASH: 8f4644c9191ed716
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S07 — PASS
- ORACLE: comment-only change: zero strong proposals with reason
- CONTRACT: plan §8 S07/A07 + X20
- DEPS: FIXTURE
- INPUT_HASH: 9fca63927682edd9
- NOTES: 
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S08 — PASS
- ORACLE: formatting-only (line/quote drift): zero proposals
- CONTRACT: plan §8 S08/A08
- DEPS: FIXTURE
- INPUT_HASH: 87a34d15a944f613
- NOTES: closed P06
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S09 — PASS
- ORACLE: helper-only change: no NODE_ADD / strong proposal
- CONTRACT: plan §8 S09/A09 + F10
- DEPS: FIXTURE
- INPUT_HASH: 15907ca42bd2f29a
- NOTES: 
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S10 — PASS
- ORACLE: internal class added: no NODE_ADD
- CONTRACT: plan §8 S10/A10 + F9
- DEPS: FIXTURE
- INPUT_HASH: 5f6c4a48298ea4dc
- NOTES: 
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S11 — PASS
- ORACLE: docstring import text is never a relation; string/comment included
- CONTRACT: plan §8 S11/A11 + X03/X12
- DEPS: REAL git
- INPUT_HASH: 547870203c0e6d9f
- NOTES: 
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S12 — PASS
- ORACLE: test/generated noise → no business architecture candidates
- CONTRACT: plan §8 S12/A12
- DEPS: FIXTURE
- INPUT_HASH: f7306af850728428
- NOTES: closed P06
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S13 — PASS
- ORACLE: B skipped source → HUMAN_REQUIRED; no channel uses it; normal sources work
- CONTRACT: plan §8 S13/A13 + X04/X21
- DEPS: REAL B skipped semantics
- INPUT_HASH: af4ffd8fe86569ff
- NOTES: C-02: full evidence-domain eligibility gate bound
- EVIDENCE: 6 passed, 0 skipped, 0 failed of 6 mapped

## S14 — PASS
- ORACLE: B mismatch rejected on all paths; same-revision/empty diff no bypass
- CONTRACT: plan §8 S14/A14 + X06
- DEPS: REAL B mismatch + supplied fixtures
- INPUT_HASH: b12f65ed015b8f8e
- NOTES: 
- EVIDENCE: 6 passed, 0 skipped, 0 failed of 6 mapped

## S15 — PASS
- ORACLE: B unavailable → honest degraded; B-free channels continue; no fabricated facts
- CONTRACT: plan §8 S15/A15
- DEPS: REAL absence + REAL exception
- INPUT_HASH: 8ecc54427f69e52c
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S16 — PASS
- ORACLE: stale map: pre-base deletion candidate; read-unknown ≠ absent; base==target zero
- CONTRACT: plan §8 S16/A16-valid-map + F11/F15
- DEPS: FIXTURE + MOCK tree
- INPUT_HASH: 4bf91d028534ca49
- NOTES: 
- EVIDENCE: 3 passed, 0 skipped, 0 failed of 3 mapped

## S17 — PASS
- ORACLE: ambiguous multi-owner mapping → low confidence + uncertainty, no arbitrary pick
- CONTRACT: plan §8 S17/A17
- DEPS: FIXTURE
- INPUT_HASH: 81854bfa17a83c3e
- NOTES: rename + relation variants
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S18 — PASS
- ORACLE: missing evidence: added file without B entries → unresolved UNKNOWN
- CONTRACT: plan §8 S18/A18
- DEPS: FIXTURE
- INPUT_HASH: 670614d8604b73a2
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S19 — PASS
- ORACLE: relevant CA conflict suppresses touching candidates only; word boundary
- CONTRACT: plan §8 S19/A19 + X14/X15/X18
- DEPS: REAL CA pack
- INPUT_HASH: 47eefcec00cc0096
- NOTES: C-03: subject-aware T3 bound
- EVIDENCE: 10 passed, 0 skipped, 0 failed of 10 mapped

## S20 — PASS
- ORACLE: non-current partitions (stale/proposal/research/history) never read
- CONTRACT: plan §8 S20/A20
- DEPS: REAL CA stale semantics
- INPUT_HASH: 80addf9bbca5a829
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S21 — PASS
- ORACLE: multi-scope same key both in selection layer
- CONTRACT: plan §8 S21/A21
- DEPS: REAL CA pack
- INPUT_HASH: f416303a35a1f63c
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S22 — PASS
- ORACLE: verified_fields per field; unverified fields support nothing
- CONTRACT: plan §8 S22/A22
- DEPS: MOCK validator (field map contract)
- INPUT_HASH: c300613296fd608e
- NOTES: live verifiers = recorded limit
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S23 — PASS
- ORACLE: unavailable keys explicit UNKNOWN, never faked bad-pack
- CONTRACT: plan §8 S23/A23
- DEPS: MOCK validator
- INPUT_HASH: 7c537661d2e82bc9
- NOTES: real unavailable rows need network verifiers (recorded)
- EVIDENCE: 1 passed, 0 skipped, 0 failed of 1 mapped

## S24 — PASS
- ORACLE: invalid pack → whole-pack discard; independent candidates survive
- CONTRACT: plan §8 S24/A24
- DEPS: REAL CA digest tamper
- INPUT_HASH: 18e943416f48e3df
- NOTES: 
- EVIDENCE: 2 passed, 0 skipped, 0 failed of 2 mapped

## S25 — PASS
- ORACLE: coherent poison never enters evidence/rationale (also with proposals present)
- CONTRACT: plan §8 S25/A25 + X05/X16/X17
- DEPS: REAL CA pack poison
- INPUT_HASH: c5ae2f32f53f3646
- NOTES: 
- EVIDENCE: 4 passed, 0 skipped, 0 failed of 4 mapped

## S26 — PASS
- ORACLE: determinism: byte-identical repeats; order-insensitive IDs
- CONTRACT: plan §8 S26/A26 + X09
- DEPS: REAL git + REAL B history
- INPUT_HASH: 6a4c26f7ad94c2b7
- NOTES: 
- EVIDENCE: 4 passed, 0 skipped, 0 failed of 4 mapped

## S27 — PASS
- ORACLE: malformed inputs controlled rejection incl. valid-context malformed map
- CONTRACT: plan §8 S27/A27
- DEPS: FIXTURE
- INPUT_HASH: 74f18d290ec32ee0
- NOTES: closed P06
- EVIDENCE: 3 passed, 0 skipped, 0 failed of 3 mapped

## S28 — PASS
- ORACLE: path abuse rejected across changed/oldPath/map evidence/entryPoint sources
- CONTRACT: plan §8 S28/A28
- DEPS: FIXTURE
- INPUT_HASH: 2d4cc81125317e2a
- NOTES: 
- EVIDENCE: 5 passed, 0 skipped, 0 failed of 5 mapped

## S29 — PASS
- ORACLE: no formal-map write: file hash unchanged; no position; PROPOSED lifecycle
- CONTRACT: plan §8 S29/A29
- DEPS: REAL formal map hash
- INPUT_HASH: 2f4d8ca75076f8ef
- NOTES: 
- EVIDENCE: 3 passed, 0 skipped, 0 failed of 3 mapped

## S30 — PASS
- ORACLE: host isolation: runtime BaseException contained, all routes survive
- CONTRACT: plan §8 S30/A30
- DEPS: REAL Core A30 runtime tests (bound by name)
- INPUT_HASH: 0618f5fc92e44174
- NOTES: runs the actual test_a30_* behavior tests in-runtime when present, else in the A30 fix worktree (owner delivery); zero discovered A30 tests → NOT_RUN
- EVIDENCE: 4 A30 runtime test(s) run in A30 fix worktree projectmind-core-a30 (external owner delivery): ExtensionHttpTests.test_a30_d_extension_routes_survive_runtime_system_exit=ok, ExtensionHttpTests.test_a30_host_run_contract_direct=ok, ExtensionHttpTests.test_a30_runtime_base_exception_family_is_contained=ok, ExtensionHttpTests.test_a30_runtime_system_exit_is_contained_as_extension_error=ok

