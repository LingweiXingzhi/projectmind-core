# AGENT_BOOTSTRAP — Context Authority 使用规则

> 这是使用规则,不是 Skill,也不是新的 source-of-truth。
> Context Authority 的输出是**派生视图**;真正的事实源是 claims + evidence + human decisions + 可验证的仓库状态。

Before working on any ProjectMind task:

1. Load the Context Pack for your task:
   `POST /api/extensions/context_authority {"action": "context", "task": "<your task>"}`
   (or read the generated `CURRENT_STATE.json` when HTTP is unavailable).
2. Treat `current_state.current` as the canonical starting context. Every item
   carries `claim_id` + `source` — follow the evidence links when you need
   deeper verification instead of guessing.
3. NEVER promote PROPOSAL or RESEARCH entries into current truth.
4. NEVER treat an OPEN PR as merged, and never treat unmerged branch content
   as main content.
5. NEVER use STALE / SUPERSEDED / HISTORICAL material as current authority —
   they are kept for provenance only.
6. If `known_conflicts` contains an item relevant to your task: mark your
   plan as blocked on `HUMAN_REQUIRED` and continue with unrelated work.
   Do not pick a winner yourself.
7. `do_not_assume` is binding: those points must not be "filled in" from
   your own prior knowledge.
8. You MAY disagree with proposals and research. You may NOT silently
   rewrite verified facts or human decisions. If you believe a verified fact
   changed, re-verify via evidence links and report — do not edit the claim
   registry by hand.

Failure modes this prevents (real ProjectMind history):
reading main's old role mapping instead of V1; quoting a stale benchmark
report that says "B NOT IMPLEMENTED"; citing `build_snapshot@106` after the
code moved to line 109; treating research suggestions as contract
requirements.
