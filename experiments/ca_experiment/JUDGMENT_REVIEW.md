# Independent judgment review: original frozen 20-question experiment

## Result

All six answer files were independently read and all 120 answers were judged against the unchanged frozen truth and the evidence available in `raw_inputs/` and `context_inputs/`. Agent self-reported uncertainty/conflict flags, author PASS labels, and pre-existing experiment metrics were not used as correctness labels. Repository instructions were read only for work procedure, not as experimental evidence. No live project state, other answers, or product code was used to fill an answer's missing facts.

| Condition | Correct | Partial | Uncertain | Wrong | Strict correctness | Half-partial correctness | Factual disagreement |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raw, A1-A3 | 60 | 0 | 0 | 0 | 60/60 = 100.00% | 60/60 = 100.00% | 0/60 = 0.00% |
| Frozen CA, B1-B3 | 53 | 1 | 6 | 0 | 53/60 = 88.33% | 53.5/60 = 89.17% | 2/60 = 3.33% |

A1, A2, and A3 each have 20 correct answers. B1 has 17 correct, one partial, and two uncertain answers; B2 and B3 each have 18 correct and two uncertain answers. No answer used a stale source as current authority, and no answer introduced an unsupported assumption under the stated definition. CDR is **N/A**, represented by JSON `null`; the original twenty questions do not contain an unresolved-conflict truth label or positive-case denominator.

These results describe this small frozen sample and the particular pack supplied to the CA agents. They do not establish a general advantage of either condition. The CA omissions and the inherited SHA-length defect are substantive findings, even though the CA answers are usually mutually consistent.

## Adjudication rules

- `CORRECT` means the question-relevant factual answer matches the frozen truth or a supported valid alternative. It does not require reproducing every parenthetical detail of an expected-answer sentence when that detail is not requested.
- `PARTIAL` means the answer supplies substantive correct constraints but contains a material factual error or omission. Strict accuracy gives it zero; the separately reported half-partial measure gives it 0.5.
- `UNCERTAIN` means the answer abstains or cannot determine the requested fact. A justified abstention avoids fabrication but is not a correct factual answer when the frozen truth supplies a determinate result.
- Semantic normalization projects the answer onto the fact requested by the question. Supported extra context and prose do not create disagreement. A withheld fact remains unknown; it is never normalized to the correct fact. Different erroneous factual assertions must receive different labels.
- For the open-ended requests q08/q09/q11, supported research, proposal, or stale examples share the respective valid-example label. Choosing different valid examples does not count as inconsistent factual cognition.
- `used_stale_source` is true only when an answer relies on an obsolete source as current authority. Citing an old report to explain its history or reject its current use is false.
- `unsupported_assumption` concerns an assertion without support in that run's permitted input. A wrong claim copied from the pack is a source defect, not an unsupported invention. Correctness still penalizes the wrong claim.

## Ambiguous-answer audit

### q05: C implementation versus absence of implementation evidence

The truth says C is not implemented in the frozen main/PR trees. Both extension lists contain only `extensions/__init__.py` and `extensions/project_summary/`; there is no `extensions/map_proposal`. PR21's collaboration contract additionally states that the B/C/D business extension directories are unimplemented, and its interfaces distinguish proposed business functions from the implemented host.

- A1 explicitly answers not implemented and supplies the two-tree evidence: `CORRECT`.
- A2 starts cautiously but explicitly cites the unimplemented-extension statement and two-tree absence: `CORRECT`.
- A3 says the materials do not show implementation and then explicitly asserts the concrete absence of `map_proposal` in both frozen trees. That bounded factual statement matches the truth's specified implementation scope: `CORRECT`. This does not infer that C can never exist elsewhere.
- B1/B2/B3 only say `suggest_map` is proposed and implementation cannot be confirmed. The pack omits the tree/nonimplementation evidence. A proposal label and no positive evidence cannot establish nonimplementation: all three `UNCERTAIN`, normalized to `C:IMPLEMENTATION_UNKNOWN_PROPOSAL_ONLY` rather than `NOT_IMPLEMENTED`.

This distinction rests on concrete negative evidence, not on a cautious writing style or the agents' own `uncertain` flag.

### q08: valid RESEARCH alternatives

The pack explicitly classifies the cat-file performance finding and batch-streaming suggestion as RESEARCH. B1-B3 correctly identify that entry and preserve its research/estimate status. The raw condition does not include that research artifact. A1-A3 instead choose `B_PR22_BENCHMARK_REPORT.md`, which is an evaluation asset documenting methods, measurements, and limitations, explicitly separated from product authority. That is a supported research/evaluation example for the open-ended question. All six are `CORRECT` and share `RESEARCH:VALID_RESEARCH_OR_EVALUATION_EXAMPLE`.

Reported benchmark figures were checked as claims present in the allowed evaluation report; this judgment does not independently rerun or certify that earlier benchmark.

### q09: proposal example

