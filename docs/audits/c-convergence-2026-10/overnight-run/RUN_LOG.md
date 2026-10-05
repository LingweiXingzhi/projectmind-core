# RUN LOG — overnight C convergence

## 2026-10-05 ~00:10 — START
- Read all 9 deep-audit documents + CODEX continuation + checkpoint JSON.
- Convergence worktree: integration/c-convergence-v1 @ 78c2751 (pushed), dirty relations.py.
- **Dirty work inspected, NOT blindly committed**: `_from_candidates` called at relations.py:56/68 but never defined → 10 tests error with NameError. Fix was interrupted mid-edit (audit R7 confirmed).
- Dirty patch preserved: patches/pre-overnight-dirty.patch.
- Baseline at 78c2751 (temp worktree): 99/99 OK; adversarial BEFORE recorded → logs/adversarial_BEFORE_78c2751.txt (cases 1a/1b/3/4 silent misses confirmed).

## P01 — RELATION REPAIR — DONE @ 98c3a00 (pushed)
- Replaced patch-regex signal extraction with AST base-vs-target set diff per changed file (plan §22 preferred architecture; patch no longer parsed at all).
- Fixes: relative imports keep dots (1a/1b); ImportFrom alias expansion covers `from pkg import b` submodule + `from . import b`; multiline forms AST-native; invalid syntax → DiffSignalError → limits + HUMAN_REQUIRED unresolved (honest UNKNOWN).
- Churn guard removed: resolved-set equality gives no signal for rewrites (X13 oracle strengthened; limit diagnostic removed with cited contract clause F06).
- Engine passes full change dicts (status/old_path) so renames anchor base at old_path, added files get empty base sets.
- W4 fixture fix: AdmissionTests used fake base revision 'c'*40 relying on silent channel degradation; now passes real base. CA assertions unchanged.
- Suite 104/104 OK. Adversarial AFTER: logs/adversarial_AFTER_P01.txt — 1a/1b/3 → RELATION_ADD; 4 → explicit UNKNOWN; all precision negatives unchanged.
- Known limits recorded in REVIEW_QUEUE.json (resolution heuristic; from-shape rewrite __init__ edge; deleted-file removal gap).

## NEXT
- P02 mutation testing (isolated temp copies).

## 2026-10-05 ~02:30-03:15 — P06-P08 + Codex rounds + BCD + UI — COMPLETE
- P06 matrix closure @c0a8958 (9 tests) + DevKit 11/11 (fix/devkit-c-contract-pins).
- Codex round-1 FAIL (3 HIGH + 1 MEDIUM) → fixed @dda5246 with regression guards.
- Codex round-2 FAIL (1 HIGH residual + 1 MEDIUM) → fixed @857e9d0.
- Codex round-3 PASS_WITH_LIMITS (0 BLOCKER/HIGH); LOW fixed @7af59ea (post-budget, recorded).
- P07 human decisions: b9c2994 + HUMAN_DECISIONS.md (6 items).
- P08 acceptance matrix: 30/30 PASS two-round stable (7af59ea; artifacts/ACCEPTANCE_MATRIX.md).
- BCD integration/bcd-v1 @deb9b9f (PR #37): bd-v1 + A30 cherry-pick + C-only diff + real CA; 212 tests ×2 stable; runtime HTTP smoke; S30 in-runtime.
- UI feat/unified-ui-v1 @674c70f (PR #38): 3-product nav + review evidence chain + collab tabs; browser-verified.
- FINAL safety check verified: main untouched @7484d44, all source branches at pre-overnight heads, 0 dirty files anywhere.
- Run COMPLETE. Resume point: STATE.json (finished=true).
