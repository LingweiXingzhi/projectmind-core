# Independent Context Pack review — 2026-10-03

## Result

Fresh validation used the actual `feat/context-authority-mvp` implementation, temporary Git repositories and newly authored tests. Previous experiment reports were not treated as verification. No branch switch, commit, push, merge, formal Project Model change, shared standard change or other worktree change was made.

The original builder accepted `revision="definitely-not-a-commit"`, crashed on a legal scalar `implementation.code_facts` value, replaced the second collapsed claim's source with the first source, omitted evidence for historical/proposal/research/stale sections and excluded C's team/contract context. These were reproduced before changes. A versioned producer/consumer boundary now exists in real code:

```python
from extensions.context_authority.context_pack import build_context_pack, validate_context_pack

pack = build_context_pack(task, repo_root, registry_path, revision=code_facts["revision"])
validate_context_pack(pack, expected_revision=code_facts["revision"])
# Only then inspect current_state.current_by_scope, relevant_contracts,
# human_decisions, known_conflicts, verification_unavailable and evidence.
```

HTTP consumers may POST `{"action":"validate_context","pack":pack,"expected_revision":full_sha}` to `/api/extensions/context_authority`. Invalid input returns HTTP 400. The consumer must supply the revision independently from its Snapshot/CodeFacts; copying the pack's own revision into `expected_revision` is only a consistency check.

## Findings and fixes

| ID | Reproduced failure / root cause | Minimal fix | Regression cases | Affected experiment |
|---|---|---|---|---|
| CA-FINDING-P01 | Caller revision was echoed without syntax, existence or commit validation. | Resolve default HEAD read-only; explicit inputs require an existing full lowercase 40/64 character commit SHA. Version-bound code claims at another commit become stale. Source-document revision remains provenance. | P01–P09, P23, P40, P42, P45 | Frozen Context Pack and C/Snapshot/CodeFacts revision alignment |
| CA-FINDING-P02 | Collapsed claim IDs all received the winner's source; `source.revision` was absent from evidence revision. | Reconstruct evidence from each original claim; carry distinct `claim_revision`, `source_revision` and effective `revision`; preserve verifier locator and derivation links. | P09–P11, P22, P26, P47, P56 | Provenance recovery, stale PR head and poisoned evidence studies |
| CA-FINDING-P03 | Only current and conflicted claims had evidence; historical rows were omitted entirely. | Add `historical_sources` and evidence for every emitted claim section, including stale and superseded records. | P11, P21–P22, P24–P25 | Context sufficiency and evidence fallback |
| CA-FINDING-P04 | `build_do_not_assume` called `.get` on a scalar value and only recognized OPEN at one hardcoded key. | Check value shape; recognize OPEN/PR_OPEN across current scopes; retain conservative global warnings. | P12–P14, P34; original T12 retained | OPEN PR mistaken for merged or accepted status |
| CA-FINDING-P05 | Substring `pr` matched unrelated words; map/proposal routing omitted current team decisions and contracts. Filtered counts still described the whole registry. | Word-boundary routing; map task includes C's authority, contract, implementation and research domains; counts cover emitted sections. | P17–P19, P33, P35 | C candidate generation and task context filtering |
| CA-FINDING-P06 | Legacy key-only current projection could select one scope or forget a conflicted/unavailable alternate scope. | Consume resolver `current_by_scope`; expose an unqualified key only when relevant surviving scopes are unambiguous. | P20, P32, P43–P44 | Cross-repository or multi-scope context |
| CA-FINDING-P07 | Pack had no schema/version or consumer guard; section/type/evidence contradictions were accepted. A checksum alone is recomputable. | `schema_version="0.1"`; callable and HTTP validation check projections, scopes, types, states, evidence, revisions, counts, warnings and finite JSON; most poison tests recompute checksum before rejection. Research artifacts cannot authorize current facts/contracts/human decisions; superseded rows require a real replacement edge. | P24–P36, P38–P39, P49–P55, P57–P60 | Poisoned-pack injection study |
| CA-FINDING-P08 | Live evidence could be discarded during pack construction; cached `origin/main` could look like current remote verification. | Preserve live verifier metadata and verified fields; retain `local_reference` freshness with explicit cached-reference warning. | P21–P22, P47–P49 | Verifier unavailable and local/remote freshness |
| CA-FINDING-P09 | Filtering revision-bound claims before graph resolution would turn a valid supersedes edge into a broken reference. A graph-invalid conflict need not contain two different values. | Resolve the complete registry first, then demote mismatched current code evidence; accept graph-invalid HUMAN_REQUIRED diagnostics only with a registry problem anchor. | P45–P46 | Supersedes/revision and conflict fixtures |
| CA-FINDING-P10 | Internally coherent false human decisions cannot be distinguished from actual approval by comparing fields or by an unkeyed hash. | Explicit structural-only guarantee; retain source locator for independent review. A coherent false human claim intentionally still passes structural validation. | P37 | Human-authority fallback and semantic poisoning |

## Verification

Executed:

```powershell
python -m unittest tests.test_ca_adversarial_pack tests.test_context_authority -q
```

Result: **92 tests PASS**: 60 independently authored adversarial pack tests plus the original 32 Context Authority tests. Fixtures use two known commits in a temporary Git repository and keep uncommitted content distinct from the selected commit. No network verification is needed for these tests; mocked verifiers exercise successful, stale, unavailable and cached-reference paths. Reordering the registry preserves the pack exactly.

Seed C pack at worktree HEAD `ffd8781c2996f3656022133c3269147c18fcc77f`, `run_verifiers=False`:

| Measurement | UTF-8 bytes |
|---|---:|
| Compact Context Pack | 44,669 |
| Compact HTTP validation request, including expected revision | 44,769 |
| Default Python JSON formatting validation request | 47,452 |
| Extension Host POST cap | 65,536 |

This seed fits the existing POST cap. Larger registries may exceed the HTTP request cap because projections repeat evidence; the Python callable has no host body-size cap. This review did not change the shared host cap or add a compression protocol.

## Files Changed

- `extensions/context_authority/context_pack.py`
- `extensions/context_authority/extension.py`
- `tests/test_ca_adversarial_pack.py`
- `experiments/validation/PACK_REVIEW.md`

Resolver/schema/registry/verifier changes belong to the other independent reviewer. This report does not claim ownership of their findings or tests.

## Project Model Impact

`MINOR`

Reason: this hardens the existing Context Authority boundary and derived views. Team responsibilities, accepted architecture and formal Project Model remain human decisions and were not edited.

## Risks / Follow-up

The checksum and validator establish structural consistency only. They cannot authenticate a person, prove a source document was approved, detect a fully coherent false registry, or prove an omitted claim never existed. A forged coherent human claim, a falsified source locator or a completely deleted claim with all projections and counts consistently rebuilt still requires independent source review and, when authority is unresolved, human fallback.

The pack's selected code revision does not establish that source documents, OPEN PR contracts or the curated map apply to that commit. Source revisions are preserved without silently becoming applicability guarantees. `run_verifiers=False` leaves freshness unverified. Absence of a C/D implementation claim is not proof that the module is absent from the selected repository revision; implementation sufficiency requires exact Git evidence or an explicit UNKNOWN. Frozen previous packs lack the new schema and must not be consumed through the new gate without regeneration.
