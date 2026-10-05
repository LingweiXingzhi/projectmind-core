# S01-S30 ACCEPTANCE MATRIX (canonical, two-round stable)

RESULT: 30/30 PASS | two-round stable: True
HEAD: 857e9d0019759466a82dfeae2aa8291f0f3e1b56

## S01 — PASS
- ORACLE: real NODE_ADD exactly for uncovered path with eligible declarations
- CONTRACT: plan §8 S01/A01 + X19
- DEPS: FIXTURE facts + REAL git
- INPUT_HASH: 384073c401e62bff
- NOTES: 
- EVIDENCE: 2 test(s) run: test_w2_channels.NodeAddTests.test_s01_function_only_module_still_low_confidence_node, test_w2_channels.NodeAddTests.test_s01_new_module_exact_node_with_structured_evidence

## S02 — PASS
- ORACLE: real RELATION_ADD incl. unchanged-declarations X01
- CONTRACT: plan §8 S02/A02 + X01
- DEPS: REAL git + REAL B
- INPUT_HASH: 67060bea058db6dc
- NOTES: 
- EVIDENCE: 2 test(s) run: test_real_b_integration.RealBIntegrationTests.test_s02_s13_real_collector_supplied_pipeline, test_w3_relations.RelationChannelTests.test_s02_x01_real_import_add_with_unchanged_declarations

## S03 — PASS
- ORACLE: relation removal: last cross-domain import gone; multi-source residual; churn stays silent
- CONTRACT: plan §8 S03/A03 + X11/X13
- DEPS: REAL git
- INPUT_HASH: fcfa98c0933f5679
- NOTES: 
- EVIDENCE: 5 test(s) run: test_w3_relations.RelationChannelTests.test_removal_requires_existing_map_edge, test_w3_relations.RelationChannelTests.test_s03_domain_proof_is_ast_not_text, test_w3_relations.RelationChannelTests.test_s03_multi_source_remaining_import_no_removal, test_w3_relations.RelationChannelTests.test_s03_x11_last_import_removed_gives_removal_candidate, test_w3_relations.RelationChannelTests.test_x13_import_rewrite_churn_no_relation

## S04 — PASS
- ORACLE: rename/move → IMPLEMENTATION_LINK_CHANGE, never NODE_ADD; subdirectory variant
- CONTRACT: plan §8 S04/A04
- DEPS: FIXTURE
- INPUT_HASH: 62ee8a65a43c3c14
- NOTES: 
- EVIDENCE: 2 test(s) run: test_p06_matrix_closure.S04SubdirectoryRename.test_s04_subdirectory_move_link_change, test_w2_channels.RenameTests.test_s04_rename_updates_link_not_node

## S05 — PASS
- ORACLE: node removal: all evidence gone; partial retention → no candidate
- CONTRACT: plan §8 S05/A05
- DEPS: FIXTURE + MOCK tree
- INPUT_HASH: 84e3063fc936b1df
- NOTES: 
- EVIDENCE: 1 test(s) run: test_w2_channels.StaleMapTests.test_s05_partial_evidence_retained_no_removal

## S06 — PASS
- ORACLE: responsibility change: entryPoint declaration gone, no first-symbol pick
- CONTRACT: plan §8 S06/A06
- DEPS: REAL B (installed collector)
- INPUT_HASH: 3bdbab2f9a89ce83
- NOTES: 
- EVIDENCE: 2 test(s) run: test_real_b_integration.RealBIntegrationTests.test_s06_real_base_delta_gives_responsibility_change, test_w2_channels.ModifiedChannelTests.test_s06_entrypoint_gone_responsibility_no_first_symbol_pick

## S07 — PASS
- ORACLE: comment-only change: zero strong proposals with reason
- CONTRACT: plan §8 S07/A07 + X20
- DEPS: FIXTURE
- INPUT_HASH: b9a8e223a872db04
- NOTES: 
- EVIDENCE: 1 test(s) run: test_w2_channels.ModifiedChannelTests.test_s07_comment_only_zero_strong_proposal

## S08 — PASS
- ORACLE: formatting-only (line/quote drift): zero proposals
- CONTRACT: plan §8 S08/A08
- DEPS: FIXTURE
- INPUT_HASH: cd1fdc4ab9bb9593
- NOTES: closed P06
- EVIDENCE: 1 test(s) run: test_p06_matrix_closure.S08FormattingOnly.test_s08_line_and_quote_drift_only_zero_proposals

