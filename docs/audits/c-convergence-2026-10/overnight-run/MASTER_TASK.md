# OVERNIGHT C CONVERGENCE — MASTER TASK

Run started: 2026-10-05 ~00:10 local. Supervisor/implementer: ZCode. External reviewer: Codex gpt-6.1-sol (non-blocking).

## Goal ladder (priority: CORRECTNESS > INTEGRATION > REVIEW > UI)
- P0: C → C_CONVERGENCE_READY_FOR_HUMAN_REVIEW (requires 30/30 + mutation gates + real B + real CA + A30 + 0 unresolved BLOCKER/HIGH + independent review PASS/PASS_WITH_LIMITS)
- P1: real Core/B/CA integration validation required by C
- P2: incremental Codex review via cursor model (never full-repo re-audit)
- P3: B+C+D integration branch `integration/bcd-v1`
- P4: only if time/quota remain: unified UI branch `feat/unified-ui-v1`

## Hard safety rails
- NO main merge/push, NO force push, NO source-branch modification, NO teammate branch deletion, NO formal map writes. Normal push only (HTTPS_PROXY=http://127.0.0.1:7897).
- Codex quota exhaustion NEVER pauses ZCode implementation.
- Morning: 08:00 no new large phases; 08:30 stop new work → checkpoint → FINAL_REPORT.md.

## State
- Authoritative resume point: STATE.json (same directory).
- Convergence branch: integration/c-convergence-v1 (worktree G:/jiagou/projectmind-c-convergence).
- Pre-overnight dirty relations.py preserved at patches/pre-overnight-dirty.patch (was broken mid-edit: `_from_candidates` called but never defined — 10 test errors; superseded by P01 principled repair).
