# Independent post-fix judgment review

## Result and retained baseline

The three new CA runs were independently read against `context_final_inputs/` and the original unchanged twenty-question truth. The original 60 raw judgment records were reused verbatim in meaning and content, not reassessed against the enlarged pack. All 120 final rows contain the strict schema, factual normalization, flags, and nonempty independent reasons.

| Condition | Correct | Partial | Uncertain | Wrong | Strict accuracy | Half-partial accuracy | Factual disagreement |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original raw A1-A3, reused | 60 | 0 | 0 | 0 | 100% | 100% | 0/60 = 0% |
| Post-fix CA B1-B3 | 60 | 0 | 0 | 0 | 100% | 100% | 0/60 = 0% |

Stale-source use as current and unsupported assumptions are both zero. CDR remains **N/A/null**: the unchanged twenty questions contain no unresolved-conflict positive truth cases. Agent self-reported `conflict_detected` flags on superseded material do not create such a denominator.

The original `judgments.jsonl`, `metrics.json`, and `JUDGMENT_REVIEW.md` are retained, including the original CA result of 53 correct, one partial, and six uncertain answers (88.33% strict, 89.17% half-partial). The post-fix result is a new experiment, not a replacement of that failure record.

## Specific repaired failures

**q05:** The final pack adds `claim-c-observed-status`, with the absence of `extensions/map_proposal/` in main@7484d44, PR21@ff22b769, and PR22@0c467471. All three runs explicitly answer NOT_IMPLEMENTED in those immutable observed trees, rather than inferring it from a proposal label. Other branches, future revisions, and the requested product revision remain separately unknown. All three are CORRECT even though they mark `uncertain=true`: they supply the entire frozen factual answer and bound the uncertainty outside its scope.

**q17:** The final pack adds `claim-pr21-contents`, describing V1 role mapping and human-review boundaries at the unchanged PR21 head and listing README, the audit, and five standard documents. All three runs now state the substantive documentation change and preserve the distinction from merger or team approval. Seven total documents is consistent with the truth's five standard documents plus README/audit, not a conflicting file count. All three are CORRECT.

**q19:** The active replacement contract specifies 40/64 **characters** of lowercase hexadecimal SHA directly resolving to a commit; the old bit-unit claim is explicitly superseded. All three runs state the correct character unit and rejection constraints. B1's original bit-unit PARTIAL error is repaired. All three are CORRECT.

## Ambiguous-question audit

| Question | Independent reasoning |
|---|---|
| q05 | Original raw concrete tree absence is equivalent to the final CA's bounded three-tree negative. A true scope limitation is not abstention on the observed fact. No all-branches nonimplementation is inferred. |
| q08 | Raw benchmark evaluation and final CA cat-file performance research are both supported research/evaluation examples. They retain one equivalent valid-example normalization rather than counting their different subjects as disagreement. |
| q09 | All runs identify the proposed mapSource digest/applicability patch. Extra consistency/acceptance detail is supported, and no implementation is asserted. |
| q11 | Raw old-main baseline/branching text and final CA old-main role mapping are different valid stale examples. Both receive the equivalent valid-stale label; none is used as current authority. |
| q19 | Raw Chinese SHA-1/SHA-256 representation length and all final CA explicit hexadecimal character units are equivalent. Superseded bit units are mentioned only to reject them. |

Additional uncertainty-sensitive checks: B1-B3 q06 all explicitly give the correct captured main SHA while warning that local `origin/main` does not prove subsequent remote state. B2 additionally flags the cached-ref locator/scope naming difference present in the pack. A different worktree path alone does not prove a different Git origin; repository identity requires source checking. These answers remain CORRECT against the frozen as-of truth. B2 q15/q16 state the captured approval/map-identity facts completely while qualifying future/applicability state; their uncertainty flags do not remove that answer. Grading does not claim that the agents independently authenticated the pack.

## All remaining cross-condition differences

The original full twenty-row comparison in `JUDGMENT_REVIEW.md` remains applicable, with q05/q17/q19 updated above. The following exhaustive projection makes the final comparison reviewable without converting prose or extra evidence into factual disagreement.