## S09 — PASS
- ORACLE: helper-only change: no NODE_ADD / strong proposal
- CONTRACT: plan §8 S09/A09 + F10
- DEPS: FIXTURE
- INPUT_HASH: ea7d2c5e6b65f55c
- NOTES: 
- EVIDENCE: 1 test(s) run: test_w2_channels.ModifiedChannelTests.test_s09_helper_only_no_node_no_strong_proposal

## S10 — PASS
- ORACLE: internal class added: no NODE_ADD
- CONTRACT: plan §8 S10/A10 + F9
- DEPS: FIXTURE
- INPUT_HASH: f3d39c04eeff3fe2
- NOTES: 
- EVIDENCE: 1 test(s) run: test_w2_channels.ModifiedChannelTests.test_s10_added_class_does_not_become_node

## S11 — PASS
- ORACLE: docstring import text is never a relation; string/comment included
- CONTRACT: plan §8 S11/A11 + X03/X12
- DEPS: REAL git
- INPUT_HASH: 27096d945bfd5a85
- NOTES: 
- EVIDENCE: 1 test(s) run: test_w3_relations.RelationChannelTests.test_s11_x03_docstring_import_text_never_a_relation

## S12 — PASS
- ORACLE: test/generated noise → no business architecture candidates
- CONTRACT: plan §8 S12/A12
- DEPS: FIXTURE
- INPUT_HASH: 65a85671d9cdf729
- NOTES: closed P06
- EVIDENCE: 2 test(s) run: test_p06_matrix_closure.S12TestNoise.test_s12_test_and_generated_noise_no_business_candidates, test_w2_channels.NodeAddTests.test_test_noise_and_generated_not_nodes

## S13 — PASS
- ORACLE: B skipped source → HUMAN_REQUIRED; no channel uses it; normal sources work
- CONTRACT: plan §8 S13/A13 + X04/X21
- DEPS: REAL B skipped semantics
- INPUT_HASH: c0f9085f2878a699
- NOTES: 
- EVIDENCE: 2 test(s) run: test_real_b_integration.RealBIntegrationTests.test_s02_s13_real_collector_supplied_pipeline, test_w3_relations.RelationChannelTests.test_f04_x21_skipped_source_never_feeds_relations

## S14 — PASS
- ORACLE: B mismatch rejected on all paths; same-revision/empty diff no bypass
- CONTRACT: plan §8 S14/A14 + X06
- DEPS: REAL B mismatch + supplied fixtures
- INPUT_HASH: b0b119a5f52d5164
- NOTES: 
- EVIDENCE: 6 test(s) run: test_map_proposal.BGateTests.test_installed_b_mismatch_rejected, test_map_proposal.BGateTests.test_supplied_mismatch_rejected_on_empty_changes, test_map_proposal.BGateTests.test_supplied_mismatch_rejected_on_normal_path, test_map_proposal.BGateTests.test_supplied_mismatch_rejected_on_same_revision, test_map_proposal.PinGateTests.test_empty_changes_with_different_pins_rejected, test_real_b_integration.RealBIntegrationTests.test_s14_real_revision_mismatch_rejected_same_revision_safe

## S15 — PASS
- ORACLE: B unavailable → honest degraded; B-free channels continue; no fabricated facts
- CONTRACT: plan §8 S15/A15
- DEPS: REAL absence + REAL exception
- INPUT_HASH: 1036b0e65f26006c
- NOTES: 
- EVIDENCE: 2 test(s) run: test_map_proposal.BGateTests.test_b_unavailable_degraded_with_limits_no_fabricated_fact, test_real_b_integration.RealBIntegrationTests.test_s15_real_collector_unavailable_and_exception

## S16 — PASS
- ORACLE: stale map: pre-base deletion candidate; read-unknown ≠ absent; base==target zero
- CONTRACT: plan §8 S16/A16-valid-map + F11/F15
- DEPS: FIXTURE + MOCK tree
- INPUT_HASH: fa7966371ce16cab
- NOTES: 
- EVIDENCE: 3 test(s) run: test_w2_channels.StaleMapTests.test_base_equals_target_zero_proposal_even_with_stale_map, test_w2_channels.StaleMapTests.test_s16_deleted_before_base_flagged_honestly, test_w2_channels.StaleMapTests.test_s16_fully_gone_at_target_removal_candidate

