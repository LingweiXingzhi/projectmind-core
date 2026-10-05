# CODEX FOLLOW-UP REVIEW PACKAGE — 53f3580..dda5246

FOLLOWUP review per the incremental protocol: this range contains ONLY the
fixes for your round-1 findings on 78c2751..53f3580 (verdict FAIL: 3 HIGH +
1 MEDIUM) plus their regression guards. Do not re-audit previously reviewed
commits except to verify a fix. Read-only.

- AUDIT_BASE_SHA: 53f3580 (your round-1 target)
- AUDIT_TARGET_SHA: dda5246
- Intermediary commit c0a8958 (P06 matrix closure tests) is included in the
  range; its content is test-only (tests/test_p06_matrix_closure.py).

## Finding-by-finding fix map

1. HIGH-1 valid scalar context claims crash admission
   → ca_adapter._context_line now passes the CLAIM ROW to claim_value_text
   (not the raw value). Guard: tests/test_real_ca_integration.py
   test_p05b_t1_context_enrichment_labeled_relevant_only now includes a
   scalar team.focus claim and asserts its text renders in the labeled line.

2. HIGH-2 changed dynamic imports become silent absence
   → relations._scan_imports tags dynamic calls with the statically visible
   string target (_dynamic_tag): "__import__:pkg.b". Set-diff over tags now
   surfaces changed targets. Guard: test_x02_changed_dynamic_target_is_not_silent
   (pkg.c → pkg.b rewrite → HUMAN_REQUIRED unresolved again).

3. HIGH-3 contradicted pack still controls conflict admission
   → apply_context_admission gates the conflict-row loop on pack_trusted;
   a contradicted pack contributes nothing except its contradiction record.
   Guard: test_p05b_t3_head_contradiction_marks_pack_untrusted now adds a
   relevant conflict pair to the pack and asserts the NODE_ADD survives and
   no conflict: unresolved appears.

4. MEDIUM-4 alias expansion fabricates submodule dependencies
   → _scan_imports returns from-alias-derived candidates separately;
   _file_relation_events records added_from_derived per resolved target;
   handle_relations forces low confidence + explicit "may be a package
   __init__ attribute" uncertainty when ALL candidates for a target are
   alias-derived. Prefix-derived candidates (from pkg.b import B → pkg/b.py)
   keep medium. Guard: adversarial case 3 asserts confidence low + named
   ambiguity.

5. False-green: the real-history test now hashes data/project-map.json (the
   formal map), not implementation files.

## Verification state

- Full suite 131/131 OK; mutation suite 6/6 MUTATION_CAUGHT (re-run after
  the fixes).
- Your other round-1 false-green notes addressed: scalar T1 claim, changed
  dynamic args, contradiction-with-conflict-row, attribute-shadowing
  negative. (Real B/CA tests still resolve the real implementations from
  documented paths and can skip when absent — by design, skips are recorded,
  never counted as PASS.)

## Output format

AUDIT_BASE_SHA..AUDIT_TARGET_SHA, findings by severity, FALSE_GREEN_RISK,
CONTRACT_REGRESSIONS, SECURITY_FINDINGS, VERDICT: PASS | PASS_WITH_LIMITS | FAIL.
