# Independent question-content sufficiency review

After actual-source review, final full-source A and pack-plus-fallback C both provide sufficient content for all fifteen questions. The pack alone supplies six complete answers, eight partial answers, and no usable extension-connection details for S10. The pack is therefore a useful starting context, with source fallback needed for development details omitted from its seed.

| Condition/version | Participant SUFFICIENT / PARTIAL / INSUFFICIENT | Independent SUFFICIENT / PARTIAL / INSUFFICIENT | Self-classifications upheld |
|---|---|---|---|
| A initial documents/source | 14 / 1 / 0 | 14 / 1 / 0 | 15/15 |
| A final, bounded actual-B-source supplement | 15 / 0 / 0 | 15 / 0 / 0 | 15/15 |
| B final pack only | 6 / 8 / 1 | 6 / 8 / 1 | 15/15 |
| C final pack plus source fallback | 13 / 2 / 0 | 15 / 0 / 0 | 13/15 |

C's original S05/S06 PARTIAL labels are retained in its unmodified answer file and the review JSON. They are independently classified SUFFICIENT because their remaining unknown concerns future formal adoption, while their actual answers completely provide the requested observed path rules and advertised prototype limits. This is a question-scope judgment, not a grant of operational acceptance.

## Basis and complete per-question audit

SUFFICIENT means all material requested facts are provided within their stated observed/proposed authority scope. PARTIAL means a material requested fact is missing; INSUFFICIENT means the main operative information needed for that requested task is absent. Honest refusal prevents fabrication but does not make missing content sufficient. Conversely, an honest caveat about future approval or current remote verification does not remove a complete answer to a scoped factual question.

| QID | Final A | Pack-only B | Final C | Independent content assessment and missing facts |
|---|---|---|---|---|
| S01: revision strings/aliases | SUFFICIENT | SUFFICIENT | SUFFICIENT | Full lowercase 40/64 hexadecimal characters, direct commit, common aliases and noncommit rejection are covered. No bit-unit error remains. |
| S02: five kinds | SUFFICIENT | SUFFICIENT | SUFFICIENT | Exact five-kind set is present. |
| S03: qualified/repeated names | SUFFICIENT | PARTIAL | SUFFICIENT | Pack supplies lexical names but not repeated-declaration occurrence preservation. Source appends every AST declaration; repeated names must remain separate entries. Extra precise ordering/identity policies are not independently required by this question. |
| S04: line semantics | SUFFICIENT | SUFFICIENT | SUFFICIENT | One-based def/async def/class keyword line, excluding decorators, is covered. |
| S05: path rules | SUFFICIENT | PARTIAL | SUFFICIENT | Pack omits detailed lexical rejection, exact tree membership/request failure, None/[] and blank GET selection behavior. Actual B source supplies all of them; final A/C preserve the formal-adoption caveat while giving usable explicit POST behavior. |
| S06: advertised limits | SUFFICIENT | PARTIAL | SUFFICIENT | Pack lacks explicit .py/Python-only language and content-accounting scope. A/C provide 2000 files, 1 MiB per eligible Python file, 16 MiB eligible Python content and language scope; source accounting refinements are accurate. Future formal service adoption is not asked. |
| S07: empty/parse/encoding cases | SUFFICIENT | PARTIAL | SUFFICIENT | Pack omits the successful zero-declaration files row and detailed skipped/encoding handling. A/C correctly give entries=[] success versus skipped path/reason and request-level failure. Source uses a shared parse/encoding reason, not separate stable machine subtypes. |
| S08: unsupported inference | SUFFICIENT | SUFFICIENT | SUFFICIENT | Declarations cannot establish dependencies, signatures, runtime entries or responsibilities; candidate/human boundaries are preserved. |
| S09: proposed C shapes | SUFFICIENT | PARTIAL | SUFFICIENT | Pack names suggest_map but omits its signature, aligned input revisions/repository, minimal candidate output and real-evidence/model/confirmation rules. Source supplies those proposed boundaries. |
| S10: independent extension connection | SUFFICIENT | INSUFFICIENT | SUFFICIENT | Pack lacks registration, routes, handle/context, body cap and concurrency. Source supplies directory discovery/restart, GET/POST API, JSON dict, 65,536-byte cap and shared-process threaded-state constraints without Core edits. |
| S11: code revision/map applicability | SUFFICIENT | SUFFICIENT | SUFFICIENT | Explicitly no: mutable local map identity/confirmation is distinct from code revision. |
| S12: map overwrite/confirmed architecture | SUFFICIENT | PARTIAL | SUFFICIENT | Pack denies accepted architecture and withholds overwrite permission but omits C's explicit curated/formal-map write prohibition. A/C supply both requested prohibitions; detailed future promotion workflow is not necessary to this question. |
| S13: PR/main/approval assumptions | SUFFICIENT | SUFFICIENT | SUFFICIENT | Captured OPEN branch and candidate main do not establish merged implementation or team approval. Later source/freshness checks remain operational responsibilities, not missing negative-assumption content. |
| S14: conflict/registry/unavailable policy | SUFFICIENT | PARTIAL | SUFFICIENT | Empty issue collections alone do not define future handling. Bootstrap/consumer contract supplies validation rejection, dependent-action stop, UNKNOWN/HUMAN_REQUIRED and evidence fallback. |
| S15: stable consumer fields/checks | SUFFICIENT | PARTIAL | SUFFICIENT | A/C distinguish normative frozen v0.1 interfaces from provisional seed/routing/prose and retain source/pin/repository/freshness/human checks. Pack-only field existence does not establish a stability/API guarantee. |

