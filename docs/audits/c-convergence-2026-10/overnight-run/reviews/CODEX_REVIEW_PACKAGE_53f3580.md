# CODEX REVIEW PACKAGE — AUDIT 78c2751..53f3580

You are reviewing ONLY this commit range of branch `integration/c-convergence-v1`
(worktree G:/jiagou/projectmind-c-convergence). Do not review commits before
AUDIT_BASE_SHA unless a finding requires checking a dependency. Read-only.

- AUDIT_BASE_SHA: 78c2751 (pre-overnight stable convergence HEAD)
- AUDIT_TARGET_SHA: 53f3580 (current frozen review target)
- Range commits: 98c3a00 (P01 relations), 43255b8 (P02 mutation-gap tests), 2c69093 (P04 real B), 53f3580 (P05/P05B real CA + typed consumption)

## Phases completed in this range

1. **P01 relations repair** — `extensions/map_proposal/relations.py` rewritten: the
   patch-regex signal extractor is GONE. Per changed .py file, C now AST-parses the
   pinned base blob and pinned target blob, normalizes to RESOLVED import-target
   sets, and diffs the sets. Rationale: adversarial cases 1a/1b/3/4 proved the
   regex silently missed relative imports, from-submodule imports and multiline
   imports (parse/extract failure → no signal at all, violating C-3). Read/parse
   failure now raises DiffSignalError → limits + HUMAN_REQUIRED unresolved.
   `engine.py` passes full change dicts (status/old_path) so renames anchor the
   base side at old_path and added files get empty base sets.
2. **P02 mutation-gap closure** — mutation testing (M1 revision-gate off, M2
   skipped-into-relations, M3 claim auto-attach, M4 text-only import, M5 position
   allowed, M6 lifecycle auto-accept; isolated clones, never committed) caught
   4/6 initially. Two genuine misses fixed by ADDING contract tests (never by
   weakening oracles): S25 no-attach instantiated with a real proposal + poison,
   and S03 domain-proof-bound-to-AST (docstring-only residual must not retain a
   relation). Final: 6/6 MUTATION_CAUGHT.
3. **P04 real B integration** — `tests/test_real_b_integration.py`: the REAL
   code_facts collector from the validated B+D line (file-loaded, registered as
   `extensions.code_facts.facts`, overridable PROJECTMIND_REAL_B_ROOT) runs in
   C's pipeline. Proven: S06 real base declaration delta → RESPONSIBILITY_CHANGE
   (the base-comparison channel previously existed only under mock), S13 real
   syntax-bad source → real skipped semantics, S14 real mismatch reject +
   same-revision safe, S15 real unavailable/exception → honest degradation,
   wanted_paths removed-path strictness (real B rejects; C never passes removed
   paths), real-history end-to-end (git compare HEAD~5..HEAD → real facts → C,
   deterministic, map hash unchanged).
4. **P05/P05B real CA + typed consumption** — `tests/test_real_ca_integration.py`
   + `ca_adapter.py` T1/T2/T3. Real packs built by the real CA builder (schema
   0.1, integrity digest), validated by the real validator (layer 1) before C
   consumes (layer 2). S19 real conflict routing with real `path:` scopes,
   S20 real stale semantics (implementation.* VERIFIED_FACT only binds
   revisions — discovery), S21 multi-scope, S24 tampered real pack → digest
   REJECT → whole-pack discard, S25 poison non-attach, metadata round-trip.
   P05B: T1 labeled context enrichment into uncertainty (never evidence),
   T2 per-field verification labels, T3 implementation-head claims checked
   against C's own pin — confirmed / UNKNOWN / contradicted (pack claims stop
   being consumed, invariant 11).

## Test results

- Full suite: `python -m unittest discover tests` → 121/121 OK (~30s).
- New tests this range: +5 W3 contract tests (relative/from/multiline/invalid-syntax),
  +1 W4 S25-with-proposals, +1 W3 domain-proof-AST, +6 real B integration, +9 real
  CA integration/P05B.
- Mutation results: 6/6 MUTATION_CAUGHT (M1-M6). M7 (no-map-write) is structural:
  no write path exists in C to disable; S29 hash tests guard the observable.
- Adversarial W3 script before/after: logs recorded; 1a/1b/3 now RELATION_ADD,
  case 4 invalid syntax now explicit UNKNOWN, all precision negatives unchanged.

## Real B / real CA / A30 status

- real_b = PASS (real collector in pipeline; ownership boundary: ast confined to
  relations.py — declaration parsing stays B's product).
- real_ca = PASS for builder/validator/conflict/stale/poison/tamper flows; live
  network verifiers (gh_api) remain unexercised → verification_unavailable rows
  and T2 live-verification flow stay component-level (recorded limit).
- A30 = fixed on a SEPARATE branch `fix/core-extension-runtime-isolation` @13c7ca8
  (Core run() catches BaseException → ExtensionError with operator-interrupt
  policy; 4 new tests fail on pre-fix host, pass post-fix; core suite 51/51).
  NOT in this range's runtime — S30 formal acceptance happens on the integration
  base later.

## Known limits (declared, not hidden)

- relations.py module resolution is the dotted-path ∩ known_paths heuristic:
  namespace packages / src-layout imports may stay invisible (no fabricated
  relations; recorded).
- A from-import shape rewrite can flag the package-__init__ dependency as
  removed (bounded: needs existing map edge + full domain proof + human review).
- Deleted-file removal signals are not in the relation channel (stale-map
  channel covers node removal; edge removal via a deleted last importer is a
  recorded gap).
- Real CA live verifiers (network) unexercised tonight.

## Contract invariants to check in this range

1. C-3: unknown/parse failure is never silent zero (relations.py).
2. E-4/S-2: claims never enter evidence; T1/T2 go to uncertainty with labels only.
3. Invariant 11: contradiction → record claim_id + both values + pack untrusted.
4. O-1/O-2: declaration parsing stays B's; import AST is C's own inference domain.
5. No formal-map write path; no position; PROPOSED/human_required everywhere.
6. Oracles strengthened, never weakened: X13 churn diagnostic removal is cited to
   contract F06 (resolved-set equality → no signal at all); W4 fixture base
   revision corrected (was a nonexistent 'c'*40 relying on silent degradation).

## Output format

AUDIT_BASE_SHA..AUDIT_TARGET_SHA, then findings by severity (BLOCKER/HIGH/
MEDIUM/LOW), FALSE_GREEN_RISK, CONTRACT_REGRESSIONS, SECURITY_FINDINGS, and
VERDICT: PASS | PASS_WITH_LIMITS | FAIL. No repository modification.
