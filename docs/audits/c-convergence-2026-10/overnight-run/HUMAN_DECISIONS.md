# HUMAN DECISIONS REQUIRED — overnight C convergence run (2026-10-05)

Recorded per master instruction §29 (P07): semantic ambiguities the contract
does not define are NOT resolved by implementation policy. Conservative
behavior is in place for each; none blocks unrelated positive proposals.

## D1 — HUMAN_DECISION_REQUIRED_EVIDENCE_DOMAIN (highest risk, R5)
Question: does a map node's `evidence path` mean (A) a supporting reference,
or (B) the node's implementation/responsibility domain?
Impact: the RELATION_REMOVE_CANDIDATE proof domain ("all .py files of the
source node's evidence domain free of imports into the target domain") and
the NODE_REMOVE_CANDIDATE proof domain ("all evidence paths absent at
target") both assume (B). If humans hang reference-only paths in evidence,
removal proofs are computed over the wrong file set.
Current behavior: destructive-style candidates are low confidence, carry
"map may be stale rather than the node meaningless" uncertainty, require an
existing map edge (relations) or full evidence-path absence (nodes), and
never block positive proposals.
Decision needed from: TEAM C owner (+ map maintainers).

## D2 — HUMAN_DECISION_REQUIRED_MAP_NODE_FIELDS
Question: does Core's map schema REQUIRE title/summary/entryPoint per node?
C's intake currently demands only id + evidence (structure), tolerating
missing title. Found while closing S27 (valid-context malformed payload).
Impact: intake strictness vs. real-map rejection risk (R11).
Decision needed from: Core owner.

## D3 — HUMAN_DECISION_REQUIRED_STATUS_VOCABULARY (R10)
Question: the convergence handler's honest status vocabulary
(degraded / empty / rule_candidate) is self-created. Old consumers may
branch on other values.
Current behavior: status is never ai_candidate without a real model run
(X07). K03 candidates projection is gated.
Decision needed from: TEAM owner + DevKit/frontend consumers.

## D4 — HUMAN_DECISION_REQUIRED_GREENFIELD_MAP (R16)
Question: what is C's product behavior for a project with NO map yet?
Currently: request rejected with an explicit message ("current_map 缺失…"),
X10 empty-map remains withdrawn.
Decision needed from: TEAM owner (product flow).

## D5 — HUMAN_DECISION_REQUIRED_B_SHAPE_TOLERANCE
Question: B facts shape tolerance boundary — "container malformed = 400,
entry malformed = lenient" is C's defensible policy, not contract text.
Impact: if B owner considers entry shape contractual, C's leniency masks
drift.
Decision needed from: B owner.

## D6 — HUMAN_DECISION_REQUIRED_T2_CONFIDENCE_UPLIFT
Question: may a CA verified field lift a proposal's confidence
(T2 "strengthen an already independently-supported proposal")?
Current behavior: T2 renders per-field verification labels in context lines
only; confidence is never changed by CA.
Decision needed from: TEAM owner (+ CA owner).

## Discovery note (no decision required, informational)
- Real CA revision-binding semantics: only implementation.* VERIFIED_FACT
  claims bind to a project revision (human decisions are never
  revision-stale). C's stale-partition handling aligns with the real
  resolver; mock-era assumptions about freshness-based staleness were
  corrected in the real-CA integration tests.
