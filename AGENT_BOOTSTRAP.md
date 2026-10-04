# AGENT_BOOTSTRAP — Context Authority consumer preflight

Context Authority is a derived context view. Claims, human decisions and
independently retrieved evidence remain the authority behind it.

Before developing C or making a decision from a pack:

1. Pin the target repository commit yourself as a full lowercase 40/64-character
   SHA. Request a pack for task `map proposal` and that exact revision.
2. Require schema_version `0.1`. Call
   `validate_context_pack(pack, expected_revision=your_pinned_commit)` (or POST
   action `validate_context`). Validation must succeed before using any field.
   Legacy unversioned packs require regeneration.
3. Read `current_state.current_by_scope` by BOTH key and scope. The unqualified
   `current` map deliberately omits ambiguous scopes; absence means UNKNOWN,
   never NOT_IMPLEMENTED. Check relevant known_conflicts, registry_problems,
   verification_unavailable and known_stale_sources before planning.
4. Resolve conflicts/invalid replacement graphs through HUMAN_REQUIRED. Treat
   unavailable volatile verification as unknown. Continue unrelated work only.
5. Follow each relevant claim's own evidence. Independently retrieve its exact
   source/revision before relying on implementation status, PR status, roles,
   contracts or architecture. A doc source revision is provenance; it does not
   certify that its assertions apply to your selected code commit. Local
   origin/main verification proves a local cached ref only; re-fetch/check
   remote state for a current GitHub claim. OPEN, MERGED and TEAM APPROVED are
   separate facts. Missing evidence or an unexpected repository needs fallback.
6. Keep proposals/research/historical sources in their respective sections.
   Their presence does not authorize a contract, architecture or map write.
7. Compare retrieved evidence with the pack. Reject inconsistent claims and
   report changed facts through the own CA review workflow. A checksum is
   structural consistency only, not source authentication; a coherent forged
   claim can pass validation. Human decisions require actual human authority.
8. Use full docs/code fallback for development details absent from the pack.
   Record the extra evidence and remaining unknowns. The pack is an entry point,
   not a substitute for API contracts or source review.

Preflight is complete only when every fact needed for the proposed action has
valid structure, the intended scope/revision and independently checked source,
or is explicitly recorded UNKNOWN/HUMAN_REQUIRED. C remains a separate task.
Interface boundary: C_CONSUMABLE_INTERFACE.md. No merge is authorized here.