The nine questions needing information absent from the initial pack are S03/S05/S06/S07/S09/S10/S12/S14/S15. C's read manifest and fallback-required flags agree with that pattern. Its cited corroborating sources on other questions do not turn those questions into pack-content gaps.

## S05 and S06: why C's self-classification differs

S05 asks what validation rules C must respect when requesting CodeFacts. The actual frozen PR22 source specifies a None-or-list input with at most 2000 items before deduplication; nonempty strings; rejection of backslashes, controls below 32, DEL, and empty/dot/dotdot slash segments; exact membership in the selected committed tree; missing-path rejection; deduplication/sorting; None/all versus []/none. The GET adapter converts absent/empty paths to None and splits nonempty strings into lines. Literal drive/glob-like characters are not specially rejected by the lexical helper and are not expanded; exact tree membership still applies.

Both supplemented A and C provide these facts and explicitly recommend unambiguous POST selection rather than treating blank GET as a formally adopted integrated contract. No operative requested fact is missing. Formal future blank-GET acceptance is a valid retained authority unknown; it is not a reason to downgrade this observed-behavior answer. Initial A genuinely lacked backslash/control/dot/empty-segment rules before reading that source, so its earlier PARTIAL label remains upheld.

S06 asks what B **advertises**. C gives every advertised count/byte/language limit and accurate source-defined accounting: all selected files count toward 2000, explicit input length is checked before deduplication, files excluded at early skip stages do not consume the Python budget, and later decoding/parse failures do consume it. Oversized individual files are skipped; aggregate budget exhaustion fails the request. A's supplemented answer adds the same correct distinctions and per-Git-command timeout. Neither answer claims that these prototype bounds are an accepted future integrated service promise. The missing formal adoption cited by C is outside S06's requested fact, so independent SUFFICIENT is warranted.

## Evidence checks and retained records

The judge independently read the actual frozen PR22 `facts.py` and adapter `extension.py`, B delivery/boundary documentation, PR21 C/interface/role documentation, Core extension-interface/host/app code, bootstrap and C consumer contract, and relevant CA generation/validation/action code. The review compared actual code behavior rather than trusting participant classifications or probe summaries. The source confirms occurrence-preserving AST entries, path rules, byte accounting, shared parse/encoding skips, GET conversion, route/body/concurrency boundaries and revision/provenance distinctions.

All primary answer files and manifests cover S01-S15. A's supplement changes only S05-S07; every other answer record is identical to its retained `sufficiency_full_initial.json`. The initial 14/1 result is preserved separately in the review JSON. C's completed read manifest records exact-source reads and in-memory helper probes, with no Git/web or verifier execution. Its independently supplied expected revision was checked structurally, rather than resolved as a Git object. The judge did not rerun formal participants or modify any answer.

The final pack's compact UTF-8 size was independently reproduced as **71,822 bytes** and its canonical integrity digest matched. That exceeds the 65,536-byte host POST cap: a small context request/large response is usable, while uploading the complete pack to HTTP validate_context is not. Python validation is the appropriate route for this artifact. Structural validation and hashes do not authenticate human authority, semantic facts or applicability.

`SUFFICIENCY_INDEPENDENT_REVIEW.json` records the judge's own SHA-256 hashes of the four answer versions, questions, pack and three read manifests, plus reviewed source files. Those are review receipts, not an invented pre-dispatch freeze or reconstructed historical working-file snapshot.

## Reproducibility and interpretation limits

1. A was supplemented after its initial evidence gap was found; final A is not a fresh matched rerun. Initial answers remain available and only the bounded changed questions receive additional source detail.
2. These are fifteen fixed questions and one participant per condition. The comparison is information sufficiency under different access conditions, not statistical superiority, general correctness, or isolated schema/bootstrap causality.
3. Full-source/fallback conditions use permitted working Core/CA files as well as pinned B source. Not all normative working documents were separately frozen byte copies before participant reads. During reporting, root appended size/legacy-source caveats and corrected `current_state.registry_hash` in `C_CONSUMABLE_INTERFACE.md`; line-number citations can therefore shift. Operational product meaning/code and pinned B/questions/pack were retained, but a perfectly identical pre-read working-document snapshot is not claimed or reconstructed.
4. Allowlisting is instructional and recorded, **not an OS sandbox**. Complete manifests make the declared sources reviewable but cannot rule out unrecorded reads.
5. SUFFICIENT describes requested answer content. It is not evidence of live remote freshness, actual human acceptance, successful runtime integration, deployment safety, or applicability to all code branches/revisions. Formal blank-GET adoption, future capacity changes, new approval and map applicability remain separate dependent-action checks.
6. Source refs using legacy `repos/...` shorthand require exact live-verification/original-capture locators. A different linked worktree path is not proof of a different origin; repository identity and cached-ref versus remote freshness must still be checked independently.
7. The missing original performance report and fresh remote/approval/target-runtime evidence were not recovered by this restricted study. They were not manufactured to make any sufficiency count larger.

No participant answer, frozen question/pack, source/product file, Project Model, or git state was changed by the judge.
