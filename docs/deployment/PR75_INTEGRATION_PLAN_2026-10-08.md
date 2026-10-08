# PR75 integration plan

## Goal / baseline
Integrate PR73 repairs into PR75, which already includes PR74.
Frozen sources: PR73 b8322e024c4f23017fc85ecef155de75a31e65c1;
PR74 1ace7e265ea09fd84d515e6ddb0c7aad8a7378ca;
PR75 3db7017e73ac0a34ab9234e9e806c6572b00dff9.
The local source snapshot is byte/mode identical to PR75. Local synthetic
ancestry supports three-way comparisons, not full upstream history validation.
The uploaded integration commit will retain actual upstream PR75 and PR73 parents.

## Scope / conflict decisions
Preserve PR75 user guide, inline editor and entry flows; PR74 restore path
exclusions and real service-account guards. Combine installer permissions using
root:projectmind + 0750/0640, with guards retained.
Keep PR75 local task verification and process-trace checks; integrate PR73
HTTPS account/repository transport, fixture-write opt-in, independent HEAD
checks, native packet integrity and governed-task path. Real human approval
and external provider acceptance remain NOT_RUN.
Additional security defects reproduced by prior PR71 review require the same
public-session and review-scope repairs on this integrated source, without
replacing PR75 UI. Formal Project Model remains untouched (MINOR).

## Acceptance / process
1. Resolve overlaps with source-specific evidence and preserve both source intents.
2. Review auth/CSRF/Host/Origin, repository paths, JSON limits, AI worker lifecycle,
   installer permissions, restore boundaries and untrusted UI content.
3. Run targeted security tests and whole suite on frozen integrated source.
4. Run actual Waitress+Caddy HTTPS, cold restore, HTTP DOM and native browser
   flows including PR75 entry/editor UX. Fix concrete defects and rerun.
5. Commit; upload fast-forward to PR75 only after successful validation and
   checking unchanged remote head. Recheck remote tree and main, keep Draft.