All six choose the map-source patch. PR21 interfaces place `mapSource`, the digest of actual map bytes, and `confirmedForRevision:null` under PROPOSED. The pack also labels this an active proposal, not implemented or accepted architecture. The raw answers' extra digest/cross-request detail is supported. All six are `CORRECT`, with an equivalent valid-proposal label.

### q11: different valid stale examples

A1-A3 choose the old main collaboration contract's statement that main lacks the product PR chain and that extensions must branch from `feat/19-extension-seams`. PR21 documentation says the Core/Extension Host chain was merged, and the frozen main evaluation records those capabilities. B1-B3 choose the same old document's pre-V1 role mapping, explicitly marked HISTORICAL/SUPERSEDED in the pack. Both are supported stale examples. All six are `CORRECT`, share the valid-stale-example normalization, and have `used_stale_source=false` because they identify rather than adopt the obsolete claim.

### q17: omitted PR21 content

The frozen PR21 title is `docs: confirm V1 ownership and review boundaries`; the three supplied PR21 standard documents provide the V1 roles, boundaries, interface authority, main-baseline distinction, and review procedure changes. A1-A3 describe those substantive documentation changes: `CORRECT`. The question asks what the PR brings, not for an exact file inventory.

The CA pack provides PR21 status/head but no content summary or PR title. B1-B3 correctly notice the omission and abstain, yet do not answer the content question: all `UNCERTAIN`, normalized to `PR21:CONTENT_UNKNOWN_PACK_OMITS_IT`. Missing information is not silently supplied by the judge.

### q19: hexadecimal characters versus bits

The raw delivery contract specifies full lowercase SHA-1/SHA-256 representations: 40 or 64 hexadecimal positions. Its rejection examples and full-SHA examples disambiguate the unit. PR21 interfaces also explicitly describe lowercase hexadecimal length. Forty hexadecimal characters encode 160 bits; 64 encode 256 bits.

- A1-A3 explicitly say 40-position SHA-1 or 64-position SHA-256 and correctly state direct commit/rejection constraints: `CORRECT`.
- B2/B3 use Chinese `40/64 位 SHA` in the full lowercase SHA context. This matches the frozen truth's wording and is reasonably read as representation length, not an explicit bit count: `CORRECT`.
- B1 explicitly says `40/64-bit`. That is a material length-unit error, although lowercase/full/direct-commit and rejection rules are correct: `PARTIAL`. Its normalization records the literal bit assertion and therefore differs from B2/B3 in two of the three CA pairwise comparisons.

The frozen pack itself contains `full 40/64-bit lowercase SHA`, twice, including in relevant contracts. B1's error is directly supported by its supplied pack, so `unsupported_assumption=false`; correctness still penalizes the inaccurate contract representation. Truth and frozen inputs were not edited to cure the defect. If the bit error were graded wholly wrong instead of partial, strict accuracy would remain 88.33% and half-partial accuracy would become 88.33%.

## Complete audit of cross-condition answer differences

Every original question and every run is covered below. A1-A3 and B1-B3 refer to all three answers in each condition; exceptions are explicit. Detail differences that do not change the requested fact are recorded so that wording differences cannot silently become disagreement pairs.

| QID | Raw answers | Frozen CA answers | Independent disposition |
|---|---|---|---|
| q01 | V1 roles plus human-confirmation/main-old-text explanation | Same V1 roles | Equivalent mapping; six correct |
| q02 | OPEN/unmerged plus delivery/main-tree evidence | OPEN/unmerged plus pack boundary | Equivalent not-merged fact; six correct |
| q03 | Existing independent reference prototype, unmerged/unintegrated; A1/A2 give head and explicit OPEN, A3 omits those | Delivered OPEN PR22, waiting review, benchmark figures | Same requested reference-implementation/unmerged-PR status; six correct; extra detail is not disagreement |
| q04 | Dependency/call graph excluded; report marks unsupported | Declaration-only, no dependency graph; B2/B3 mention signatures/entry points | Same dependency exclusion; six correct |
| q05 | Concrete two-tree absence; A1 definitive, A2 explicit document negative, A3 bounded material statement | Proposal-only inability to establish implementation | Raw supported negative versus CA unknown; audited above |
| q06 | Full main SHA; A3 attributes old report's remote-confirmation limitation | Same full main SHA | Same frozen revision; historical attribution does not change SHA; six correct |
| q07 | Full PR22 head | Same full PR22 head | Exact equality; six correct |
| q08 | Benchmark research/evaluation example | Cat-file RESEARCH example | Both valid alternatives; equivalent valid-example labels; six correct |
| q09 | Proposed mapSource patch, digest/consistency details | Same proposed mapSource patch, pack nonacceptance label | Equivalent valid proposal; six correct |
| q10 | C, sometimes scope/input/integration details | C | Same owner; supported extra detail; six correct |
| q11 | Old main baseline/branching excerpt | Old main role-map excerpt | Both valid stale examples; equivalent valid-example labels; six correct |
| q12 | Historical main-only scope versus current independent B prototype | Cannot use old report currently; B3 additionally says direct report coverage unavailable | Same rejection of stale global status; B3's `uncertain=true` does not erase its explicit correct answer; six correct |
| q13 | Five kinds, sometimes class/nesting or old-interface-coverage clarification | Same five kinds | Equal kind set; six correct |
| q14 | One-based keyword line, sometimes duplicate-definition detail | Same one-based keyword line | Equal line semantics; six correct |
| q15 | Candidate baseline; merge/testing does not prove approval; old SOP explanation | Candidate, team_approved=false | Same approval status; historical explanation is not stale usage; six correct |
| q16 | No independent map identity; mapRevision UNKNOWN and proposal detail | No digest/commit pin and unknown applicability | Same absent identity; six correct |
| q17 | V1 ownership/boundary/review documentation changes | Pack lacks content, so abstain | Raw content versus CA unknown; audited above |
| q18 | Full PR21 head | Same full PR21 head | Exact equality; six correct |
| q19 | Full 40/64-position lowercase SHA-1/SHA-256; direct commit; some extra rejection/validation details | Same constraints, except B1 literal bit units | B1 partial, other five correct; distinct incorrect unit label; audited above |
| q20 | No batch contract requirement; cannot locate research origin in raw allowlist | Explicitly RESEARCH and no requirement | Same requested contract denial; raw inability to verify origin does not contradict the denial; six correct |

