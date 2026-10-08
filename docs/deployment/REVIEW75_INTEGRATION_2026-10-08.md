# PR75 · PR73/PR74 integration and security review · 2026-10-08

## Result
PR75 already contains PR74 as its first parent. Integrate PR73 repairs into
that exact PR75 source; retain the PR75 user flow/inline editor and PR74
restore exclusions/service-user guards. Uploaded merge parents will be actual
upstream PR75 and PR73 SHAs; no main merge is authorized.

Sources:
- PR73: b8322e024c4f23017fc85ecef155de75a31e65c1
- PR74: 1ace7e265ea09fd84d515e6ddb0c7aad8a7378ca
- PR75 original: 3db7017e73ac0a34ab9234e9e806c6572b00dff9
- Tested local source: 99190135c0fbda8995db722040d1b8d8a968e723
- Tested source tree: a8821b7c99f66e7f0a77cbf776228509eb96cd02

The local checkout is an exact GitHub source-tree snapshot with local synthetic
ancestry for three-way merge analysis; it does not prove a full upstream
Git CLI clone/history. Actual remote ancestry is preserved on upload.

## Files Changed
- `archloop/ai_transport.py`, `ai_worker.py`: bounded admission/IPC, single
  total deadline and process cleanup, credentials remain in private pipes.
- `archloop/acceptance.py`, `acceptance_http.py`: preserve newer local runner
  checks; add certificate-validated HTTPS account/repository transport,
  fixture-write opt-in, independent Git HEAD and native packet integrity.
  Public task submission remains verification_pending; real human review NOT_RUN.
- `deployment/host.py`, `host_templates/install.sh`: combine root:projectmind
  0750/0640 release modes with existing runuser readability/executable guards.
  Preserve PR74 restore exclusions; reject target nested under runtime output.
- `app.py`, `deployment/wsgi.py`: finite/depth-bounded JSON, encoded version
  reads, correct trusted public account session instead of double local login gate.
- `archloop/backend_b.py`, `web/archworkbench.js`, `web/index.html`:
  explicit code-vs-design review; static files do not confirm process behavior;
  reject non-boolean review mode. Keep PR75 labels/entry/editor/download behavior.
- Relevant regressions and reproducible native-browser/DOM harnesses.

## Conflict resolution / security findings
1. Installer: keep PR74 ambient umask normalization and actual runuser guards;
   use PR73 explicit service-group ownership and validated mode scan, avoiding
   world-readable final release files and preserving symlink targets.
2. Acceptance runner: do not replace PR75 with the older PR70 runner.
   Keep process branch/failure details, guarded local task verification,
   no-session denial and independent self-coverage; integrate HTTPS variant
   and native handoff checks. Scripts operate only on explicit disposable fixtures.
3. Additional restore defect reproduced: runtime output as the parent of the
   destination caused FileExistsError AFTER creating recovered files. Refuse
   both containment directions before any copy; add no-output/no-backup-change regression.
4. Review mode: reject strings/numbers/collections instead of silently coercing
   them into code/design review. Existing absent/null defaults remain compatible.
5. Current public-session and review-scope defects identified in previous PR71
   review were still present here; apply minimal repairs, keeping new UX.
6. Source75 user-guide.js/css, app.js, view.js, user-flow README and author
   workspace.cjs remain byte-identical. Fixed SVG icon innerHTML sites use
   internal constants; untrusted project/guide/editor content uses text values.
7. New-content credential/machine-path pattern scan, diff check, JS syntax and
   shell syntax pass. This is self-review, not two human approvals.

## Verification
- Final full suite: **1102 tests / 310.784 s; 1092 PASS, 10 SKIP, 0 failures/errors**.
- Skips: 8 Linux maintenance tests on macOS; 1 unavailable upstream fixed 803c history;
  1 rule fixture without expected process steps. They are not counted as PASS.
- Whole-suite actual HTTPS acceptance runner: **32 PASS / 5 NOT_RUN**, including
  anonymous-write denial; real AI, human review and second-copy conditions remain separate.

Fresh runtime source: 99190135c0fbda8995db722040d1b8d8a968e723:
- 40 actual local TLS requests through Waitress + Caddy 2.11.7; independent
  Python CA/certificate/hostname verification, login/CSRF/cross-session guards,
  CAS, code/planning publication, version reads and serving lease.
- Cold restore after stopping the service: SQLite integrity; A workspaces,
  B documents, D tasks and shared record/history equality; architecture Git HEAD
  equality; 0 restored sessions.
- Actual Chromium: 136 HTTP requests, 0 page exceptions. PR75 entry chooser,
  registered repository import, inline editor/process save, planning route without
  fake SHA, cross-browser confirm/publish 403, governed task create/receive/start,
  explicit download JSON identical to HTTP packet, encoded version/second context
  reads, 430px viewport with 430px scroll width and fitting controls/forms.
  Only this disposable local CA fixture uses browser ignoreHTTPSErrors;
  the separate Python client verifies CA and hostname. This is not second-device
  or public-network proof.
- Real HTTP DOM: 12 scripts / 121 requests / 0 exceptions, shared record
  create/edit/history, conflict retains unsaved input, candidate labels and
  unchanged native JSON. Dialog/download/pointer are DOM polyfills, not native
  browser or TLS proof.
- Source remained clean during every final run. Original raw logs and temporary
  fixture credentials stay outside Git; uploaded evidence contains aggregate facts.

Reproduce on an isolated checkout:
```sh
python -m unittest discover -s tests -v
python verification/rehearse_public_https.py --caddy /path/to/caddy --output /private/new-tls-fixture
python verification/rehearse_public_dom.py --node /path/to/node --jsdom /path/to/jsdom --output /private/new-dom-fixture
python verification/rehearse_public_browser.py --caddy /path/to/caddy --node /path/to/node --playwright /path/to/playwright --browser-cache /path/to/browser-cache --output /private/new-browser-fixture
```
Use Python with requirements-deploy installed; make Node and Caddy available on
PATH for the full suite. Do not target live team repos/data with fixture runners.
Local legacy entry: `python app.py`; protected account entry:
`python -m deployment.server serve --config /private/runtime.json`, behind
a proxy configured from docs/deployment/README.md. Backend/state/architecture Git
must be configured for complete publish/task behavior, not just a rendered home page.

## Project Model Impact
MINOR.
Reason: integrates existing modules and repairs implementation/transport/runtime
boundaries. No new product responsibility, public business exchange format or
formal Project Model is approved/modified. README/AGENT_STANDARD and code are the
implementation basis; historical product analysis is not approval.

## Risks / Follow-up
No server/domain: actual cloud deployment, DNS/public CA, firewall,
second physical device/network, real AI semantic acceptance and real team review
remain NOT_RUN. Actual Linux systemd/service UID/maintenance remain NOT_RUN on
this macOS host. Upstream pinned 803c history not present in the local snapshot.
The historical PR70/PR75 reports remain source-specific historical evidence and
are not this integrated version's acceptance. Source PR73/74/main remain unchanged;
PR75 remains Draft. Do not infer merge permission from tests/CLEAN/MERGEABLE.