## S17 — PASS
- ORACLE: ambiguous multi-owner mapping → low confidence + uncertainty, no arbitrary pick
- CONTRACT: plan §8 S17/A17
- DEPS: FIXTURE
- INPUT_HASH: fd42266ff504e823
- NOTES: rename + relation variants
- EVIDENCE: 2 test(s) run: test_p06_matrix_closure.S17MultiOwnerAmbiguity.test_s17_multi_owner_relation_ends_low_confidence_not_arbitrary, test_w2_channels.RenameTests.test_s17_multiple_owners_ambiguity_flagged

## S18 — PASS
- ORACLE: missing evidence: added file without B entries → unresolved UNKNOWN
- CONTRACT: plan §8 S18/A18
- DEPS: FIXTURE
- INPUT_HASH: 1784637cff7fdf16
- NOTES: 
- EVIDENCE: 2 test(s) run: test_p06_matrix_closure.S18MissingEvidence.test_s18_added_file_without_b_entries_unresolved_unknown, test_w2_channels.NodeAddTests.test_added_without_facts_entries_is_unresolved

## S19 — PASS
- ORACLE: relevant CA conflict suppresses touching candidates only; word boundary
- CONTRACT: plan §8 S19/A19 + X14/X15/X18
- DEPS: REAL CA pack
- INPUT_HASH: 5622ea7f01c5b4f8
- NOTES: 
- EVIDENCE: 3 test(s) run: test_real_ca_integration.RealCAIntegrationTests.test_s19_s25_real_pack_conflict_routing_and_poison_non_attach, test_w4_ca_trust.AdmissionTests.test_s19_related_conflict_suppresses_touching_candidates_only, test_w4_ca_trust.AdmissionTests.test_s19_x15_word_boundary_no_substring_false_positive

## S20 — PASS
- ORACLE: non-current partitions (stale/proposal/research/history) never read
- CONTRACT: plan §8 S20/A20
- DEPS: REAL CA stale semantics
- INPUT_HASH: cc029387233b3af2
- NOTES: 
- EVIDENCE: 2 test(s) run: test_real_ca_integration.RealCAIntegrationTests.test_s20_real_stale_partition_never_read, test_w4_ca_trust.LoadContextTests.test_s20_non_current_partitions_never_read

## S21 — PASS
- ORACLE: multi-scope same key both in selection layer
- CONTRACT: plan §8 S21/A21
- DEPS: REAL CA pack
- INPUT_HASH: af3bd6080ffeb66a
- NOTES: 
- EVIDENCE: 2 test(s) run: test_real_ca_integration.RealCAIntegrationTests.test_s21_real_multi_scope_both_in_selection_layer, test_w4_ca_trust.LoadContextTests.test_s21_multi_scope_same_key_both_in_selection_layer

## S22 — PASS
- ORACLE: verified_fields per field; unverified fields support nothing
- CONTRACT: plan §8 S22/A22
- DEPS: MOCK validator (field map contract)
- INPUT_HASH: d1aa3a735de81ad0
- NOTES: live verifiers = recorded limit
- EVIDENCE: 2 test(s) run: test_real_ca_integration.RealCAIntegrationTests.test_p05b_t2_field_level_support_labels, test_w4_ca_trust.LoadContextTests.test_s22_verified_fields_per_field

## S23 — PASS
- ORACLE: unavailable keys explicit UNKNOWN, never faked bad-pack
- CONTRACT: plan §8 S23/A23
- DEPS: MOCK validator
- INPUT_HASH: ace8a26f4b6af9d6
- NOTES: real unavailable rows need network verifiers (recorded)
- EVIDENCE: 1 test(s) run: test_w4_ca_trust.AdmissionTests.test_s23_unavailable_keys_explicit_unknown_not_fake_badpack

## S24 — PASS
- ORACLE: invalid pack → whole-pack discard; independent candidates survive
- CONTRACT: plan §8 S24/A24
- DEPS: REAL CA digest tamper
- INPUT_HASH: f9366ab6321686b9
- NOTES: 
- EVIDENCE: 2 test(s) run: test_real_ca_integration.RealCAIntegrationTests.test_s24_tampered_real_pack_rejected_whole_pack_discarded, test_w4_ca_trust.AdmissionTests.test_s24_invalid_pack_degrades_but_independent_candidates_survive