Thus the material cross-condition factual differences are q05, q17, and B1's q19. Different valid q08/q11 examples do not create inconsistency. Within-condition pairwise disagreement occurs only for CA q19; disagreement is not a substitute for correctness.

## Metrics-script review and verification

`compute_metrics.py` was inspected without alteration. Its aggregation uses independently supplied normalization labels rather than agent prose or grade labels. It rejects an incomplete 6 x 20 grid, duplicates, unexpected run/qid, condition mismatch, invalid verdict, empty normalization, and nonboolean flags. Its current fixed three-run grid makes three pairs per question and 60 pairs per condition correct. Strict accuracy, half-partial accuracy, stale/assumption rates, and null CDR were independently checked with synthetic in-memory probes.

One validation gap was found: `aggregate()` accepts judgment rows with no `reason` field, even though the requested judgment schema requires it. The final 120 real rows all contain nonempty reasons; this gap did not affect the computed results. Semantic adequacy of normalization is necessarily a judge responsibility; the script cannot prove it from strings alone.

Verification performed:

- All 21 hashes in `INPUT_FREEZE.json`, including frozen truth, matched before judgment emission and when the metrics script ran.
- All six answer files contain their complete 20-question grids; judgments contain exactly the required 120 unique run/qid rows.
- In-memory probes confirmed rejection of missing/duplicate judgments, invalid condition/verdict, empty normalization, and nonboolean flags. A controlled changed factual label produced exactly two disagreements; a PARTIAL judgment produced 59/60 strict and 59.5/60 half-partial on the synthetic raw condition. CDR stayed null.
- `python experiments/ca_experiment/compute_metrics.py` completed successfully and wrote `metrics.json` from the independent judgments.

## Limitations and evidence discrepancies

1. The pack is an asymmetric, imperfect information transformation of raw evidence: it adds the explicit cat-file RESEARCH entry but drops C nonimplementation and PR21 content. These results evaluate that supplied pack rather than isolate all possible Context Authority implementations.
2. q03's expected text includes MERGEABLE, but `pr22_status.json` has only number/state/merged/title/head. The allowed evidence supports OPEN/unmerged and the reference prototype, not the PR's actual mergeability value. Missing repetition of that unsupported secondary qualifier was not penalized. The separate head question q07 provides precise revision coverage.
3. q17's expected text mentions five standard documents, while the frozen allowlist supplies three PR21 standard documents and a title, not a full changed-file inventory. The documented substantive changes were verified; the exact five-file count was not independently certified or invented.
4. q19 has a source-serialization defect in the pack. Faithful copying can be supported yet factually incorrect. Reporting zero unsupported assumptions does not imply flawless source facts.
5. No unresolved-conflict truth appears among the twenty questions. Agent `conflict_detected` flags concerning superseded/historical text cannot define a positive unresolved-conflict denominator. CDR is N/A; adversarial conflict tests, if separately reported, are a different experiment.
6. Allowlisting was instructional and recorded rather than enforced by an OS sandbox. This review grades recorded answers against allowed frozen evidence; it cannot independently prove that no unrecorded reading occurred.
7. The 20 questions and three repetitions per condition are small, fixed, and related. No statistical significance or generalizable performance claim follows from the percentages.

Only judgment/review/derived-metrics artifacts were written. Frozen truth, frozen input files, metrics script, product code, and Project Model were not modified. No git action was performed.
