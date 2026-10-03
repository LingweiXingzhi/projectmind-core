# Agent Context experiment — independent final adjudication

Original twenty questions and ground truth were retained byte-for-byte.
INPUT_FREEZE precedes all six fresh formal participants A1–A3/B1–B3.
They used separate instructed file allowlists and recorded exact reads, with
no other runs, truth or metrics allowed. This was not an OS security sandbox;
unrecorded access cannot be independently excluded. Pilot runs are excluded.

| Condition | Strict accuracy | Half-partial accuracy | Factual disagreement | Unsupported | Stale as current |
|---|---:|---:|---:|---:|---:|
| Raw A1–A3 | 60/60 = 100% | 100% | 0/60 pairs = 0% | 0/60 | 0/60 |
| Original frozen CA B1–B3 | 53/60 = 88.33% | 89.17% | 2/60 pairs = 3.33% | 0/60 | 0/60 |
| Post-fix fresh CA B1–B3 | 60/60 = 100% | 100% | 0/60 pairs = 0% | 0/60 | 0/60 |

Original CA: six UNCERTAIN answers on q05/q17 because implementation-snapshot
evidence and PR21 contents were missing; one PARTIAL q19 copied the pack's
incorrect “40/64-bit” transcription. Supported copying can still be incorrect.
Four append-only, source-backed seed corrections restore bounded C/D snapshot
facts, PR21 contents and 40/64-character SHA units. Formal B/team documents
were not changed. Independent source-tree/head evidence is preserved.

FINAL_INPUT_FREEZE was written before three new, independent post-fix CA
participants. Its product revision is
`3e12fdfebc507ff1755f9f8bcb01e67a0eac14d6`. Raw runs were reused because their
immutable main/PR21/PR22 inputs stayed unchanged. The intervention combines
schema/resolver/bootstrap/seed improvements; it does not isolate each change's
causal effect. Later report/publication commits do not rewrite this pack or
its pinned experiment revision.

An independent judge assessed every answer and every cross-condition factual
difference, including five ambiguous questions and q05/q17/q19. Complete
as-of factual answers were graded on content, not automatically penalized for
an uncertainty flag about other branches or future remote status. Different
valid research/proposal/historical examples are semantically normalized.

Conflict Detection Rate: **N/A**, denominator zero. The frozen twenty questions
contain no unresolved-conflict truth item. Conflict/HUMAN_REQUIRED behavior
is verified separately by adversarial tests and poisoning P06; no fabricated
100% conflict score is reported. q03's MERGEABLE qualifier is absent from the
raw status snapshot and was not invented; q17 judges substantive changes,
not an exact raw-input file count.

Evidence: `experiments/ca_experiment/INPUT_FREEZE.json`, `FINAL_INPUT_FREEZE.json`,
all original and final participant/read files, `judgments.jsonl`, `metrics.json`,
`final_judgments.jsonl`, `final_metrics.json`, `JUDGMENT_REVIEW.md` and
`FINAL_JUDGMENT_REVIEW.md`. Strict aggregation rejects incomplete/duplicate
grids, bad conditions, absent normalized content/reasons and nonboolean flags.
Both runs of the metrics command verify unchanged frozen inputs.

This small fixed same-model study demonstrates recovered accuracy and no
observed disagreement regression. It does not establish superiority over Raw,
statistical significance, independence of model errors, generalization to
other projects or resistance to arbitrary attacks. Full evidence fallback
remains a consumer requirement.