| QID | Raw versus post-fix CA | Final disposition |
|---|---|---|
| q01 | Raw human-confirmation explanation; CA current scoped V1 and old/V2 rejection | Same A/B/C/D roles |
| q02 | Raw tree/delivery evidence; CA timestamped PR_OPEN | Same not-merged state |
| q03 | Raw independent-prototype/integration detail; CA full head, PR_OPEN, benchmark and approval qualification | Same reference implementation in unmerged PR22 |
| q04 | Raw dependency/call-graph exclusion; CA declaration-only/signature/entry exclusion | Same no dependency graph |
| q05 | Raw main/PR21 tree absence; CA adds PR22 absence and explicit other-tree unknown | Same frozen nonimplementation; repaired |
| q06 | Raw frozen main SHA; CA same captured SHA with local-reference/repository and requested-pin qualification | Same captured revision; no current-remote authentication claimed |
| q07 | Raw full head; CA same with API verification timestamps | Same PR22 head |
| q08 | Raw evaluation example; CA explicit performance RESEARCH example | Equivalent valid research examples |
| q09 | Raw mapSource digest/consistency detail; CA same proposal/nonacceptance state | Equivalent valid proposal |
| q10 | Raw C input/integration detail; CA C under current V1 | Same owner C |
| q11 | Raw stale baseline/branching excerpt; CA stale role-map excerpt | Equivalent valid stale examples |
| q12 | Raw historical main-benchmark scope; CA explicit historical report classification | Same rejection of old global current B status |
| q13 | Raw kind enum/nesting detail; CA same enum and historical-example distinction | Same five kinds |
| q14 | Raw keyword-line semantics and occasional duplicate detail; CA keyword-line semantics | Same one-based nondecorator line |
| q15 | Raw candidate versus approval explanation; CA same captured candidate and later-approval qualification | Same not TEAM APPROVED |
| q16 | Raw local-map identity absence/UNKNOWN; CA same plus proposal/applicability qualification | Same absent identity |
| q17 | Raw documented V1/review/baseline changes; CA explicit head-scoped content and seven-file inventory | Same substantive documentation change; repaired |
| q18 | Raw full head; CA same with API verification timestamps | Same PR21 head |
| q19 | Raw SHA-1/SHA-256 lengths; CA explicit hexadecimal characters and rejected superseded bit text | Same contract; repaired |
| q20 | Raw no batch requirement but research provenance unavailable; CA explicit RESEARCH source | Same contract denial |

No material contradiction remains in the twenty question-relevant answers. Valid alternate q08/q11 examples and supported timestamp/scope qualifications do not establish a better raw or CA factual result. The narrower operational questions about source authentication and revision applicability are not answered by 100% factual agreement.

## Verification and limitations

- Verified all 21 original `INPUT_FREEZE.json` hashes and all four `FINAL_INPUT_FREEZE.json` hashes, including unchanged truth. Original raw records were reused exactly as JSON values; the final judgment grid is 120 unique run/qid records with required fields.
- Ran `python experiments/ca_experiment/compute_metrics.py --final` successfully. The script verifies both freezes and writes `final_metrics.json`. Its earlier missing-reason validation gap has been repaired by the root task; inspection confirms a required nonempty reason check is now present. The judge did not modify the script or product.
- Normalization preserves the same original question-relevant factual labels. Unsupported source invention and stale-as-current use are judged separately from correctness. Self-reported uncertainty/conflict flags never substitute for factual adjudication.
- The intervention combines schema/scope representation, bootstrap rules, seed-claim completeness, and contract-unit correction. It was selected after examining original failures. This study does not isolate which component caused improvement, and the same fixed questions are not a new holdout set.
- Raw agents were not rerun. Their source main/PR snapshots and truth are unchanged, but the CA pack has later verification metadata and additional scoped evidence. Reuse is appropriate for this comparison and is a reproducibility limitation for causal or matched-runtime claims.
- Only three repetitions per condition over twenty related questions are available. No significance, broad superiority, or general reliability inference follows from the resulting percentages.
- Allowlisting was instructional and recorded, **not an OS sandbox**. The review cannot establish that no unrecorded external reading occurred.
- Final bootstrap requires independent evidence retrieval before operational reliance. The answer task restricted these runs to their supplied pack, so correct captured answers do not demonstrate complete development preflight, current remote verification, semantic authentication, or applicability to product revision 3e12fdf.
- C's negative implementation claim is limited to three observed immutable trees. The corresponding D claim has the same limited scope; other remote D candidates are not globally ruled out by that absence.
- Existing truth q03 includes a MERGEABLE parenthetical not exposed by the original frozen PR-status input. As in the original review, missing repetition of that secondary detail is not penalized. The accurate unmerged reference-implementation status and separately tested head are the requested factual core.

Frozen truth and original failure artifacts remain unchanged. No product code, Project Model, or git state was modified by this judgment task.