## S25 — PASS
- ORACLE: coherent poison never enters evidence/rationale (also with proposals present)
- CONTRACT: plan §8 S25/A25 + X05/X16/X17
- DEPS: REAL CA pack poison
- INPUT_HASH: 1e39679694e24585
- NOTES: 
- EVIDENCE: 4 test(s) run: test_real_ca_integration.RealCAIntegrationTests.test_p05b_t1_context_enrichment_labeled_relevant_only, test_real_ca_integration.RealCAIntegrationTests.test_s19_s25_real_pack_conflict_routing_and_poison_non_attach, test_w4_ca_trust.AdmissionTests.test_s25_coherent_poison_never_enters_evidence, test_w4_ca_trust.AdmissionTests.test_s25_poison_never_attaches_when_proposals_exist

## S26 — PASS
- ORACLE: determinism: byte-identical repeats; order-insensitive IDs
- CONTRACT: plan §8 S26/A26 + X09
- DEPS: REAL git + REAL B history
- INPUT_HASH: 4aec4b5936c3d45e
- NOTES: 
- EVIDENCE: 4 test(s) run: test_map_proposal.CanonicalAndIdentityTests.test_determinism_same_input_same_output, test_real_b_integration.RealBIntegrationTests.test_real_history_end_to_end_deterministic_no_map_write, test_w3_relations.RelationChannelTests.test_relation_add_determinism, test_w5_compatibility.DeterminismAndIdentityTests.test_a26_repeat_is_byte_identical

## S27 — PASS
- ORACLE: malformed inputs controlled rejection incl. valid-context malformed map
- CONTRACT: plan §8 S27/A27
- DEPS: FIXTURE
- INPUT_HASH: 55b108f4a204d78c
- NOTES: closed P06
- EVIDENCE: 3 test(s) run: test_p06_matrix_closure.S27MalformedWithContext.test_s27_malformed_map_evidence_inside_valid_context_rejected, test_w5_compatibility.ErrorBoundaryTests.test_malformed_facts_shape_controlled_rejection, test_w5_compatibility.ErrorBoundaryTests.test_malformed_map_shape_controlled_rejection

## S28 — PASS
- ORACLE: path abuse rejected across changed/oldPath/map evidence/entryPoint sources
- CONTRACT: plan §8 S28/A28
- DEPS: FIXTURE
- INPUT_HASH: 333a29306cbff5ea
- NOTES: 
- EVIDENCE: 5 test(s) run: test_map_proposal.PathSafetyTests.test_facts_and_entry_point_paths_bounded, test_map_proposal.PathSafetyTests.test_unsafe_changed_paths_rejected, test_map_proposal.PathSafetyTests.test_unsafe_map_evidence_path_rejected, test_p06_matrix_closure.ExtensionSeamBoundary.test_malicious_map_text_controlled_rejection_not_crash, test_w5_compatibility.ErrorBoundaryTests.test_s28_rename_old_path_abuse_rejected

## S29 — PASS
- ORACLE: no formal-map write: file hash unchanged; no position; PROPOSED lifecycle
- CONTRACT: plan §8 S29/A29
- DEPS: REAL formal map hash
- INPUT_HASH: 7c5491deda7f3993
- NOTES: 
- EVIDENCE: 3 test(s) run: test_map_proposal.NoMapWriteTests.test_map_file_hash_unchanged, test_real_b_integration.RealBIntegrationTests.test_real_history_end_to_end_deterministic_no_map_write, test_w5_compatibility.ErrorBoundaryTests.test_no_position_anywhere_in_any_proposal

## S30 — PASS
- ORACLE: host isolation: runtime BaseException contained, all routes survive
- CONTRACT: plan §8 S30/A30
- DEPS: REAL Core (A30 fix branch)
- INPUT_HASH: n/a (external worktree)
- NOTES: verified on fix/core-extension-runtime-isolation worktree
- EVIDENCE: fix/core-extension-runtime-isolation: 9/9 extension tests incl. 4 A30 formal tests (fail on pre-fix host)

