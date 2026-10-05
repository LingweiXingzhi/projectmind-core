Reading additional input from stdin...
OpenAI Codex v0.160.0
--------
workdir: G:\jiagou\projectmind-c-convergence
model: gpt-6.1-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: medium
reasoning summaries: none
session id: 01a107ea-22c1-70d3-8df5-57f4ef29bc49
--------
user
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

You are an independent reviewer. Read the actual code in G:/jiagou/projectmind-c-convergence (git show 53f3580:extensions/map_proposal/relations.py etc. or read the working tree at the frozen SHA). Apply the 9 standard review questions from the C convergence protocol: (1) did the new range violate any C contract invariant; (2) did skipped evidence leak into strong proposals; (3) did CA poison gain a path into proposal evidence; (4) did UNKNOWN become silent absence; (5) did relation recall improvements cause precision regressions; (6) did ZCode weaken an oracle to make tests pass; (7) did B/CA/Core responsibilities get duplicated; (8) did any formal-map write path appear; (9) are new tests independent from implementation behavior. Output your findings in the requested format.
warning: Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.
  user (C:\Users\李则兴\.codex\config.toml): `features.rmcp_client` is ignored.
warning: Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.
  user (C:\Users\李则兴\.codex\config.toml): `features.rmcp_client` is ignored.
2026-10-04T17:15:49.313319Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
2026-10-04T17:15:51.246848Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
2026-10-04T17:15:52.258693Z ERROR codex_models_manager::manager: failed to refresh available models: request timed out
ERROR: Reconnecting... 2/5
ERROR: Reconnecting... 3/5
ERROR: Reconnecting... 4/5
ERROR: Reconnecting... 5/5
warning: Falling back from WebSockets to HTTPS transport. request timed out
codex
我会按 `code-review` 技能读取项目规范与冻结提交的实际差异，核查九项审查问题，并保持仓库只读。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content 'C:/Users/李则兴/.codex/skills/code-review/SKILL.md'; Get-Content README.md; Get-Content docs/standards/AGENT_STANDARD.md; Get-Content docs/standards/TEAM_SOP.md" in G:\jiagou\projectmind-c-convergence
 succeeded in 422ms:
---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to \"review since X\"."
---

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

The issue tracker should have been provided to you. If `docs/agents/issue-tracker.md` is missing, tell the user to run `/setup-matt-pocock-skills`.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point (a commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If they didn't specify one, ask for it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.), fetched via the workflow in `docs/agents/issue-tracker.md`.
2. A path the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* �?*how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. �?rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. �?extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. �?move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). �?bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. �?give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. �?replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. �?gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. �?split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. �?delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. �?hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. �?cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. �?drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

**Standards sub-agent prompt** should include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full (the sub-agent has no other access to it).
- The brief: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** should include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings, because the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing �?**Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions �?**Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
# projectmind-core
面向复杂项目的HUMAN-AI协同认知与管理平�?

## 本地运行第一条演示主�?

需�?Python 3.10+ �?Git。在本仓库根目录运行�?

```powershell
python app.py
```

然后打开 <http://127.0.0.1:8765>。查看地图和 Git 变化无需安装 Python 包或配置 API Key�?

页面显示 ProjectMind 自身的一�?*人工整理的演示功能图**。点击节点可以查看职责、关系、关键入口，并读取固�?Git 提交中的真实文件内容。顶部显示此次证据所对应的完整提�?ID；若来源文件不在该提交中，页面会标记“此版本缺失”。“导出当前摘要”会生成带提�?ID �?Markdown 文件，方便交接�?

节点可拖动以调整查看布局；连线会跟随。点击“保存临时布局”后，位置只保存在当前浏览器本机，刷新页面可以恢复。若 Git 提交已变化，页面会提示复核旧布局。“恢复原位”会清除本机保存的位置。“导出图草稿 JSON”包含当前位置、节点说明、关系、来源路径和对应的完�?Git 提交 ID，可交给队友�?AI 审看。位置只代表查看布局，不表示新增依赖；导出文件明确标记为未确认草稿，不会写入正式 Project Model �?model 仓库�?

“对照两个真实提交”默认比较当前提交与它的父提交。也可以输入另一�?*完整提交 ID**作为基准。变化文件来�?Git；若节点声明的来源文件出现在变化中，节点只会标记为“待复核”。导出的 Markdown 摘要包含这次比较。文件变化不能证明职责或架构一定改变�?

可选的“让 AI 解释”按钮仅在配置后启用。在启动程序的同一�?PowerShell 窗口设置环境变量，再运行 `python app.py`�?

```powershell
$env:OPENAI_API_KEY = "你的 API Key"
$env:PROJECTMIND_AI_MODEL = "你账户可使用的模�?ID"
python app.py
```

点击按钮后，只会�?OpenAI 发送选中节点的人工演示描述、直接关联的变化文件名和最�?12,000 个字符的 Git 差异。请求使�?`store: false`；密钥只留在本地服务端环境变量中，不进入地图文件或浏览器。页面把返回内容标为“AI 候选”，要求人对照来源复核。未配置时其它功能照常可用。API 调用可能产生费用；是否能成功取决于所用账户、模型和网络�?

这一步验证“图 �?详情 �?Git 来源 �?版本变化 �?待复核候�?�?可�?AI 解释 �?临时布局与导出”的运行路径。演示图不代表自动识别出的架构，也不代表团队批准的正�?Project Model�?

## 团队独立扩展

新增功能放入 `extensions/<功能�?/extension.py`，定义标题、说明与 `handle(context, method, data)`。重启服务后，主页侧栏自动出现该功能的独立页面入口，数据接口�?`/api/extensions/<功能�?`；不需要为每个人的新功能修�?`app.py` 或共享页面。`extensions/project_summary/` 是可运行的样例。扩展只接入独立功能页，不会自动修改人工功能图；需要在主图展示的内容仍由团队复核并集成�?

具体输入、错误和四人目录分工�?[独立扩展接口](docs/standards/EXTENSION_INTERFACE.md)�?

## 查看另一个本�?Git 仓库

可以在启动时指定仓库及其**人工整理的地�?JSON**。这里不自动扫描代码，也不会在启动时读取未指定的其他项目�?

```powershell
python app.py --repo "仓库完整路径" --map "地图 JSON 完整路径"
```

地图文件可参�?`data/project-map.json`：顶层需�?`note`、`nodes`、`edges`；每个节点需�?`id`、`title`、`summary`、`entryPoint`、`position`（`x`/`y` 数字）和 `evidence`（仓库内相对路径 `path` 及说�?`reason`）；每条关系需要已存在的节�?`from`、`to` �?`label`。目前画布为 680×470，节点约�?185×140；为让节点完整显示，初始位置建议满足 `x` �?0�?95、`y` �?0�?30。程序会在启动时检查地图格式，并按目标仓库�?Git 提交核查来源文件。地图内容仍须人工复核�?

运行核心验证�?

```powershell
python -m unittest discover -s tests -v
```
# ProjectMind Development Agent Standard

You are the coding agent for ProjectMind.

Your job is to complete the requested task with the smallest safe change while keeping code, tests, and the confirmed Project Model consistent.

## PRIORITY

Follow this order:

1. User / Issue requirement
2. Confirmed Project Model
3. Existing design decisions
4. Existing repository conventions
5. Your own inference

Never override a higher-priority source with your own assumption.

## BEFORE EDITING

You MUST determine:

- task goal
- acceptance condition
- affected module(s)
- relevant files
- relevant Project Model entries
- likely scope of change

Read only what is necessary first.
Do NOT scan the whole repository unless the task truly requires it.

If critical information is missing, state what is missing before making a risky assumption.

## EDITING RULES

You MUST:

- make the minimum change needed
- preserve existing behavior outside the task
- follow existing naming and structure
- update or add tests when appropriate
- keep secrets out of source control

You MUST NOT:

- refactor unrelated code
- rename or move unrelated files
- invent requirements
- treat AI inference as confirmed architecture
- silently modify confirmed Project Model decisions
- expose API keys, passwords, tokens, or private credentials
- add new dependencies unless they are necessary for the task and consistent with the existing stack

## PROJECT MODEL RULE

After code changes, classify Project Model impact as exactly one of:

- `NONE` �?no project cognition change
- `MINOR` �?internal implementation changed; module boundary/responsibility unchanged
- `UPDATE` �?module, responsibility, dependency, code mapping, or implementation status should change
- `UNCERTAIN` �?evidence is insufficient; human decision required

For `UPDATE` or `UNCERTAIN`, do NOT finalize the Project Model yourself.
Provide a proposed change and evidence for human approval.

## AI / TOKEN EFFICIENCY

Prefer deterministic methods before LLM reasoning:

1. task / Issue context
2. Git diff
3. file / symbol changes
4. static dependency analysis
5. existing code-to-module mapping
6. relevant Project Model entries
7. LLM reasoning only when semantic judgment is needed

Do not re-read the entire repository when a local diff is sufficient.
Do not repeatedly summarize context that is already available in structured form.

## VERIFICATION

Verify changed behavior when practical.

Prefer:

- relevant automated tests
- targeted manual checks
- obvious failure-path checks when appropriate

Never claim a change is tested or verified unless the corresponding test or check was actually performed.

If verification cannot be completed, state what was not verified and why.

## UNCERTAINTY

For low-risk local uncertainty, choose the most conservative reasonable option and state the assumption.

If uncertainty may affect architecture, security, data integrity, public interfaces, or major behavior, stop and request human confirmation.

Do not hide uncertainty.

## REQUIRED FINAL REPORT

Return this exact structure:

### Result
What was completed.

### Files Changed
Key files only.

### Verification
Tests or checks performed, including failures or unverified items.

### Project Model Impact
`NONE | MINOR | UPDATE | UNCERTAIN`

Reason:
<short explanation>

### Risks / Follow-up
Remaining risks, assumptions, or next steps.

## CORE RULE

Code provides implementation facts.
Project Model stores confirmed project cognition.
AI proposes.
Humans confirm.
# ProjectMind 团队开发流�?

这份文件只给人看。目标：我们按同一套最简单的流程开发�?

## 一次任务怎么�?

### 1. 先建任务
�?GitHub Issue 写清三件事：
- 要做什�?
- 谁来�?
- 做到什么算完成

例：
> 实现本地 Git 项目导入。能选择一个仓库并读取基础信息，导入失败时有提示�?

### 2. 开自己的分�?
不要直接�?`main`�?

命名�?
- 新功能：`feat/任务�?名字`
- �?Bug：`fix/任务�?名字`
- 文档：`docs/任务�?名字`

例：
`feat/12-project-import`

### 3. 开�?
可以使用任意 AI 辅助�?

要求只有三条�?
- 只做当前任务，不顺手大改别的东西
- 重要阶段及时 commit
- API Key、密码、Token 不上�?

### 4. 自己先检�?
提交前确认：
- 功能能不能跑
- 有没有明显报�?
- 有没有误改无关内�?
- 这次修改会不会改变“项目地�?/ Project Model�?

### 5. �?PR
PR 就是“我做完了，请合进正式版本”�?merge)

写清�?
- 做了什�?
- 怎么验证
- 是否影响 Project Model
- 还有什么没解决

### 6. 检查后合并
另一名队员简单检查�?not must)
没问�?�?合并�?`main`�?

合并后临时分支会自动删除�?

---

## Project Model 什么时候要�?

只问一句：

> 这次代码修改，有没有改变“这个项目由什么组成、模块负责什么、模块之间怎么联系”？

- 没有 �?不改
- 只是模块内部实现变化 �?可记一条变化，不改结构
- 新增/删除/拆分/合并模块，职责或重要依赖变了 �?要改
- 拿不�?�?交给人讨�?

---

## 团队统一原则

1. `main` = 当前正式版本
2. 一个任务一个分�?
3. 做完�?PR
4. 团队决定正式架构
5. Project Model 发生重要变化时必须由人确�?
6. 能不用大模型解决的事情，不强行烧 Token

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git rev-parse HEAD 78c2751 53f3580; git status --short; git log --oneline 78c2751..53f3580; git diff --stat 78c2751 53f3580; rg --files docs | rg 'CONVER|[Cc]onver|MVP|COLLAB|[Cc]ontract|[Cc]riteria|[Aa]ccept'" in G:\jiagou\projectmind-c-convergence
 succeeded in 530ms:
53f3580bf2af1738bd0b8d6e443e83ff1d57736c
78c2751c174bcdd8db586f160f61f9c66357cc5d
53f3580bf2af1738bd0b8d6e443e83ff1d57736c
53f3580 convergence: P05/P05B real CA integration + typed consumption (T1/T2/T3)
2c69093 convergence: P04 real B integration — real collector in pipeline (no mock verdict)
43255b8 convergence: P02 mutation gap closure — bind no-attach and AST-domain-proof invariants to real candidates
98c3a00 convergence: P01 relation channel — AST base/target set diff replaces patch-regex signals
 extensions/map_proposal/ca_adapter.py | 138 +++++++++-
 extensions/map_proposal/engine.py     |  16 +-
 extensions/map_proposal/relations.py  | 413 +++++++++++++++---------------
 tests/audit_probes.py                 | 243 ++++++++++++++++++
 tests/audit_w3_adversarial.py         | 151 +++++++++++
 tests/test_real_b_integration.py      | 325 ++++++++++++++++++++++++
 tests/test_real_ca_integration.py     | 458 ++++++++++++++++++++++++++++++++++
 tests/test_w3_relations.py            |  93 ++++++-
 tests/test_w4_ca_trust.py             |  51 +++-
 9 files changed, 1664 insertions(+), 224 deletions(-)
docs\standards\MVP_INTERFACES.md
docs\standards\MVP_CONTRACT_EXAMPLE.json
docs\standards\COLLABORATION_CONTRACT.md

2026-10-04T17:18:11.556904Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
2026-10-04T17:18:20.693184Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Encoding utf8 docs/standards/COLLABORATION_CONTRACT.md; Get-Content -Encoding utf8 docs/standards/MVP_INTERFACES.md; git diff 78c2751 53f3580 -- extensions/map_proposal/ca_adapter.py extensions/map_proposal/engine.py; rg -n 'C-3|invariant|F06|S30|convergence|收敛' docs extensions/map_proposal tests" in G:\jiagou\projectmind-c-convergence
 succeeded in 375ms:
# ProjectMind ����Э��Լ���������棩

> ״̬��2026-09-29 ��**ʵʩԼ���᰸**�����Ŷ���顣��Լ��������Э����ʽ������׼���ڲ�Ʒ�ܹ�����ʽ Project Model��ԭ�� MVP �Ĺ̶���� [�������](../audits/2026-09-29-mvp-audit.md)����������Ķ�����չ��ڼ� [�ӿ�Լ��](MVP_INTERFACES.md)����������ȷ�ϵĲ�Ʒ���������ڱ��᰸�������Ƿ������ָ�� Git �ύΪ׼��

## 1. ��ͬ����������Ϣ���Ŷ�

�����汣��һ��ÿ������е�·������**�˹������Ĺ���ͼ**�����鿴ָ�� Git �ύ��Ĵ���֤�� �� ������ܿ�ְ����ڡ���ϵ��֤�� �� �Ƚ�������ʵ�ύ �� �����Ҫ���˵Ĺ��� �� ��ѡ AI ��ѡ���� �� ��������һλЭͬ�ߡ��ļ���֤�ݣ���ռ��ͼ��Ҫ���򡣵�ǰ�˹���ͼ�ӱ����ļ���ȡ����δ������ύһ��̶��汾�����Ǳ�����Ʒ��ֵ�ȱ�ڣ������ϵĴ����ύ�Ų���֤��ͼ�����õ����ύ���϶���Ĳ���ֻ�Ǳ�����ʱ��������ʽ�ܹ�ͼ���䡰�˲����õ��ĸ������ύ����δʵ�֡�

ÿ�����û��� Agent չʾ����ϢҪ����������������֮һ��

| ���� | ������˵�� | ��Ϊ��ʽ��ʵ������ |
|---|---|---|
| ������ʵ | ���ύ X ��������ļ�/��ڡ���Git ��ʾ�ļ��ѱ仯�� | �ܰ��ύ��·�����飻���� AI �²� |
| ��ѡ���� | ��������ĳ���ܡ�������仯ֵ�ø��ˡ� | ʼ�ձ�����ѡ��ǡ�������δ֪�� |
| �ŶӾ��� | ���ù��ܸ���ʲô�����ӿ���γ�ŵ������ʽͼ���õ� X�� | �� `AGENT_STANDARD.md` ����ȷ�ϣ���׼����汾Ҫ���� |

ԭʼ��Ʒ��ͼ�����ϸ��� `projectmind-model/docs/PROJECT_ANALYSIS.md`���������� Master Spec ֻ�� AI �ݸ塣������ʵ�Ա��ֿ�ָ���ύΪ׼����������ì��ʱ�� Issue/PR д����ԭ˵��������λ�á������޶�������Ҫ���ĸ�д��ƷĿ�ꡣ

## 2. ����ǰ��ͬ����

1. ÿ���õ�һ�� Issue���û��ܿ����Ľ�����������ղ��衢�����ˡ������Ԥ�ƸĶ��ļ���û�� Issue �ŵ���ʱ�޸����ȱ��漯���ˣ��ٲ��ǡ������޸������������ġ���ͼ�汾����ȱʧ���͡�AI ���δ���뽻�ӡ�����ȱ�ڡ�
2. ����ȷ����ͬ��**��׼�ύ���� SHA**�͹�ͬ������ڡ���ǰ������ʵ��λ�������� PR #6��#8��#10��#12��#14��#16��`main` Ŀǰ��û����Щ��Ʒ���롣�ӿ�Լ���� `docs/17-mvp-interface-contract`��������չ���������� `feat/19-extension-seams`��**B/C/D Ҫʹ�ö�����չ�ڣ��ʹ� `feat/19-extension-seams` ��ͬһ�ύ����֧��PR ���Ը÷�֧Ϊ base**��������֧���κ���󣬵��� PR base��������Ʒ PR ������ `main` ���ٴ� `main` ���·�֧����Ҫ�ѡ�PR �Ѵ򿪡�˵�ɡ�main ���й��ܡ���
3. ʹ��ͬһ�� [�ӿ�Լ��](MVP_INTERFACES.md)�����Ե� Codex �ȶ� `AGENTS.md`����� Issue���ӿ�Լ���������漰���ļ�������Ҫÿ��ȫ�����¸�����
4. ��ȷ��Ӵ����ļ�������Ҫ��ͬһ�ļ�ʱ��Լ��һ�������ˡ���ǰ��֧���� [������չ���](EXTENSION_INTERFACE.md)��B/C/D �����ύ `extensions/<������>/` �����ԣ�������������ҳ�������ݽӿ��Զ����֣����� A �޸� `app.py` ����ǰ�ˡ�B/C/D ��ҵ������ֻ�����ĵ����齻�ӵ㣬�������ʵ�֣���Ҫ�����Ƕ�����й���ͼ������ A �Ĺ������ߡ�

## 3. ���˵�������ӿڽ���

����� A/B/C/D ��**����λ**��������Ա������ÿ�˿ɶ����� Codex ��һ�������֧���������ٽ���һ�������л����ù̶�������֤����������������ֻ�������� Issue����������������ͨ����ϸ�ڡ�

| ����λ | �������������׸����� | ����λ�� | ���������˵�����/��� | ���� |
|---|---|---|---|---|
| A������������ | ��������ͼ�����顢�Ƚϡ�����ͬһ��ڿ����У��˲���չ������������� | `app.py`��`web/`��`README.md` | ���� `Snapshot`��`Comparison`���������й���ͼ�빫��·�ɸĶ� | ��ǰ�����з�֧����ͼ������ B/C/D ���ʱ���������� |
| B��������ʵ | ��ѡ�� Git �ύ��ȡһС����ʵ��ڼ�·��������ɺ˲� JSON�������Թ���ְ�� | `extensions/code_facts/`��`tests/test_code_facts.py` | `repo + revision + ��ѡ·��` �� `CodeFacts`���Լ�����չ�ӿ�/ҳ�棻���ӿ��ĵ� | �������ò��Բֿ⿪�������� C |
| C����ѡ���ܽṹ | �ù̶������Ĵ�����ʵ���˹�ͼ������������ܽڵ�/��ϵ��ѡ����ʾ���ݺ�δ֪���������˹�ͼ | `extensions/map_proposal/`��`tests/test_map_proposal.py` | `Snapshot + CodeFacts` �� `MapProposal`���Լ�����չ�ӿ�/ҳ�� | ���ղ��� B����ʵ����� B ���׸���� |
| D��Эͬ���������� | �õ�ǰ `Snapshot + Comparison` ���ɿ�����һλ Agent ���˵ļ�̽��Ӱ������ɷ����߸�����ʾ | `extensions/handoff/`��`tests/test_handoff.py` | `Snapshot + ��Դ + Comparison? + AI ��ѡ?` �� `Handoff`���Լ�����չ�ӿ�/ҳ�� | �����������нӿڿ��� |

**��ֹ�ѷֹ���������󼯳��ĸ���顣** A �ӵ�һ��ͱ�ס�������ߣ�B/C/D ÿ���ύ�Լ��Ŀ�������չ��̶��������������A ÿ����֤����ڼ�ԭ���ߡ�ĳ�����ʧ��ʱ����ǰһ������а汾��Issue д���������롢����������л�����D ������ӹ���Ӧ������ֻƾ�����������У������½�������������������һ�����飬���� Issue ���������Ŷ����룻�������� B/C/D ҵ�����Ѿ�ʵ�֡�

**��ֱ����ȡ���������񿨣����Ե��� Issue/PR����**

1. **A����ͼ��Դ�ܱ������������ڴ����ύ��** �ӵ� 2 ��Լ���Ĺ�ͬ���߿���֧����������������ʾ����ͬһ���� SHA �¸Ķ�һ���˹���ͼ������ˢ�£������뵼���������÷����߿�����ͼ�ļ������ѱ仯����ͼ�Ƿ��ѱ��ŶӺ˲�Ϊ UNKNOWN������ֻ��ʾ���� SHA���ȽϽ����������һ�ݵ�ͼ���㣬��ʾ���»�ȡ���ա���дһ����ʧ�ܵĹ̶��������������С�Ķ��������ļ� `app.py`��`web/`��`tests/test_app.py` ���� A ���ߡ�����һ�δӸɾ���֧�ɸ��ֵ�����������������ǰ������
2. **B����ʵ�ύ�е������ʵ��** �� `extensions/code_facts/` ʵ�ֽӿ��ĵ��� `collect_code_facts` ���Լ��� `handle`/ҳ�棬����ֻ�� `tests/test_code_facts.py`������ʱ Git �ֿ��ύһ����֪���룬������ SHA �󷵻ظ��ύ����ʵ��·������������кţ����޸�δ�ύ������������Ա���ԭ�ύ��ʵ��δ֪���Խ��� `skipped`�����¹���ְ���ύ HTTP ���������ʹ������������� `app.py`����ǰ������
3. **C����ѡ����˵����** �� `extensions/map_proposal/` ʵ�� `suggest_map` ���Լ��� `handle`/ҳ�棬����ֻ�� `tests/test_map_proposal.py`����ʹ�� [�̶���Լ����](MVP_CONTRACT_EXAMPLE.json) ���������һ���� `evidencePaths` �� `unknowns` �ĺ�ѡ���汾��һ�»���֤��ʱ������ȷʧ�ܻ�ս���������˹�ͼ�����ÿɿ���Ӧ��֤�������ƣ���ʵģ�͵��������м�¼��������ǰ������������ʵ������ʵʱ���� B ���׸������C ���� `app.py`������ `web/` �� `data/project-map.json`��
4. **D����һλ Agent �ܼ��������Ľ��Ӱ���** �� `extensions/handoff/` ʵ�� `build_handoff` ���Լ��� `handle`/ҳ�棬����ֻ�� `tests/test_handoff.py`���� [�̶���Լ����](MVP_CONTRACT_EXAMPLE.json) �еĿ��ա��������ṩ�Ĳֿ���Դ�ͱȽϽ������ȷ���� SHA����ͼ�汾 UNKNOWN���仯·���������˽ڵ��֤�ݣ���ѡ AI ��ѡ��Ϊ�������벢����δ֪���һ������ֻ�����Ӱ���Ӧ��ָ�����ֿ����ȡ�á������Ӧ�ĸ��ύ����ͼ�Ƿ��Ѻ˲顢�ĸ��ڵ�����ˡ���һ��ȥ�ĺ˲顱��D ��������·�ɣ��������Լ���ҳ���ṩ���ء���ǰ������

���� 1 �� 4 �����������Ƶ�ʵ��ȱ�ڣ����� 2 �� 3 ��չ�Զ��������������������ǵ�ǰ���ߵ���С��Ƭ����һλ Agent Ӧ�ڸ��� Issue �м�¼�ύ�����գ�����������ȫ���Խ�������ȫ��֪ʶͼ�׻���ʽ�ܹ���顣

## 4. ��֧��PR �ͼ��ɽ���

���� [TEAM_SOP](TEAM_SOP.md) �� Issue �� ������֧ �� �Լ� �� PR �� ��һ�˼�顣ÿ�� PR ֻ��һ������֤����Ϊ����ͬ��Ҫ�Ĳ��Ի�̶������������ڿ������� Draft PR ���������翴��һ���˵�����Ҫֱ�Ӹ���һ�˵ķ�֧����д����ʷ��

ÿ��̶�һ�μ��ɼ�飺��¼��ͬ��׼ SHA�����ν�����ͨ�����յ� PR���ɷ����ߴ�����˵����������ͨ�������ߣ���ʵ��ͨ��/ʧ�ܵĲ��衢�ύ���������� PR�����˹�ͬ�޸� `app.py`����ͼ JSON ��ͬһǰ���ļ�ʱ�� A �����ϲ�˳�����ڸ��Է�֧���� base �ٽ����ͻ�������á������ҵİ汾��������һ�˵Ĺ��ܡ�PR ��������֧���������ָ�� base��������� PR �Ĳ��������

����� `main` ���� PR �������Ͳ��Լ�飻�ֿ����Աʵ������ǰ����ֻ�ǽ��飬�����ƹ��������á����˶����̽�������**һλ������**�����漰�����ӿڡ���ʽͼ����ʾ���ߵ� PR�������İ�Ҳ��˶�ʵ��״̬��ʧ�ܵļ�顢δ�˶Ե� AI ������޷����ֵ���ʾ���ܵ��������ա�С PR ���ڼ�ʱ���ͼ��ɡ�[GitHub �ܱ�����֧](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)��[Google ��С�Ķ�������](https://google.github.io/eng-practices/review/developer/small-cls.html)��

## 5. �ӿڱ���취

���нӿ���ʵ�� [MVP_INTERFACES](MVP_INTERFACES.md) �� `IMPLEMENTED` С�ںͶ�Ӧ����Ϊ׼��`PROPOSED` С���ǹ����˲��е���С����Լ�����з����й��ܡ��ӿڰ����ֶΡ���Դ�ύ���ɿ�����������ʽ���������ƣ���ֻ�Ǻ�������

�����Ѿ����������ѵ��ֶ�/����ʱ������ Issue/PR д��������������������������Ӱ������ߡ�Ǩ���������ȸ��ɵ����߿ɼ��ݵĹ��ɣ����� A ���½��ߺͲ��ԣ�����������ͨ��ͬһ�̶���������Ƴ�����ʽ����չ��ѡ�ֶ�ҲҪ˵��Ĭ��ֵ��`nodeId` ��һ��ͼ��Ψһ���ȶ���֤��·���ǲֿ������·�����汾���������� Git �ύ SHA����ͬ�ύ�����ݲ������Ļ��á����ܰѺ�ѡ����д����ȷ��ͼ��

## 6. ��顢�����뱣��

- ÿ������������һ���û�·����̶������ܱ�**������**���֣��ؼ�����·��Ҫ�������ʧ�ܡ�B �Ĵ�����ʵ����ʵ��ʱ Git �ֿ�����֪�ύ�˶ԣ�C �ĺ�ѡ���뱣��֤�ݺ�δ֪�D �Ľ��Ӱ������ñ����ҵ�ͬһ�ύ��
- ÿ�� PR д��Ŀ�ꡢʵ�ʱ������֤����ͽ����Project Model Ӱ�� `NONE/MINOR/UPDATE/UNCERTAIN`��δ������⡢�������� PR �ͶԽӿڵĸĶ�����Ӱ��ְ��/��ϵ/��ʽ���ð汾��ֻ�������飬���� Agent ֱ�Ӷ��塣
- ÿ�ս�������д��Issue/����λ����֧������**����**�ύ SHA�����õ�ͼ�ļ����䵱ǰ�汾״̬��Ŀǰδ�̶�ʱд UNKNOWN�������ڿ���ʾʲô����ʲô���踴�֡��ӿ��Ƿ�仯��ʧ��/δ֪/��һλ������ڡ���Ҫֻд����� 80%�����������ܽᡣ
- API Key��Token ������ֻ�ű�������������PR����ͼ����־�͵������������ܡ�AI ����ֻ����ǰ�����Ҫ��֤�ݣ����ⲿģ�ͷ���������ǰ���ŶӼ��й������Ƿ���������ǰ `/api/explain` �ǰ�ѡ�нڵ�����޲�����ã������Զ�ȫ�����⡣
- ������ʾ�زı�������ʵ�����У�������Ӧ�ύ����ʵ��ͼ���ɸ��ֲ��輰 AI ��������״̬��Unity �ֿ�ֻ���������ⲿ��������֤�����ڲ���ȡ��

## 7. ���õȴ�����������ͶƱ������

�����ڲ���֯��������ʱ�ֿ⡢ͼ��ʼ���ꡢ�����İ��������������˾������� PR ˵����ֻ�л�ı�**��Ʒ��ŵ���Ŷ���ʽ�ܹ�������˭����׼Ȩ**��������ύ������/�Ŷӣ����д������嵥�� `projectmind-model/docs/TEAM_REVIEW_QUESTIONS.md`���ѷ��ֵ�����д�ɾ������Ӻͽ��飬�����ĸ��˷ֱ�ƾ AI ��һ�״𰸡�

## ���������÷�Χ

��Լ�������� [TEAM_SOP](TEAM_SOP.md) �䵽����������Э�����ⲿ����ֻ���ڲ������ϸ�ڣ�[GitHub �� PR �� Issue ����](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)��[PR ģ��](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)��[���븺����](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)������������ GitHub Ȩ����δ��ʵ������ݲ�д `CODEOWNERS` ��ٳ������÷�֧������
# ��������С�ӿ�Լ��

> ԭ�� MVP �ĺ˲����Ϊ `feat/15-local-repo-input` �� `8a6a19c`��������չ����ں��� `feat/19-extension-seams` ��֧ʵ�֡�**IMPLEMENTED** ��ʾ��Ӧ��֧���ܴӴ�����֤����Ϊ������ʾ�Ѻ��� `main`��**PROPOSED** ��ʾҵ�������Դ�ʵ�֡��ӿڲ����Ǻ�����������������Լ������Դ�汾�����󡢵���˳��ͽ�����ʡ����Ĳ����峤�� Project Model Schema��

## ��ͬ�ʻ��벻����

- **���ܽڵ�**�ǵ�ͼ�����������Ŀ���֣�`node.id` ��������ͬһ��ͼ��Ľڵ㡣����ǿ�Ƶ����ļ���Ŀ¼������ package ��ĳ���ࡣ
- **����汾**Ϊ Git �������ύ SHA����ǰ������� 40�C64 λСдʮ�����ƣ���`HEAD` ֻ���ڷ���˶�ȡ��ǰ״̬ʱ���������˽��Ӻ��ѱ������һ�ɷŽ���������� SHA�������ױ�� `HEAD`��**��ͼ�汾**��ǰû�е������ύ ID ��ժҪ����ͼ����ʱ�����ļ���ȡ��`Snapshot.revision` ��֤������֤�ݵİ汾������֤����ͼְ����ϵ���ڸ��ύ�������벹��ͼ������˲�״̬��
- **֤��·��**�ǲֿ������·����ʹ�� `/`����ͬ���ֵĲ�ͬ���زֿⲻ�ܽ���Ŀ¼������ͬһ�ֿ⡣��ǰ��Ӧֻ�� `repository: repo.name`�����޿�����ȶ��ֿ� ID���Ŷӽ�������д�ֿ��ַ/��Դ���ݲ���Ŀ¼�������ݼ���
- **����**���������˹���ʾͼ `curated_demo`��`ai_candidate`��`temporary_unconfirmed_draft` �뽫����������ʽͼ��Git �仯ֻ�ܲ����������ˡ������ܲ������ܹ��ѱ仯���Ķ��ԡ�
- ֤�ݺͱȽ�ʹ�����������ύ����ͼ��ǰ����δ�̶��ı����ļ�״̬������ʱӦ��ȷд `mapRevision: UNKNOWN`���� `Comparison.targetRevision` �� `Snapshot.revision` ��ͬ�������������»�ȡ����ȷ��ʾ����汾��һ�¡�

## IMPLEMENTED����ǰ�Ѵ��ڵĶ�д���

������Python 3.10+��`python app.py` �ڱ��� `127.0.0.1:8765` �ṩ���棻`python app.py --repo <���� Git �ֿ����·��> --map <�˹������ĵ�ͼ JSON ����·��>` ����ָ����һ�����زֿ⡣�ⲿ�ֿ����ͬʱ�� `--map`����ǰ�����Զ�����ͼ������ʱ�����ֿ��Ŀ¼��У���ͼ����Ч����ʹ����ʧ�ܡ��Դ��� `app.py` �� `resolve_sources` / `load_map` Ϊ׼��

### ��ͼ���������

�˹���ͼ�ļ����㣺`note: string, nodes: Node[] (���� 1 ��), edges: Edge[]`��ÿ�� `Node` ���� `id/title/summary/entryPoint: string`��`position: {x:number,y:number}` �Ǹ������ޡ�`evidence: [{path:string,reason:string}]`��`id` ��ͼ��Ψһ��`Edge` ���� `from/to` ָ����֪�ڵ� `id`��`label:string`����ǰУ�鲻��֤ `evidence.path` ����ڣ����ջ��� `existsAtCommit` ���档����**�����ʽ**����������׼����ʽ�ܹ���ʽ��

`GET /api/snapshot` �� HTTP 200 JSON��

```json
{
  "repository": "�ֿ�Ŀ¼��",
  "revision": "���� Git SHA",
  "parentRevision": "���� Git SHA �� null",
  "branch": "��ǰ��֧���� detached HEAD",
  "mapOrigin": "curated_demo",
  "mapNote": "�˹���ͼ��ע",
  "nodes": [{
    "id": "���ܱ�ʶ", "title": "������", "summary": "ְ������",
    "entryPoint": "�˹���¼�Ĺؼ����", "position": {"x": 20, "y": 54},
    "evidence": [{"path": "app.py", "reason": "Ϊ�����", "existsAtCommit": true}]
  }],
  "edges": [{"from": "���ܱ�ʶ", "to": "��һ���ܱ�ʶ", "label": "��ϵ˵��"}]
}
```

`entryPoint` ��ְ��Ŀǰ����**��ǰ�����˹���ͼ**�����ܽ�ƾ `existsAtCommit` �������ȷʵ���ڡ���ϵ�ѱ�����֤�����ͼ�Ѿ��˲����õ� `revision`��`parentRevision` �ڳ�ʼ�ύ����Ϊ `null`��

### Git ֤����汾�Ƚ�

`GET /api/evidence?path=<���ڵ�ͼ��������·��>&revision=<����SHA>` �� `{path, revision, content, truncated}`����������ָ�� Git �ύ������ȡ������δ�ύ�ı�����ǰ�����ʾ 12,000 ���ַ���·��δ�ڵ�ͼ���� �� 400���ڸ��ύ��ȱʧ �� 404���������ȴӿ���ѡ·���� `revision`�����ܰѹ������������ύ���ݻ�д��

`GET /api/compare?base=<����SHA>&target=<����SHA>` �� `{baseRevision,targetRevision,changes,reviewCandidates,note}`��`changes` ÿ��Ϊ `{code,path,oldPath?}`������������ԭ·����`reviewCandidates` ÿ��Ϊ `{nodeId,changedEvidencePaths}`����ѡֻ��ʾ��ͼ������֤��·���� Git �仯·��ƥ�䣻û��ƥ�䲻֤���ڵ�δ��Ӱ�졣�ͻ����豣֤Ŀ���ύ�����ڿ��Ŀ���һ�£�����ʾ�û�ˢ�¡���ǰ�Ƚϲ��ǻ���ʽ���·�����Ҳû������ʡ Token��

`GET /api/export?revision=<����SHA>&base=<����SHA����ʡ��>` �� ���ύ��Ϣ�� Markdown ���أ����ṩ base�����Ƚ�ժҪ���˳����ǽ���ժҪ��������ʽͼ��⡣

### ��ѡ AI ����ʱ����

`GET /api/ai-status` �� `{configured:boolean, model:string|null, note:string}`��ֻ���ڷ�������� `OPENAI_API_KEY` �� `PROJECTMIND_AI_MODEL` �ſ��á�

`POST /api/explain`��`Content-Type: application/json`��JSON `{base:<����SHA>, target:<����SHA>, nodeId:<���սڵ�ID>}`�������嵱ǰ������ 2,048 �ֽڡ��ɹ� �� `{status:"ai_candidate",model,nodeId,baseRevision,targetRevision,changedEvidencePaths,diffTruncated,explanation,note}`��`explanation` �� `summary:string, observations:string[], possibleEffects:string[], unknowns:string[], evidencePaths:string[]`��ֻ�Խڵ������ұ��α仯��֤��·��ȡ���죬����ģ�͵Ĳ������ 12,000 �ַ���`evidencePaths` ֻ��������Щ·����δ���á�ģ�Ͳ����û򷵻ز���Լ��ʱʧ�ܣ���Ӧ��ʾΪ��ȷ�Ͻ��ۡ���ǰʵ�ֿ��Զ�����֤������״����δ�ڱ�����ʵ�����ⲿģ�͡�

ͬһ�����ڱ��� Python ��ɵ��� `explain_change(repo, map_path, base_ref, target_ref, node_id) -> dict`���н� Git �����ں����ڲ����졣��**����**�ɸ��õ�ͨ�� `build_change_context` ģ�飺�� B/C/D �븴�ò��췶Χ���Ȱ���ǰ�ӿڵ��û����С����ȡ PR���� A ���𹫹����ߣ����ܸ��Ը���һ�� Git ѡ�����

ǰ�ˡ�������ʱ���֡�д��ǰ������� `localStorage`��������ͼ�ݸ� JSON���õ� `{status:"temporary_unconfirmed_draft",note,exportedAt,repository,revision,mapOrigin,nodes,edges,comparison?}`��`nodes` �� `position` ���϶���λ�ã������ı�ְ�𡢽ڵ���ϵ��Ҳ���Զ�д�� model �ֿ⡣`comparison` Ϊ JSON ����� `null`��**��ǰ�������� AI ���ͣ�Ҳ����������ͼ�汾**����һλЭͬ�߲��ܽ�ƾ���������� AI ���ۡ�ͬ�����زֿ⵱ǰ���ܹ��ò��ּ�����˶�ֿⲢ��ʹ��ʱ�踴�˵������ݣ����Ǵ���ȱ�ڣ���Ӧ�Ѹü�����ֿ����ݡ�

��ʱͼĿǰ**û��Ӧ���� AI ���ӿ�**���û����԰ѵ����� JSON ���� AI ����ѷ��������ⲻ���� ProjectMind ���Զ��ȽϷ�����ʶ���ͻ�򱣴��������

HTTP ����ǰͨ��Ϊ `{error:string}`��400 ��ʾ���벻��Լ����404 ��ʾȱʧ·��/ҳ�棬AI �������Ϊ 502������ Git/�ļ�����Ϊ 500��������Ӧ���� HTTP ״̬���������������Ĵ����İ����������ݣ�ʵ�ָ�·�ߵľ�ȷ������ `app.py` �� `make_handler` Ϊ׼��

### ������չ���

��ǰ��֧��ʵ�� `extensions/<������>/extension.py` ���Զ����֡����� HTTP ������ںͿ�ѡ����ҳ�档����һ����չֻ���޸��Լ���Ŀ¼�����ԣ�������������ҳ�����Զ�������ڡ����顢������Ϊ�������� [������չ�ӿ�](EXTENSION_INTERFACE.md)�����ǹ��ܽ��뷽ʽ��B/C/D ��ҵ����������ֱ�ʵ�ֺ����գ��������Զ��޸��˹�����ͼ��

## PROPOSED����һ��������������С����Լ��

�����ֶ�ֻΪ��ǰ���˲��з��񣬲��� Master Spec ���Ĳ�ģ�ͻ����� Schema�������˲������ֶξ�����ͨ����ϸ�ڣ�ʵ������Ҫ���׸� PR �̶������ʹ�����Ϊ��B/C/D �ֱ����Լ�����չĿ¼��ʵ�ֹ��ܡ�ҳ���� HTTP ������ڣ���Ҫ�ѽ��Ƕ��������ͼ������ A �����������档

**����״̬��ͨ����չ·����ҳ������Ѿ�ʵ�֣����� B/C/D ��ҵ���������᰸��** ��ʵ�ֵ� `Snapshot` �� `Comparison` �ǿɶ�ȡ�� JSON �����档B/C/D ������ [ͬһ�ݺϳɺ�Լ����](MVP_CONTRACT_EXAMPLE.json) ������������֤�����ļ�ֻ���ڲ��Խ�����״���������ֿ�����ʵ���� `src/entry.py`���������Լ�ʵ�� `handle` �������Լ���ҵ����������·�ɵ���Ӧ�ֶ��뱣��������ȷ�ṩ���ݹ��ɡ�

### A����ͼ��Դ�����������һ����

�� `Snapshot`��`Comparison` �����ֵ���������ͬ����ĵ�ͼ���ݣ����� `mapSource: {kind:"local_curated_file", digest:"sha256:<64λժҪ>", confirmedForRevision:null}`��`digest` ����Ա���ʵ�ʶ�ȡ�ĵ�ͼ�ֽڼ��㣻`confirmedForRevision:null` ��ʾ�Ŷ���δ�˲����ð汾��**��ʹ��ͼ�ļ�ǡ�ô��ڴ���ֿ���Ҳ�����Զ��ĳ��ύ SHA**���Ƚϻ�����һ�ݵ�ͼ����ʱ�����ɼ�����ʾΪͬһ�ο��յġ������˽ڵ㡱��A ���÷���˷��ز�ƥ����󣬻��ý���ǿ��ˢ�²���ʾ�������� A �� PR �̶���`Snapshot.revision` ��ֻ��ʾ�����ύ���˲������׸������ǡ�ͬһ���� SHA���ĵ�ͼ���� �� digest �ı����û�������ͼ״̬���������ǰ�����ʽ model �ֿ��ʽС�öࡣ

### B��`collect_code_facts(repo, revision, paths=None) -> CodeFacts`

���룺�ѽ����ı��� Git �ֿ��Ŀ¼�������ύ SHA����ѡ�Ĳֿ����·���б����������Ϊ��

```json
{
  "revision": "���� Git SHA",
  "files": [{"path": "app.py", "language": "python", "entries": [
    {"name": "build_snapshot", "kind": "function", "line": 106}
  ]}],
  "skipped": [{"path": "unknown.bin", "reason": "δ֧�ֻ򲻿ɶ�ȡ"}]
}
```

`entries` ���ڸ��ύ���ܺ˲�Ĵ�����ʵ������Ϊ�գ�`line` �Ǹð汾�� 1 ��ʼ�кš��װ��ֻ֧��һ������ʾ�ֿ�ʵ��ʹ�õ����ԣ������ļ����� `skipped`������Ϊ����ͼ�����캯��������·�������ڡ��ύ��Чʱ����ȷ���󣬲��ں�̨͵͵��ȡ��ǰ��������������������жϡ�����ģ�顱����ȫ������ͼ��B ��һ����ʱ Git �ֿ����֪�ı����������ա�

### C��`suggest_map(snapshot, code_facts) -> MapProposal`

���룺ͬһ�ύ�� `Snapshot` �� `CodeFacts`���� SHA ��һ�£��ܾ����ɡ��������Ϊ��

```json
{
  "status": "ai_candidate",
  "revision": "���� Git SHA",
  "candidates": [{"title": "��ѡ����", "summary": "����", "evidencePaths": ["app.py"], "unknowns": []}],
  "note": "���˸��ˣ��������˹���ͼ"
}
```

����ɸ�һ���ȶ��ġ����ݵ�ǰ�˹��ڵ�ʹ�����ʵ�����ѡ˵���������ӣ���Ҫ���Զ��������ּܹ��������� LLM��������ʽ���á��������롢����δ֪�`evidencePaths` �����������ʵ·����ѡ����û���㹻���ݣ����ؿ� `candidates` ��ԭ��C ���ñ��Ĺ̶������������ԣ�B ������ú�����������ѡ����д�� `data/project-map.json` ����ʽ model �ֿ⡣

`status:"ai_candidate"` ֻ����ȷʵ����ģ�����ɵĽ����C ���տ��ÿɿ�ģ����Ӧ��֤�ӿڣ��޿���ģ��ʱ������ȷ��δ����״̬�����ù�����ð�� AI���Ժ������Ӵ������ѡ���������ɷ�ʽ��

### D��`build_handoff(snapshot, source_locator, comparison=None, ai_candidates=None) -> Handoff`

���룺��ǰ `Snapshot`����ȷ�ṩ�Ĳֿ���Դ `source_locator={kind:"git_remote"|"local_path",value:<�ǿ��ַ���>}`����ѡ `Comparison`���Լ���ѡ�� `/api/explain` ԭ���ɹ�����б����Ƚ�Ŀ�������ǿ��� SHA���ܾ�����ʽ���ز�ƥ�䡣��ǰ `Snapshot.repository` ֻ��Ŀ¼���������������������һ̨�����򿪵ĵ�ַ������·��������ĵ���ʱ���ܲ����ã��������밴 `kind` �жϡ����������״��

```json
{
  "status": "handoff_draft",
  "repository": "�ֿ�Ŀ¼��",
  "sourceLocator": {"kind": "git_remote", "value": "�������ṩ�Ĳֿ� URL"},
  "codeRevision": "���� Git SHA",
  "mapRevision": "UNKNOWN",
  "mapOrigin": "curated_demo",
  "nodes": [{"id": "���ܱ�ʶ", "title": "������", "evidencePaths": ["app.py"]}],
  "changes": [{"code": "M", "path": "app.py"}],
  "reviewCandidates": [{"nodeId": "���ܱ�ʶ", "changedEvidencePaths": ["app.py"]}],
  "aiCandidates": [],
  "unknowns": ["��ͼ��δ��Ǻ˲����ð汾"],
  "nextCheck": "�������ύ��֤��·������"
}
```

û�бȽ�ʱ `changes`��`reviewCandidates` Ϊ���б������� AI ����ʱ `aiCandidates` �б���ԭ `status:"ai_candidate"`����Դ·���� `explanation.unknowns`������ƾ�����ɡ�A ��ɵ�ͼ���ݲ�����`mapRevision` Ӧ����Ϊʵ�� `mapSource`����δȷ�����õ�״̬�Ա��������ü���û����Դ�ġ���ʽ�ܹ���ȷ�ϡ�������D �÷��������»Ự������ش𡰴���֤�ݶ�Ӧ�ĸ��ύ����ͼ�汾�Ƿ��Ѻ˲顢�ĸ��ڵ�����ˡ���Ϊ���գ�D �����Լ���չҳ���ṩ�������أ���Ҫ����������ͼ������ť���� A �޸Ĺ������档

### �����᰸��`review_draft(draft, reference_snapshot) -> DraftReviewCandidate`

�����ŶӾ����ѡ������� AI ����������Ӧ����ʱʵʩ������Ϊ������ `temporary_unconfirmed_draft` �͹����յĵ�ǰ���գ��ȼ��ֿ���Դ�������ύ���ͼ״̬�Ƿ�ɱȡ�������� `ai_candidate`�������г�**�ɴ�����ͼֱ�ӹ۲�Ľڵ�/��ϵ����**�����ܺ����֤�ݽڵ� ID �Ͳ����ж�֮�����Բ�һ�°汾�ȷ��ء����ɱȽϡ������ܰ���ʱ�϶�λ�õ��ܹ������ı䡣����д��ʽͼ����ǰû�����������HTTP ·�ɻ����������ˣ����ܰѴ��᰸���� C ��������������

## �Ķ�������

ÿ������ģ��� PR ���Ϲ̶����롢ʵ�����������������ֻ��Թ����ӿڵı�Ҫ���Ժͽ��뷽ʽ���ֶκ����汾Լ���ı�ʱ�Ȱ� [Э��Լ��](COLLABORATION_CONTRACT.md#5-�ӿڱ���취)֪ͨʹ���ߣ���չ·�ɰ���ʵ�ֵ�Լ���Զ����룬B/C/D ��ҵ��ӿ�ͨ�����պ�Ÿ��±��ļ��� `IMPLEMENTED` ״̬����ǰ��ʵ�ֳ��ڲ�����Ϊ���᰸���Զ��ı䡣
diff --git a/extensions/map_proposal/ca_adapter.py b/extensions/map_proposal/ca_adapter.py
index 69e206c..9da1857 100644
--- a/extensions/map_proposal/ca_adapter.py
+++ b/extensions/map_proposal/ca_adapter.py
@@ -1,5 +1,5 @@
 # -*- coding: utf-8 -*-
-"""Context Authority consumption for C (P01 port + R04 admission, W4).
+"""Context Authority consumption for C (P01 port + R04 admission, W4+P05B).
 
 Protocol:
 - PIN: C validates with its own expected_revision (= target_revision).
@@ -9,11 +9,21 @@ Protocol:
 - SELECT: only current_state.current_by_scope is read; stale/proposal/
   research/history partitions are never consumed (S20); conflict and
   verification-unavailable keys never become evidence (S23).
-- EVIDENCE: no claim is attached to any proposal automatically (DROP L01/L02 —
-  no keyword trust heuristics, no first-survivor supplement). C has no
-  independent git/gh verifier in this build, so pack claims support nothing;
-  they exist in the selection layer for typed consumers and conflict routing
-  (S21/S22/S25).
+- EVIDENCE: no claim is ever attached to proposal evidence automatically
+  (DROP L01/L02 — no keyword trust heuristics, no first-survivor supplement).
+  Typed consumption is the only channel (P05B):
+  - T1 context enrichment: a relevant LOW-IMPACT claim (team.*/architecture.*)
+    whose key/scope/value mentions a touched path or node adds a labeled
+    context line to the proposal's uncertainty — provenance always shown
+    (freshness, claim id, pack revision); never enters evidence/rationale.
+  - T2 field support: for dict values the per-field verification map is shown
+    (field=verified / field=UNVERIFIED, S22); unverified fields are labelled
+    and support nothing.
+  - T3 independent verification: implementation.* head claims are checked
+    against C's own pinned target. Confirmed → the pin speaks for itself;
+    unverifiable locally (semantic status, no pin) → UNKNOWN limit, claim not
+    consumed; contradicted → claim_id + both values recorded, the pack's
+    claims stop being consumed entirely (invariant 11).
 - CONFLICTS: structural routing over key/scope and word-boundary path/node
   association (P08). A related conflict moves touching proposals to
   unresolved HUMAN_REQUIRED; unrelated candidates keep their valid proposals
@@ -29,6 +39,9 @@ from extensions.map_proposal.model import make_evidence
 DEGRADED = "DEGRADED_NO_CONTEXT"
 FULL = "FULL"
 
+# Domains whose claims are low-impact enough for T1 context enrichment.
+_T1_DOMAINS = ("team.", "architecture.")
+
 _EMPTY = {
     "claims": [],
     "conflict_keys": set(),
@@ -146,10 +159,12 @@ def mentions(text, token):
 
 
 def apply_context_admission(proposals, ca, ca_mode, changed_paths, node_ids,
-                            limits, unresolved):
-    """R04 admission over the canonical proposal list. Returns
-    (proposals, limits, unresolved). Claims are never attached as evidence;
-    conflicts are routed structurally; related proposals move to unresolved."""
+                            limits, unresolved, target_revision=None):
+    """R04 admission + P05B typed consumption over the canonical proposal
+    list. Returns (proposals, limits, unresolved). Claims never become
+    proposal evidence; conflicts are routed structurally; T1/T2 add labeled
+    context to uncertainty; T3 verifies implementation head claims against
+    the pin and marks the pack untrusted on contradiction."""
     if ca_mode != FULL:
         return proposals, limits, unresolved
 
@@ -164,6 +179,10 @@ def apply_context_admission(proposals, ca, ca_mode, changed_paths, node_ids,
             + ", ".join(sorted(str(k) for k in ca["conflict_keys"]))
         )
 
+    claims_for_context = _independent_verification(
+        ca, target_revision, limits, unresolved)
+    pack_trusted = claims_for_context is not None
+
     kept = list(proposals)
     for row in ca["conflict_rows"]:
         if not isinstance(row, dict):
@@ -224,4 +243,103 @@ def apply_context_admission(proposals, ca, ca_mode, changed_paths, node_ids,
             else:
                 still_kept.append(proposal)
         kept = still_kept
+
+    if pack_trusted and claims_for_context:
+        annotated = 0
+        for proposal in kept:
+            tokens = _proposal_tokens(proposal)
+            if not tokens:
+                continue
+            for claim_row in claims_for_context:
+                key = str(claim_row.get("key") or "")
+                if not key.startswith(_T1_DOMAINS):
+                    continue
+                text = " ".join([key, str(claim_row.get("scope") or ""),
+                                 claim_value_text(claim_row)])
+                if not any(mentions(text, token) for token in tokens):
+                    continue
+                proposal.setdefault("uncertainty", []).append(
+                    _context_line(claim_row, ca.get("project_revision")))
+                annotated += 1
+        if annotated:
+            limits.append(f"CA context enrichment: {annotated} labeled context line(s) "
+                          "added to proposal uncertainty (never evidence)")
     return kept, limits, unresolved
+
+
+def _independent_verification(ca, target_revision, limits, unresolved):
+    """T3: check implementation.* head claims against C's own pin. Returns
+    the claims that may still be consumed as context (None = pack
+    contradicted, nothing may be consumed)."""
+    claims = list(ca["claims"])
+    contradicted = False
+    for claim_row in claims:
+        key = str(claim_row.get("key") or "")
+        value = claim_row.get("value")
+        if not key.startswith("implementation."):
+            continue
+        if not isinstance(value, dict) or not isinstance(value.get("head"), str) or not value["head"]:
+            limits.append(f"context implementation claim unverifiable locally (UNKNOWN): "
+                          f"{claim_row.get('claim_id')} ({key}); semantic external status "
+                          "needs an independent verifier C does not run")
+            continue
+        head = value["head"]
+        if not target_revision:
+            limits.append(f"context head claim unverifiable without a pin (UNKNOWN): "
+                          f"{claim_row.get('claim_id')} ({key})")
+            continue
+        if head == target_revision:
+            limits.append(f"context head claim independently confirmed against the pinned "
+                          f"target: {claim_row.get('claim_id')} ({key})")
+            continue
+        contradicted = True
+        limits.append(
+            f"context contradiction (independent observation differs): claim "
+            f"{claim_row.get('claim_id')} ({key}) claims head {head}, pinned target is "
+            f"{target_revision}; pack claims no longer consumed")
+        unresolved.append(
+            {
+                "subject": f"claim:{claim_row.get('claim_id')}",
+                "reason": "HUMAN_REQUIRED",
+                "evidence": [
+                    make_evidence("context_claim", detail=key, claim_id=claim_row.get("claim_id"),
+                                  claim_scope=claim_row.get("scope"), unverified=True)
+                ],
+                "note": f"CA 主张与 C 的独立观察矛盾（主张 head {head}，pinned target "
+                        f"{target_revision}）；以独立证据为准，pack 不再可信",
+            }
+        )
+    if contradicted:
+        return None
+    return claims
+
+
+def _proposal_tokens(proposal):
+    """Paths and node ids a proposal touches (relevance tokens for T1)."""
+    tokens = set()
+    subject = proposal.get("subject")
+    if isinstance(subject, str) and subject:
+        tokens.add(subject)
+    change = proposal.get("proposed_change") or {}
+    for key in ("node_id", "from", "to"):
+        value = change.get(key)
+        if isinstance(value, str) and value:
+            tokens.add(value)
+    for item in proposal.get("evidence", []):
+        if isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"]:
+            tokens.add(item["path"])
+    return tokens
+
+
+def _context_line(claim_row, project_revision):
+    """Labeled T1/T2 context line: provenance always shown, never evidence."""
+    value = claim_row.get("value")
+    verification = field_verification(claim_row)
+    if verification:
+        detail = "fields [" + "; ".join(f"{k}={v}" for k, v in sorted(verification.items())) + "]"
+    else:
+        detail = claim_value_text(value)[:80]
+    freshness = claim_row.get("freshness", "unverified")
+    return (f"CA 上下文[{freshness}] {claim_row.get('key')}@{claim_row.get('scope')}：{detail}"
+            f"（人工参考，非事实证据；claim {claim_row.get('claim_id')}，"
+            f"pack {str(project_revision)[:8]}）")
diff --git a/extensions/map_proposal/engine.py b/extensions/map_proposal/engine.py
index ede1d5d..434b471 100644
--- a/extensions/map_proposal/engine.py
+++ b/extensions/map_proposal/engine.py
@@ -86,8 +86,10 @@ def suggest_map(repo, data) -> dict:
 
         # R03: independent import-relation channel — runs regardless of
         # declaration-channel verdicts (F05); skipped sources never feed it.
-        relation_paths = [
-            c["path"]
+        # Full change dicts are passed so the channel can anchor the base
+        # side of a rename at old_path and treat added files as empty bases.
+        relation_changes = [
+            c
             for c in request["changed_paths"]
             if c["path"].endswith(".py")
             and c["path"] not in facts["skipped"]
@@ -95,7 +97,7 @@ def suggest_map(repo, data) -> dict:
         ]
         known_paths = set(facts["files"]) | changed_paths | set(indexes["node_by_path"])
         relations.handle_relations(repo, base, target, indexes, facts, known_paths,
-                                   relation_paths, proposals, unresolved, limits)
+                                   relation_changes, proposals, unresolved, limits)
 
         # R05: stale-map target existence, independent of B availability.
         analysis.handle_stale_map(repo, base, target, request["changed_paths"], indexes,
@@ -107,10 +109,12 @@ def suggest_map(repo, data) -> dict:
             proposals, request["prior_decisions"], limits
         )
 
-        # R04: CA admission — conflict routing and evidence trust boundary.
+        # R04: CA admission — conflict routing, evidence trust boundary, and
+        # P05B typed consumption (T1/T2 context, T3 independent verification
+        # of implementation head claims against C's own pin).
         proposals, limits, unresolved = ca_adapter.apply_context_admission(
-            proposals, ca, ca_mode, changed_paths, indexes["node_ids"], limits, unresolved
-        )
+            proposals, ca, ca_mode, changed_paths, indexes["node_ids"], limits,
+            unresolved, target_revision=target)
 
         # Single publication exit (invariant 2): every candidate goes through the
         # canonical proposal constructor with its invariants.
tests\test_real_b_integration.py:195:        # Same revision: gates run, then zero proposals (invariant 13).
tests\test_w4_ca_trust.py:2:"""W4 convergence contract tests: CA trust boundary (R04).
tests\test_w4_ca_trust.py:177:        # Mutation M3 (F03 regression) showed the no-attach invariant was only
tests\audit_w3_adversarial.py:4:as-is. Each case builds a real temp git repo and runs the convergence engine.
tests\test_w5_compatibility.py:2:"""W5 convergence contract tests: compatibility envelope, mode honesty,
tests\test_w2_channels.py:2:"""W2 convergence contract tests: diff × map channels.
tests\test_w2_channels.py:7:F04 cross-channel skipped suppression and base==target silence (invariant 13).
extensions/map_proposal\engine.py:2:"""C convergence engine — single canonical pipeline (R01/R06/R07 skeleton).
extensions/map_proposal\engine.py:4:Pipeline (invariant order):
extensions/map_proposal\engine.py:59:    # zero-proposal same-revision branch below applies (invariant 13).
extensions/map_proposal\engine.py:119:        # Single publication exit (invariant 2): every candidate goes through the
extensions/map_proposal\engine.py:120:        # canonical proposal constructor with its invariants.
tests\test_w6_smoke.py:9:invariant (PROPOSED / human_required / no position / no map write), is
tests\test_w6_smoke.py:108:        # publication invariants
tests\test_map_proposal.py:2:"""W1 convergence contract tests: pins, B gate, skipped eligibility, path
tests\test_map_proposal.py:6:behaviors that the convergence contract rejects (implicit HEAD fallback,
tests\audit_probes.py:3:FROZEN old implementations (old FAIL) and verify the convergence HEAD behavior
tests\audit_probes.py:9:- convergence HEAD via repo imports
tests\audit_probes.py:124:    on LOCAL frozen engine; then same fixtures on convergence HEAD."""
tests\audit_probes.py:199:    # ---- convergence HEAD on the same fixtures ----
tests\test_w3_relations.py:2:"""W3 convergence contract tests: the independent import-relation channel.
tests\test_w3_relations.py:194:        # F06 contract: "同一规范化目标的写法变换不产生关系变化". The AST
tests\test_w3_relations.py:297:        # limits), never as silent no-change (C-3).
extensions/map_proposal\ca_adapter.py:26:    claims stop being consumed entirely (invariant 11).
extensions/map_proposal\model.py:2:"""C convergence primitives: pins, paths, map intake, stable identity, evidence.
extensions/map_proposal\model.py:121:    canonical C request. C does not invent its own diff vocabulary (invariant 5).
extensions/map_proposal\model.py:161:    (invariant 6). Evidence paths are validated like every other path source
extensions/map_proposal\model.py:162:    (S28). The map carries no version identity (invariant 4).
extensions/map_proposal\model.py:267:    """Canonical proposal. K02 invariants enforced at construction time."""
extensions/map_proposal\analysis.py:6:LOCAL engine.py @5058c54 with the convergence fixes:
extensions/map_proposal\relations.py:10:"zero imports" (C-3). Declaration-channel verdicts never gate this channel
extensions/map_proposal\convergence\SOURCES_MANIFEST.md:9:| TEAM C | `3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`; branch `feat/role-c-map-proposal`; PR #35; owner `bjtxcy` | C 的交付与治理 baseline；本分支 `integration/c-convergence-v1` 的起点 |
extensions/map_proposal\convergence\SOURCES_MANIFEST.md:46:`integration/c-convergence-v1` 起点为 TEAM C frozen HEAD `3bd980de`。C 实施范围限定: `extensions/map_proposal/`、C contract/集成测试、必要 C 消费者文档。共享 A/B/D/CA 依赖由各 owner 独立交付，不在本分支修改 `extension_host.py`。
extensions/map_proposal\convergence\CONTRACT_MANIFEST.md:22:## 收敛后单一决策路径
extensions/map_proposal\convergence\COMMON_BASE_PLAN.md:15:| **D1 (A30/F12): 共享 Host runtime SystemExit 隔离** | S30: 七扩展集成，故障扩展普通 Exception 与 runtime SystemExit 分别注入，其余 route 仍可调用；不能只测 load 或 C 内部 catch | A/Core owner（修复 extension_host.py 或提供满足 oracle 的隔离执行机制） | **BLOCKER — 未完成时整体不能报 30/30 PASS** | C 不修改 extension_host.py；C 只交付自身 B/CA 依赖边界的隔离测试。S30 标记 EXTERNAL_BLOCKED 直至独立交付落地。 |
extensions/map_proposal\convergence\COMMON_BASE_PLAN.md:22:convergence: establish W0 contract oracle → complete W1 input and evidence gates → implement W2 diff-map reasoning → implement W3 relation analysis → implement W4 CA trust → implement W5 compatibility and identity → W6 integration suite。
extensions/map_proposal\convergence\COMMON_BASE_PLAN.md:28:- 30/30 PASS 才能申请 READY 评审；S30 未满足时整体 gate 阻塞，不能由 C 内部 catch 替代。
extensions/map_proposal\convergence\PORT_MANIFEST.md:7:| ID | 保留对象 | 收敛动作 | Oracle |
extensions/map_proposal\extension.py:2:"""Map Proposal extension (Role C) — convergence handler seam (K01).
extensions/map_proposal\extension.py:34:        # Internal invariant violation (proposal shape, evidence kinds) must
extensions/map_proposal\convergence\ORACLE_MANIFEST.md:3:S01–S30 一一对应冻结 Common Acceptance Matrix A01–A30，目标全部 PASS。两列历史状态不作 oracle。撤回样例（初始 A16 缺 position、X10 empty-map、初始 A27-map-shape）不进入缺陷或验收 oracle。
extensions/map_proposal\convergence\ORACLE_MANIFEST.md:36:| S30 | A30 Host isolation | 七扩展可加载；普通异常与 runtime SystemExit 均不阻断其他路由。C 边界与共享 Host 分别测试。**依赖 A/Core 修复才能 PASS。** | 冻结 Host 场景 |

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content extensions/map_proposal/relations.py; Get-Content extensions/map_proposal/convergence/CONTRACT_MANIFEST.md; Get-Content extensions/map_proposal/convergence/ORACLE_MANIFEST.md; Get-Content extensions/map_proposal/ca_adapter.py' in G:\jiagou\projectmind-c-convergence
 succeeded in 206ms:
# -*- coding: utf-8 -*-
"""Independent import-relation channel (R03, W3).

Signal AND proof are the same artifact: a per-file AST diff of the pinned
base blob against the pinned target blob. The diff patch is not parsed at
all �?a regex on patch text was only ever a candidate extractor (DROP L05)
and its line-based form silently missed relative imports, from-submodule
imports and multiline imports (adversarial cases 1a/1b/3/4, 2026-10-04).
Blob read/parse failure raises DiffSignalError �?UNKNOWN/unresolved, never
"zero imports" (C-3). Declaration-channel verdicts never gate this channel
(F05): "declarations unchanged" does not mean "no import signal" (X01/X11).

Resolution is a heuristic (dotted path �?known repo paths); modules that
resolve outside the repo (stdlib/site-packages) are not architecture
relations. Known resolution limits (namespace packages, src-layout) mean an
unresolved repo-internal import can stay invisible �?recorded limit, does
not fabricate a relation.

Removal proof domain is the whole map-node evidence domain (R03): a relation
removal candidate requires an existing map edge and ALL .py files of the
source node's evidence domain free of imports into the target domain at
target, with at least one such import at base (S03, X12 multi-source).

Known edge: a rewrite between from-import shapes can add/drop the bare
package-prefix candidate (e.g. `from . import b` �?`from .b import B`), so
the package __init__ dependency can look removed although Python still
executes the parent package implicitly. Bounded: removal candidates need an
existing map edge plus the full domain proof, and stay low-confidence
human-review items.
"""
from __future__ import annotations

import ast
import posixpath

from extensions.map_proposal import gitio
from extensions.map_proposal.analysis import diff_evidence, map_node_evidence
from extensions.map_proposal.facts_adapter import path_eligibility
from extensions.map_proposal.model import make_evidence


def resolve_module(module, source_path, known_paths):
    """Module string �?repo-relative path among known_paths. Absolute forms
    resolve directly; relative import targets resolve against the source
    file's package directory."""
    if not module:
        return None
    if module.startswith("."):
        depth = len(module) - len(module.lstrip("."))
        rest = module.lstrip(".").replace(".", "/")
        base_dir = posixpath.dirname(source_path)
        for _ in range(depth - 1):
            base_dir = posixpath.dirname(base_dir)
        base = posixpath.join(base_dir, rest) if rest else base_dir
    else:
        base = module.replace(".", "/")
    for candidate in (base + ".py", posixpath.join(base, "__init__.py")):
        if candidate in known_paths:
            return candidate
    return None


def _parse_blob(repo, revision, source_path):
    """Pinned blob �?AST. Raises DiffSignalError on read/parse failure
    (UNKNOWN, never silent zero)."""
    try:
        raw = gitio.read_blob(repo, revision, source_path)
        return ast.parse(raw)
    except (gitio.DiffSignalError, SyntaxError, ValueError) as exc:
        raise gitio.DiffSignalError(f"cannot verify imports of {source_path}@{revision[:8]}: "
                                    f"{type(exc).__name__}") from exc


def _scan_imports(tree):
    """(static module strings, dynamic import tags) from one parsed module.

    ImportFrom contributes its package prefix AND each prefix-qualified alias
    so `from pkg import b` (b a submodule) and `from . import b` carry the
    submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
    Aliased and parenthesized/multiline forms are AST-native. Docstrings,
    comments and string literals never appear here."""
    static, dynamic = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0) + (node.module or "")
            if prefix:
                static.add(prefix)
            for alias in node.names:
                if not prefix:
                    static.add(alias.name)
                elif prefix.endswith("."):
                    static.add(prefix + alias.name)
                else:
                    static.add(f"{prefix}.{alias.name}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "__import__":
                dynamic.add("__import__")
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                dynamic.add("importlib.import_module")
    return static, dynamic


def imported_paths(repo, revision, source_path):
    """Dotted module strings actually imported by source_path@revision (AST).
    Raises DiffSignalError on read/parse failure."""
    static, _ = _scan_imports(_parse_blob(repo, revision, source_path))
    return static


def _resolved_imports(repo, revision, source_path, known_paths):
    """resolved repo path �?module strings that reach it. Modules resolving
    outside known repo paths are external dependencies, not relations."""
    resolved = {}
    for module in sorted(imported_paths(repo, revision, source_path)):
        target_path = resolve_module(module, source_path, known_paths)
        if target_path:
            resolved.setdefault(target_path, []).append(module)
    return resolved


def _file_relation_events(repo, base, target, change, known_paths):
    """AST-diff one changed .py file's import sets: pinned base blob vs
    pinned target blob. `renamed` compares old_path@base with path@target;
    `added` has an empty base set; `modified` compares path@base. Raises
    DiffSignalError when a needed blob cannot be read or parsed."""
    path = change["path"]
    status = change["status"]
    base_ref = change.get("old_path") if status == "renamed" else None
    if base_ref is None and status == "modified":
        base_ref = path
    if base_ref:
        base_resolved = _resolved_imports(repo, base, base_ref, known_paths)
        base_dynamic = _scan_imports(_parse_blob(repo, base, base_ref))[1]
    else:
        base_resolved, base_dynamic = {}, set()
    target_static, target_dynamic = _scan_imports(_parse_blob(repo, target, path))
    target_resolved = {}
    for module in sorted(target_static):
        resolved = resolve_module(module, path, known_paths)
        if resolved:
            target_resolved.setdefault(resolved, []).append(module)
    return {
        "path": path,
        "added": {p: mods for p, mods in target_resolved.items() if p not in base_resolved},
        "removed": {p: mods for p, mods in base_resolved.items() if p not in target_resolved},
        "dynamic": sorted(target_dynamic - base_dynamic),
    }


def handle_relations(repo, base, target, indexes, facts, known_paths, relation_changes,
                     proposals, unresolved, limits):
    events = []
    for change in sorted(relation_changes, key=lambda c: c["path"]):
        try:
            events.append(_file_relation_events(repo, base, target, change, known_paths))
        except gitio.DiffSignalError as exc:
            limits.append(f"import signal extraction unavailable: {exc}")
            unresolved.append(
                {
                    "subject": change["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, change["path"],
                                               "import signal unverified")],
                    "note": "import 信号无法�?AST 证实（读�?解析失败），进入 UNKNOWN",
                }
            )

    emitted_pairs = set()
    for event in events:
        source_path = event["path"]
        for target_path in sorted(event["added"]):
            if path_eligibility(target_path, facts) == "skipped":
                continue
            source_owners = indexes["node_by_path"].get(source_path, [])
            target_owners = indexes["node_by_path"].get(target_path, [])
            if not source_owners or not target_owners or set(source_owners) == set(target_owners):
                continue
            pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
            if pair in emitted_pairs:
                continue
            emitted_pairs.add(pair)
            modules = "�?.join(sorted(event["added"][target_path]))
            uncertainty, confidence = [], "low"
            if len(source_owners) > 1 or len(target_owners) > 1:
                uncertainty.append("multiple candidate nodes on this import edge")
            else:
                confidence = "medium"
            proposals.append(
                {
                    "kind": "RELATION_ADD",
                    "subject": f"{source_owners[0]}->{target_owners[0]}",
                    "node_ids": None,
                    "proposed_change": {
                        "from": source_owners[0],
                        "to": target_owners[0],
                        "label": f"import 依赖(候�?: {source_path} -> {target_path}",
                    },
                    "rationale": "跨节点证据域新增实际 import（AST 证实）；方向与语义需人工确认",
                    "evidence": [
                        diff_evidence(target, source_path,
                                      f"import added (AST): {modules} -> {target_path}"),
                        diff_evidence(target, target_path, f"imported by {source_path}"),
                        map_node_evidence(source_owners[0], f"covers {source_path}"),
                        map_node_evidence(target_owners[0], f"covers {target_path}"),
                    ],
                    "confidence": confidence,
                    "uncertainty": uncertainty,
                }
            )

    for event in events:
        source_path = event["path"]
        for target_path in sorted(event["removed"]):
            if path_eligibility(target_path, facts) == "skipped":
                continue
            source_owners = indexes["node_by_path"].get(source_path, [])
            target_owners = indexes["node_by_path"].get(target_path, [])
            if not source_owners or not target_owners or set(source_owners) == set(target_owners):
                continue
            # Removal needs an existing map edge between the two domains (R03).
            edge_exists = any(
                (source_owner, target_owner) in indexes["edge_set"]
                for source_owner in source_owners
                for target_owner in target_owners
            )
            if not edge_exists:
                continue
            pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
            if pair in emitted_pairs:
                continue
            verdict = _domain_import_gone(repo, base, target, indexes, source_path,
                                          source_owners, target_path, known_paths, limits)
            if verdict != "gone":
                continue
            emitted_pairs.add(pair)
            modules = "�?.join(sorted(event["removed"][target_path]))
            proposals.append(
                {
                    "kind": "RELATION_REMOVE_CANDIDATE",
                    "subject": f"{source_owners[0]}->{target_owners[0]}",
                    "node_ids": None,
                    "proposed_change": {
                        "from": source_owners[0],
                        "to": target_owners[0],
                        "label": f"import 移除(候�?: {source_path} -> {target_path}",
                    },
                    "rationale": "源节点证据域内全�?.py 文件对目标域的静�?import 已消失（AST 证实）；"
                                 "是否意味架构关系消失由人判断",
                    "evidence": [
                        diff_evidence(base, source_path,
                                      f"import present at base (AST): {modules} -> {target_path}"),
                        diff_evidence(target, source_path, "import removed at target"),
                        map_node_evidence(source_owners[0], f"covers {source_path}"),
                        map_node_evidence(target_owners[0], f"covers {target_path}"),
                    ],
                    "confidence": "low",
                    "uncertainty": [],
                }
            )

    for event in events:
        for tag in event["dynamic"]:
            if path_eligibility(event["path"], facts) == "skipped":
                continue
            unresolved.append(
                {
                    "subject": event["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, event["path"],
                                               f"dynamic import: {tag}")],
                    "note": "动�?字符串构�?import：依赖信号不足，不足以建立关系候�?,
                }
            )


def _domain_import_gone(repo, base, target, indexes, signal_path, source_owners,
                        target_path, known_paths, limits):
    """Removal proof over the FULL source node evidence domain: every .py
    file's imports into target_path must exist at base (somewhere in the
    domain) and be gone at target everywhere. Any read/parse failure �?    'unknown' (never treated as zero, DROP L05)."""
    domain_paths = []
    for owner in source_owners:
        for node in indexes["nodes"]:
            if node["id"] == owner:
                domain_paths.extend(p for p in node["evidence_paths"] if p.endswith(".py"))
    domain_paths = sorted(set(domain_paths))
    if signal_path not in domain_paths:
        domain_paths.append(signal_path)
    if not domain_paths:
        return "insufficient"

    had_import_at_base = False
    for path in domain_paths:
        try:
            at_base = _imports_target_loose(repo, base, path, target_path, known_paths)
            at_target = _imports_target_loose(repo, target, path, target_path, known_paths)
        except gitio.DiffSignalError as exc:
            limits.append(f"import removal proof unavailable: {exc}")
            return "unknown"
        if at_base:
            had_import_at_base = True
        if at_target:
            return "retained"
    return "gone" if had_import_at_base else "insufficient"


def _imports_target_loose(repo, revision, source_path, target_path, known_paths):
    """Does any AST import of source_path@revision resolve to target_path?
    Relative candidates keep their leading dots so resolve_module anchors
    them to the source package."""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        if resolve_module(candidate, source_path, known_paths) == target_path:
            return True
    return False
# C Convergence �?Contract Manifest (W0)

契约来源: `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa`
规范入口: c-readiness/ �?C_PRODUCT_BOUNDARY / C_INPUT_OUTPUT_CONTRACT_PROPOSAL / C_ACCEPTANCE_PLAN / C_B_CODEFACTS_USAGE / C_CONTEXT_SAFETY_RULES / C_CONSUMABLE_INTERFACE�?
## 产品不变式（13 条）

1. 输入 = pinned Git diff + B 声明事实 + 当前人工 Project Map + 可�?CA；输�?= `proposals / unresolved / no_proposal / limits` + 请求与事实底座追踪。`UNKNOWN` �?unresolved，不进强 proposal�?2. 六类候�? `NODE_ADD / RELATION_ADD / RELATION_REMOVE_CANDIDATE / IMPLEMENTATION_LINK_CHANGE / NODE_REMOVE_CANDIDATE / RESPONSIBILITY_CHANGE`。每项完整字段、非空可定位 revision/path evidence、confidence、uncertainty、`status=PROPOSED`、`human_required=true`�?3. C 不写正式地图、不建议 position、不自行 accept/reject、不仲裁 CA conflict、不复制 B 声明解析、不编辑 CA registry、不接管 D worklog。职�?架构归属/关系含义 = INFERENCE；声�?路径/diff = FACT�?4. base/target 必须完整 40/64 位小�?SHA。缺 pin、HEAD、短 SHA 一律拒绝；不得�?snapshot 偷补。地图无版本身份，target SHA 不能证明地图适用�?5. compare 来源�?A/caller �?changed_paths。Core `baseRevision / targetRevision / changes[{code,path,oldPath?}]` 经显式适配映射；C 不另建文件差异口径。只�?pinned patch/blob，不从工作树补证据�?6. 地图�?Core `{note,nodes,edges}` 接收；非�?nodes �?title/summary/entryPoint/position/evidence 约束不得被测试替身放宽。输入保�?position；候�?proposed_change 不含 position�?7. B 事实仅含 revision/files/skipped 与声�?name/kind/line；无 import/签名/调用�?职责。所有目标事实来源验�?revision == target（含安装 B 返回值、同版本比较、空 diff）。必�?base 声明证据�?B 独立 pinned base 收集并标 base 角色�?8. changed 文件�?B skipped �?HUMAN_REQUIRED unresolved；不得继续作为节�?关系强候选的事实基础。B 不可�?�?limits；可运行安全 diff↔map；需 B 的新增节点进 unresolved，不虚构 code_fact�?9. 依赖信号来自实际 pinned Git diff。允�?base/target import AST 验证信号、排除字符串/docstring；不得借此重做 B 声明解析。声明未�?�?import 未变�?10. Context Pack 先真�?`validate_context_pack(pack, expected_revision=C 独立 pin)`。失败整包弃用，显式 DEGRADED/limits 后可�?pack 运行�?硬停�?= 停止消费�?pack，不是终�?C 服务�?11. CA 只读 current_by_scope；verified_fields 按字段判定。非现行分区、conflict/unavailable key 不进 proposal context evidence。revision 对应/PR 状�?contract shape/implementation 状态须独立 git/gh 核验；state/merged/draft 分别核对；不可用 = UNKNOWN；矛盾以独立证据为准、记�?claim_id 与双方值、pack 不再可信�?12. 相关 conflict �?unresolved HUMAN_REQUIRED；C 不选边。未覆盖 �?不存在；不解�?do_not_assume 中的数字。相同固定输�?+ 固定独立观察 = 相同输出；不嵌时间戳/随机值�?13. `base==target` 先完成必需输入/事实一致性校验，再返回零 proposal，并说明 map drift 不属于本次差异判断。人�?REJECTED、同 subject/kind 且理由未变的候选遵�?F20 抑制；无交叉信号不制造人工任务�?
## 收敛后单一决策路径

请求/路径/pin 校验 �?Core compare 适配 �?B �?CA 入口校验 �?独立收集声明变化/import 变化/地图路径映射/目标存在�?�?按候选来源统一检�?skipped、证据、冲突、CA 准入 �?四桶输出 �?兼容字段投影�?
各信号通道独立运行；任何单一通道不得�?声明没变"结束整个文件分析。结果发布只有一个出口：不做两套引擎 union，不在未完成准入检查时向旧 candidates 字段写候选�?
# C Convergence �?Oracle Manifest (W0)

S01–S30 一一对应冻结 Common Acceptance Matrix A01–A30，目标全�?PASS。两列历史状态不�?oracle。撤回样例（初始 A16 �?position、X10 empty-map、初�?A27-map-shape）不进入缺陷或验�?oracle�?
| ID | Common / 场景 | 必须断言的目标行�?| 变体 |
|---|---|---|---|
| S01 | A01 real NODE_ADD | 新模块无 map 覆盖且有 B 声明: 恰好预期节点，git_diff + 可回�?code_fact + map 判断；全�?changed-only 不多生无关节点；PROPOSED/human_required。函数型模块不凭 class 门槛定案�?| A01、X19 |
| S02 | A02 real RELATION_ADD | 新增实际跨域 import: 预期 from/to �?RELATION_ADD，精确源 diff + 两端 map 证据；声明没变仍触发�?| A02、X01; class �?�?import |
| S03 | A03 relation removal | 最后跨�?import 消失: 对应既有 edge �?REMOVE_CANDIDATE；其他源�?import 不移除；churn 不移除�?| A03、X11/X13; 跨文件剩�?import |
| S04 | A04 implementation link | rename/move: 对应 node 路径更新，old@base/new@target，不 NODE_ADD�?| A04; 移动子目�?|
| S05 | A05 node removal | node �?evidence 明确�?target 消失: 低置信度删除候选；任一路径保留则无删除候选�?| A05; �?evidence 部分保留 |
| S06 | A06 responsibility change | entryPoint 声明改名/消失: 对应 node 责任/实现链接候选，声明证据�?B 给出；不选无依据的首个替代符号�?| A06; 多声明歧�?|
| S07 | A07 comment only | 零强 proposal，明�?comments_only 原因；无无关人工任务�?| A07、X20 |
| S08 | A08 formatting only | �?proposal，格式原因；不因行号/引号漂移制造新职责�?| A08 |
| S09 | A09 helper only | 已有职责�?helper �?NODE_ADD；无其他交叉信号无强 proposal�?| A09、F10 |
| S10 | A10 internal class only | 已有职责加内�?class �?NODE_ADD；提示不宣称新职责事实�?| A10、F9 |
| S11 | A11 docstring only | �?docstring（含 import 文本）零关系/节点�?proposal；有其他声明变化也不能把字符串当 import�?| A11、X03/X12 |
| S12 | A12 test noise | �?test/generated 噪声无业务架构候选；不例行制造人�?unknown；确�?map 交叉按实际证据�?| A12; R02/R05 噪声输入 |
| S13 | A13 B skipped | 真实 skipped changed �?HUMAN_REQUIRED；任何通道/兼容 candidates 无依赖该源的强候选；正常源仍工作�?| A13、X04/X21; 真实 collector 语法坏源 |
| S14 | A14 B mismatch | supplied/installed B mismatch 一律受控拒绝；�?revision、空 changes 不绕过�?| A14、X06; 安装 B 注入 mismatch |
| S15 | A15 B unavailable | 明确 limits/DEGRADED；安�?diff↔map 分支仍运行；需 B 的新模块 unresolved、零虚构 code_fact�?| A15; 独立 rename 正例 |
| S16 | A16 stale map | 早于 base 删除、target �?evidence 缺失仍有 stale removal candidate；读取未�?�?缺失。base==target �?proposal + map drift limit�?| A16-valid-map `4f95f010...`、F11/F15 |
| S17 | A17 ambiguous mapping | �?map owner: �?中置信度并列 multiple candidate nodes �?unresolved；不武断单选�?| A17; �?owner rename |
| S18 | A18 missing evidence | 新文件但 facts/diff 证据不足: unresolved UNKNOWN、零强候选；B 没条�?�?架构不存在�?| A18; 无声�?缺关键证�?|
| S19 | A19 CA conflict | relevant key/scope conflict 不入任何 proposal evidence；相关候�?HUMAN_REQUIRED；精确无关节点仍有有效候选�?| A19、X14/X15/X18 |
| S20 | A20 stale claim | validated stale 与其他非现行分区不进 context_claim；相关消费需求有 limits/UNKNOWN�?| A20; stale/proposal/research/history 分区 |
| S21 | A21 multi-scope | 真实合法 pack �?key �?scope 均进选择层；按相关用途分别消费，不读 current 投影、不随便加首项�?| A21; 正面计数 + �?scope 关联 |
| S22 | A22 verified_fields | 支持字段与无支持字段分开；后�?UNVERIFIED/诊断、不能作事实支撑；行 freshness 不升级整值�?| A22; �?evidence ref、字段部分覆�?|
| S23 | A23 unavailable | 合法 unavailable/stale fixture �?validator PASS；C 不伪作坏�?DEGRADED；相关值排除且明确 UNKNOWN/limits�?| A23 `b3addc5a...`; 替换�?C_A23 自测 |
| S24 | A24 invalid pack | 真实 validator 拒绝: 整包不消费、零 context_claim、显�?DEGRADED；独立有�?diff/B/map 候选仍可存在�?| A24; �?SHA 缺字�?坏回�?�?revision |
| S25 | A25 coherent poison | 结构�?digest 合法�?poison 不进 evidence/rationale；高影响事实有独立真值或 UNKNOWN；矛盾记�?claim_id/双方值，pack 不再可信�?| A25、X05/X16/X17 `ea8cbd8f...`(X17); 中�?key/自由文本、核验不可用 |
| S26 | A26 determinism | 固定输入 + 固定外部观察重复字节一致；ID 不依赖偶然遍历顺序，无时间戳/随机数�?| A26-repeat、X09; 排序变体 |
| S27 | A27 malformed input | HEAD/�?SHA/�?facts shape/�?map shape/缺字段受控拒绝；安装 B 异常 shape 不崩溃、不误当 available�?| A27; valid-context malformed_payload_map |
| S28 | A28 path abuse | changed/old_path/map evidence/facts/entryPoint 全来源路径约束；拒绝越界/绝对路径/不安全输入；不读工作树或 repo 外补证�?| A28; map evidence + rename 双侧 |
| S29 | A29 no map write | 请求前后正式地图�?source fixture 文件 hash 不变；无 save/apply/accept �?position proposed_change�?| 冻结 no_map_write 字段 + 独立 hash 断言 |
| S30 | A30 Host isolation | 七扩展可加载；普通异常与 runtime SystemExit 均不阻断其他路由。C 边界与共�?Host 分别测试�?*依赖 A/Core 修复才能 PASS�?* | 冻结 Host 场景 |

## Fixture 纪律

- 原始记录 `request/repo/input_sha256` 可恢复输入；`results/assertions/summary` 是冻结观察，不能复制�?expected output。每�?migrated fixture 保留 source record ID/hash + 契约条款出处�?- A01–A06 正例检�?kind、subject、map node/edge、实际证据、status/human_required；反例检查所有相关候选入口与诊断�?- B skipped 用真�?collector 构造语法坏源；补正常源正例。B unavailable/mismatch 与合�?B 返回分开测试�?- CA 两层测试: 先真 validator PASS/REJECT，再�?C 行为。坏包可无包继续，必须同时有独立候选正例�?- 动�?相对等不支持信号必须�?UNKNOWN 正面断言。F18 无交叉信号、F19 动态依赖、F20 人工否决、X07 mode、X09 ID collision、多文件关系删除证明�?30 项内部必要变体�?
## 关键输入锚点

| Record ID | input_sha256 |
|---|---|
| X01-unchanged-decls-real-import | `351d9d86a0cc43fa205957e4a349578449aec5458bdd52ba7ef5947955de78cc` |
| X04-skipped-relation | `2d5d6fc0df62b8fe39112597850a74c344b39b90f48e1c14b4ec7dc933c190dd` |
| X17-hidden-open | `ea8cbdf902699cf3301a8dcee42f2bb719a771bedf726c0f5cd232755f36d8e3` |
| X18-conflict-by-scope | `deb92c02ee7a494bb64157d1ce9c174296bdf1928ace2b7b233901bbaebe2498` |
| A16-valid-map | `4f95f010ada0bb012d82611eb94b2b30c443139fd968288bd3855034794b7726` |
| A23 | `b3addc5ad3f0e2926296d979a85234bfdce4b5f543cc8f687d52962775ba944f` |
# -*- coding: utf-8 -*-
"""Context Authority consumption for C (P01 port + R04 admission, W4+P05B).

Protocol:
- PIN: C validates with its own expected_revision (= target_revision).
- VALIDATE: the real CA validator runs first; any failure discards the whole
  pack (no partial use) and C degrades explicitly �?independent diff/B/map
  candidates continue (S24).
- SELECT: only current_state.current_by_scope is read; stale/proposal/
  research/history partitions are never consumed (S20); conflict and
  verification-unavailable keys never become evidence (S23).
- EVIDENCE: no claim is ever attached to proposal evidence automatically
  (DROP L01/L02 �?no keyword trust heuristics, no first-survivor supplement).
  Typed consumption is the only channel (P05B):
  - T1 context enrichment: a relevant LOW-IMPACT claim (team.*/architecture.*)
    whose key/scope/value mentions a touched path or node adds a labeled
    context line to the proposal's uncertainty �?provenance always shown
    (freshness, claim id, pack revision); never enters evidence/rationale.
  - T2 field support: for dict values the per-field verification map is shown
    (field=verified / field=UNVERIFIED, S22); unverified fields are labelled
    and support nothing.
  - T3 independent verification: implementation.* head claims are checked
    against C's own pinned target. Confirmed �?the pin speaks for itself;
    unverifiable locally (semantic status, no pin) �?UNKNOWN limit, claim not
    consumed; contradicted �?claim_id + both values recorded, the pack's
    claims stop being consumed entirely (invariant 11).
- CONFLICTS: structural routing over key/scope and word-boundary path/node
  association (P08). A related conflict moves touching proposals to
  unresolved HUMAN_REQUIRED; unrelated candidates keep their valid proposals
  (S19/X14/X15/X18).
"""
from __future__ import annotations

import json
import re

from extensions.map_proposal.model import make_evidence

DEGRADED = "DEGRADED_NO_CONTEXT"
FULL = "FULL"

# Domains whose claims are low-impact enough for T1 context enrichment.
_T1_DOMAINS = ("team.", "architecture.")

_EMPTY = {
    "claims": [],
    "conflict_keys": set(),
    "unavailable_keys": set(),
    "conflict_rows": [],
    "schema_version": None,
    "project_revision": None,
    "registry_hash": None,
}


def _empty_context():
    return {key: (set() if isinstance(value, set) else value) for key, value in _EMPTY.items()}


def _rows(pack, name):
    rows = pack.get(name)
    return rows if isinstance(rows, list) else []


def load_context(pack, target_revision):
    limits = []
    if pack is None:
        limits.append("context authority unavailable; running DEGRADED_NO_CONTEXT")
        return _empty_context(), DEGRADED, limits
    try:
        from extensions.context_authority.context_pack import validate_context_pack  # noqa: PLC0415
    except Exception:  # noqa: BLE001 �?CA not installed on this base
        limits.append("context authority extension unavailable; running DEGRADED_NO_CONTEXT")
        return _empty_context(), DEGRADED, limits
    try:
        validate_context_pack(pack, expected_revision=target_revision)
    except Exception as exc:  # noqa: BLE001 �?any validation failure discards the whole pack
        limits.append(
            f"context pack rejected (validation failed: {type(exc).__name__}); "
            "pack discarded entirely, running DEGRADED_NO_CONTEXT"
        )
        return _empty_context(), DEGRADED, limits

    state = pack.get("current_state") or {}
    rows = state.get("current_by_scope")
    rows = rows if isinstance(rows, list) else []
    conflict_keys = {row.get("key") for row in _rows(pack, "known_conflicts") if isinstance(row, dict)}
    unavailable_keys = {
        row.get("key") for row in _rows(pack, "verification_unavailable") if isinstance(row, dict)
    }
    claims = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        if key in conflict_keys or key in unavailable_keys:
            continue
        claim_ids = row.get("claim_ids") if isinstance(row.get("claim_ids"), list) else []
        claims.append(
            {
                "key": key,
                "scope": row.get("scope"),
                "value": row.get("value"),
                "freshness": row.get("freshness", "unverified"),
                "claim_id": claim_ids[0] if claim_ids else None,
                "evidence": [ref for ref in (row.get("evidence") or []) if isinstance(ref, dict)],
            }
        )
    return {
        "claims": claims,
        "conflict_keys": conflict_keys,
        "unavailable_keys": unavailable_keys,
        "conflict_rows": [row for row in _rows(pack, "known_conflicts") if isinstance(row, dict)],
        "schema_version": pack.get("schema_version"),
        "project_revision": pack.get("project_revision"),
        "registry_hash": state.get("registry_hash"),
    }, FULL, limits


def claim_value_text(claim):
    value = claim.get("value")
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def verified_fields(claim):
    """Row-level verified freshness �?every field verified: returns the
    declared field set, or None when no live_verification declares one (then
    every value field must be treated as UNVERIFIED, S22)."""
    for ref in claim.get("evidence", []):
        live = ref.get("live_verification")
        if isinstance(live, dict) and isinstance(live.get("verified_fields"), list):
            return set(live["verified_fields"])
    return None


def field_verification(claim):
    """Per-field support map for dict values (S22 diagnostics; never a licence
    to attach the claim itself)."""
    if not isinstance(claim.get("value"), dict):
        return None
    fields = verified_fields(claim)
    return {
        key: ("verified" if fields is not None and key in fields else "UNVERIFIED")
        for key in sorted(claim["value"])
    }


def mentions(text, token):
    """Word-boundary occurrence check (P08); avoids node-a/node-api substring
    false positives."""
    if not token or not text:
        return False
    return re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", text) is not None


def apply_context_admission(proposals, ca, ca_mode, changed_paths, node_ids,
                            limits, unresolved, target_revision=None):
    """R04 admission + P05B typed consumption over the canonical proposal
    list. Returns (proposals, limits, unresolved). Claims never become
    proposal evidence; conflicts are routed structurally; T1/T2 add labeled
    context to uncertainty; T3 verifies implementation head claims against
    the pin and marks the pack untrusted on contradiction."""
    if ca_mode != FULL:
        return proposals, limits, unresolved

    if ca["unavailable_keys"]:
        limits.append(
            "context verification unavailable keys excluded from evidence (UNKNOWN): "
            + ", ".join(sorted(str(k) for k in ca["unavailable_keys"]))
        )
    if ca["conflict_keys"]:
        limits.append(
            "context claims excluded (known conflicts): "
            + ", ".join(sorted(str(k) for k in ca["conflict_keys"]))
        )

    claims_for_context = _independent_verification(
        ca, target_revision, limits, unresolved)
    pack_trusted = claims_for_context is not None

    kept = list(proposals)
    for row in ca["conflict_rows"]:
        if not isinstance(row, dict):
            continue
        row_text = " ".join(
            [str(row.get("scope") or ""), str(row.get("key") or ""),
             claim_value_text(row)] +
            [claim_value_text(c) for c in row.get("claims", []) if isinstance(c, dict)]
        )
        mentioned_paths = sorted(p for p in changed_paths if p and mentions(row_text, p))
        mentioned_nodes = sorted(n for n in node_ids if n and mentions(row_text, n))
        if not mentioned_paths and not mentioned_nodes:
            continue
        unresolved.append(
            {
                "subject": f"conflict:{row.get('key')}",
                "reason": "HUMAN_REQUIRED",
                "evidence": [
                    make_evidence(
                        "context_claim",
                        detail=row_text[:300],
                        claim_id=None,
                        claim_scope=row.get("scope"),
                        unverified=True,
                    )
                ],
                "note": "相关 CA conflict（paths: " + ", ".join(mentioned_paths)
                        + "; nodes: " + ", ".join(mentioned_nodes)
                        + "）；C 不选边，相关候选转人工",
            }
        )
        still_kept = []
        for proposal in kept:
            touched_nodes = set(proposal.get("node_ids") or [])
            change = proposal.get("proposed_change") or {}
            for key in ("node_id", "from", "to"):
                if change.get(key):
                    touched_nodes.add(change[key])
            evidence_paths = [e.get("path") for e in proposal.get("evidence", []) if e.get("path")]
            touches = (
                mentions(row_text, proposal["subject"])
                or any(mentions(row_text, node_id) for node_id in touched_nodes)
                or any(mentions(row_text, path) for path in evidence_paths)
            )
            if touches:
                unresolved.append(
                    {
                        "subject": proposal["subject"],
                        "reason": "HUMAN_REQUIRED",
                        "evidence": proposal["evidence"][:1],
                        "note": f"候选因相关 conflict {row.get('key')} 暂停，待人工裁决",
                    }
                )
                limits.append(
                    f"proposal moved to unresolved (related known conflict {row.get('key')}): "
                    f"{proposal['kind']}:{proposal['subject']}"
                )
            else:
                still_kept.append(proposal)
        kept = still_kept

    if pack_trusted and claims_for_context:
        annotated = 0
        for proposal in kept:
            tokens = _proposal_tokens(proposal)
            if not tokens:
                continue
            for claim_row in claims_for_context:
                key = str(claim_row.get("key") or "")
                if not key.startswith(_T1_DOMAINS):
                    continue
                text = " ".join([key, str(claim_row.get("scope") or ""),
                                 claim_value_text(claim_row)])
                if not any(mentions(text, token) for token in tokens):
                    continue
                proposal.setdefault("uncertainty", []).append(
                    _context_line(claim_row, ca.get("project_revision")))
                annotated += 1
        if annotated:
            limits.append(f"CA context enrichment: {annotated} labeled context line(s) "
                          "added to proposal uncertainty (never evidence)")
    return kept, limits, unresolved


def _independent_verification(ca, target_revision, limits, unresolved):
    """T3: check implementation.* head claims against C's own pin. Returns
    the claims that may still be consumed as context (None = pack
    contradicted, nothing may be consumed)."""
    claims = list(ca["claims"])
    contradicted = False
    for claim_row in claims:
        key = str(claim_row.get("key") or "")
        value = claim_row.get("value")
        if not key.startswith("implementation."):
            continue
        if not isinstance(value, dict) or not isinstance(value.get("head"), str) or not value["head"]:
            limits.append(f"context implementation claim unverifiable locally (UNKNOWN): "
                          f"{claim_row.get('claim_id')} ({key}); semantic external status "
                          "needs an independent verifier C does not run")
            continue
        head = value["head"]
        if not target_revision:
            limits.append(f"context head claim unverifiable without a pin (UNKNOWN): "
                          f"{claim_row.get('claim_id')} ({key})")
            continue
        if head == target_revision:
            limits.append(f"context head claim independently confirmed against the pinned "
                          f"target: {claim_row.get('claim_id')} ({key})")
            continue
        contradicted = True
        limits.append(
            f"context contradiction (independent observation differs): claim "
            f"{claim_row.get('claim_id')} ({key}) claims head {head}, pinned target is "
            f"{target_revision}; pack claims no longer consumed")
        unresolved.append(
            {
                "subject": f"claim:{claim_row.get('claim_id')}",
                "reason": "HUMAN_REQUIRED",
                "evidence": [
                    make_evidence("context_claim", detail=key, claim_id=claim_row.get("claim_id"),
                                  claim_scope=claim_row.get("scope"), unverified=True)
                ],
                "note": f"CA 主张�?C 的独立观察矛盾（主张 head {head}，pinned target "
                        f"{target_revision}）；以独立证据为准，pack 不再可信",
            }
        )
    if contradicted:
        return None
    return claims


def _proposal_tokens(proposal):
    """Paths and node ids a proposal touches (relevance tokens for T1)."""
    tokens = set()
    subject = proposal.get("subject")
    if isinstance(subject, str) and subject:
        tokens.add(subject)
    change = proposal.get("proposed_change") or {}
    for key in ("node_id", "from", "to"):
        value = change.get(key)
        if isinstance(value, str) and value:
            tokens.add(value)
    for item in proposal.get("evidence", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"]:
            tokens.add(item["path"])
    return tokens


def _context_line(claim_row, project_revision):
    """Labeled T1/T2 context line: provenance always shown, never evidence."""
    value = claim_row.get("value")
    verification = field_verification(claim_row)
    if verification:
        detail = "fields [" + "; ".join(f"{k}={v}" for k, v in sorted(verification.items())) + "]"
    else:
        detail = claim_value_text(value)[:80]
    freshness = claim_row.get("freshness", "unverified")
    return (f"CA 上下文[{freshness}] {claim_row.get('key')}@{claim_row.get('scope')}：{detail}"
            f"（人工参考，非事实证据；claim {claim_row.get('claim_id')}�?
            f"pack {str(project_revision)[:8]}�?)

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content tests/test_real_ca_integration.py; Get-Content tests/test_real_b_integration.py; git diff 78c2751 53f3580 -- tests/test_w3_relations.py tests/test_w4_ca_trust.py; Get-Content extensions/map_proposal/gitio.py' in G:\jiagou\projectmind-c-convergence
 succeeded in 343ms:
# -*- coding: utf-8 -*-
"""REAL CA integration (P05): packs built by the real Context Authority
builder (schema 0.1, integrity digest) are validated by the real
``validate_context_pack`` and consumed by C's trust boundary �?no mock
validator for the verdicts in this module.

Layer 1 (per contract §8): the real validator's own verdict is asserted
first (PASS for well-formed packs, REJECT for tampered ones).
Layer 2: C's behavior on the real pack.

Proven here: S19 (real conflict routing with real ``path:`` scopes �?the
R9 tune check), S20 (real stale partition never read), S21 (real
multi-scope selection layer), S24 (tampered real pack �?whole-pack
discard, independent candidates survive), S25 (validator-passing coherent
poison in a real pack attaches nothing), pack metadata round-trip.
Live-verifier-driven ``verification_unavailable`` rows require network
verifiers and stay component-level (recorded honestly as a limit).
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import ca_adapter, engine  # noqa: E402

REAL_CA_ROOT = Path(os.environ.get(
    "PROJECTMIND_REAL_CA_ROOT", r"G:\jiagou\projectmind-context-authority"))
REAL_CA_PACKAGE = REAL_CA_ROOT / "extensions" / "context_authority" / "context_pack.py"

A_CLASS = "class A:\n    pass\n"
B_CLASS = "class B:\n    pass\n"


def git(cwd, *args):
    out = subprocess.run(["git", "-C", str(cwd), *args], check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


def build_repo(base_files, target_files):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(repo, "init")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for path, content in base_files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    for path, content in target_files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD")
    return repo, base, target, tmp


def install_real_ca(test):
    """Make the REAL context_authority package importable as
    extensions.context_authority (C's seam) by extending the existing
    package path. Returns the real context_pack module."""
    if not REAL_CA_PACKAGE.is_file():
        raise unittest.SkipTest(f"real CA implementation not found: {REAL_CA_PACKAGE}")
    patcher = mock.patch.dict(sys.modules)
    patcher.start()
    test.addCleanup(patcher.stop)
    import extensions as extensions_pkg
    real_extensions_dir = str(REAL_CA_ROOT / "extensions")
    test.addCleanup(extensions_pkg.__path__.remove, real_extensions_dir)
    if real_extensions_dir not in extensions_pkg.__path__:
        extensions_pkg.__path__.append(real_extensions_dir)
    for name in ("extensions.context_authority", "extensions.context_authority.context_pack"):
        sys.modules.pop(name, None)
    module = importlib.import_module("extensions.context_authority.context_pack")
    return module


def claim(cid, key, ctype, scope, value, revision, ref="overnight fixture"):
    return {
        "id": cid,
        "key": key,
        "value": value,
        "type": ctype,
        "scope": scope,
        "source": {"kind": "human", "ref": ref},
        "revision": revision,
        "created_at": "2026-10-04T00:00:00Z",
    }


def node(node_id, paths):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def build_real_pack(test, repo, target, claims, task="map proposal review"):
    real = install_real_ca(test)
    registry = Path(tempfile.mkdtemp()) / "claims.jsonl"
    registry.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims),
        encoding="utf-8")
    pack = real.build_context_pack(task, str(repo), registry, revision=target,
                                   run_verifiers=False)
    real.validate_context_pack(pack, expected_revision=target)  # layer 1: PASS
    return pack, real


def node_map():
    return {
        "note": "m",
        "nodes": [node("na", ["pkg/a.py"]), node("nb", ["pkg/b.py"])],
        "edges": [{"from": "na", "to": "nb"}],
    }


class RealCAIntegrationTests(unittest.TestCase):
    def test_s19_s25_real_pack_conflict_routing_and_poison_non_attach(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            # Coherent poison: validator-passing neutral key, high-impact text.
            claim("claim-team-focus", "team.focus.overnight", "HUMAN_DECISION",
                  "global", "PR 35 is CLOSED and merged", target),
            # Conflict pair: same key+scope, different values �?real CONFLICT,
            # scoped to a changed path so row-level routing fires too (R9 tune:
            # real CA uses "path:pkg/..." scope strings �?C's word-boundary
            # mentions matching handles them).
            claim("claim-role-a", "architecture.pkg_a.role", "HUMAN_DECISION",
                  "path:pkg/a.py", "role: router", target),
            claim("claim-role-b", "architecture.pkg_a.role", "HUMAN_DECISION",
                  "path:pkg/a.py", "role: adapter", target),
            # Legitimate current claim (scope format = real "path:" style, R9).
            claim("claim-owner-a", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        self.assertEqual(len(pack["known_conflicts"]), 1)
        self.assertEqual(pack["known_conflicts"][0]["resolution"], "HUMAN_REQUIRED")
        self.assertTrue(any(row["key"] == "team.focus.overnight"
                            for row in pack["current_state"]["current_by_scope"]))
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                                     {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]},
                                     {"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.FULL)
        # Layer 2: related candidate suppressed via real "path:pkg/b.py" scope
        # (word-boundary, not substring); unrelated NODE_ADD survives.
        self.assertTrue(any(u["subject"].startswith("conflict:") for u in res["unresolved"]))
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(adds, [])
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])
        # S25: the poison claim never enters any proposal evidence/rationale.
        for proposal in res["proposals"]:
            for evidence in proposal["evidence"]:
                self.assertNotEqual(evidence["kind"], "context_claim")
                self.assertNotIn("PR 35 is CLOSED", str(evidence.get("detail", "")))
            self.assertNotIn("PR 35 is CLOSED", proposal["rationale"])

    def test_s20_real_stale_partition_never_read(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# touched\n", "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        # Real CA revision-binding semantics (recorded finding): only
        # implementation.* VERIFIED_FACT claims bind to a project revision.
        # A claim bound to the BASE revision is marked STALE by the real
        # resolver and routed to known_stale_sources, not current_by_scope.
        claims = [
            claim("claim-stale-arch", "implementation.pkg_a.state", "VERIFIED_FACT",
                  "path:pkg/a.py", {"state": "superseded by rework"}, base),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        self.assertEqual(pack["current_state"]["current_by_scope"], [])
        self.assertTrue(pack["known_stale_sources"])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.FULL)
        stale_text = "superseded by rework"
        for proposal in res["proposals"]:
            self.assertNotIn(stale_text, json.dumps(proposal, ensure_ascii=False))
        for unresolved in res["unresolved"]:
            self.assertNotIn(stale_text, json.dumps(unresolved, ensure_ascii=False))

    def test_s21_real_multi_scope_both_in_selection_layer(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS}, {"pkg/a.py": A_CLASS + "# t\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-ms-1", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
            claim("claim-ms-2", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "node:na", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        scopes = sorted(row["scope"] for row in pack["current_state"]["current_by_scope"])
        self.assertEqual(scopes, ["node:na", "path:pkg/a.py"])
        ca, mode, _ = ca_adapter.load_context(pack, target)
        self.assertEqual(mode, ca_adapter.FULL)
        got = sorted(c["scope"] for c in ca["claims"] if c["key"] == "architecture.pkg_a.owner")
        self.assertEqual(got, ["node:na", "path:pkg/a.py"])

    def test_s24_tampered_real_pack_rejected_whole_pack_discarded(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-legit", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        tampered = json.loads(json.dumps(pack))
        tampered["current_state"]["current_by_scope"][0]["value"] = {"owner": "attacker"}
        with self.assertRaises(real.ContextPackValidationError):  # layer 1: REJECT
            real.validate_context_pack(tampered, expected_revision=target)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                                     {"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": tampered,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)  # layer 2: C's behavior
        self.assertEqual(res["request"]["context_mode"], ca_adapter.DEGRADED)
        self.assertTrue(any("rejected" in l for l in res["limits"]))
        self.assertNotIn("attacker", json.dumps(res, ensure_ascii=False))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])

    def test_real_pack_metadata_round_trip(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS}, {"pkg/a.py": A_CLASS + "# t\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-meta", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        meta = res["context_authority"]
        self.assertEqual(meta["schema_version"], pack["schema_version"])
        self.assertEqual(meta["project_revision"], target)
        self.assertEqual(meta["registry_hash"], pack["current_state"]["registry_hash"])

    def test_p05b_t1_context_enrichment_labeled_relevant_only(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            # Relevant low-impact claim (mentions the touched path) �?T1 line.
            claim("claim-t1-relevant", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
            # Irrelevant claim (mentions nothing touched) �?no annotation.
            claim("claim-t1-irrelevant", "architecture.pkg_zzz.note", "HUMAN_DECISION",
                  "global", {"note": "unrelated module note"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        uncertainty = "\n".join(node_adds[0]["uncertainty"])
        self.assertIn("CA 上下文[unverified]", uncertainty)
        self.assertIn("claim-t1-relevant", uncertainty)
        self.assertIn("architecture.pkg_new.note", uncertainty)
        self.assertIn("人工参考，非事实证�?, uncertainty)
        self.assertNotIn("claim-t1-irrelevant", uncertainty)
        # Context never contaminates evidence or rationale (S-2/E-4).
        self.assertNotIn("context_claim",
                         {e["kind"] for p in res["proposals"] for e in p["evidence"]})
        self.assertNotIn("owner plans a rename", node_adds[0]["rationale"])
        self.assertTrue(any("CA context enrichment" in l for l in res["limits"]))

    def test_p05b_t3_head_contradiction_marks_pack_untrusted(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        wrong_head = "b" * 40
        claims = [
            claim("claim-head-wrong", "implementation.target_head", "VERIFIED_FACT",
                  "global", {"head": wrong_head}, target, ref="registry import"),
            # Would be T1-eligible if the pack were trusted �?it must NOT be.
            claim("claim-t1-muted", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertTrue(any("context contradiction" in l and wrong_head in l and target in l
                            for l in res["limits"]))
        self.assertTrue(any("pack claims no longer consumed" in l for l in res["limits"]))
        self.assertTrue(any(u["subject"] == "claim:claim-head-wrong"
                            and u["reason"] == "HUMAN_REQUIRED" for u in res["unresolved"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertFalse(any("CA 上下�? in u for u in node_adds[0]["uncertainty"]))
        self.assertNotIn("owner plans a rename", json.dumps(res["proposals"], ensure_ascii=False))

    def test_p05b_t3_head_confirmed_against_pin(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-head-ok", "implementation.target_head", "VERIFIED_FACT",
                  "global", {"head": target}, target, ref="registry import"),
            claim("claim-t1-alive", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertTrue(any("independently confirmed" in l for l in res["limits"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertTrue(any("CA 上下�? in u and "claim-t1-alive" in u
                            for u in node_adds[0]["uncertainty"]))

    def test_p05b_t2_field_level_support_labels(self):
        # T2 admission-layer semantics (S22): dict value with live_verification
        # �?verified fields labelled verified, others UNVERIFIED. Real live
        # verifiers need network and stay a recorded limit; the field map
        # contract is CA's own.
        ca = {
            "claims": [{
                "claim_id": "claim-t2",
                "key": "architecture.pkg_new.status",
                "scope": "path:pkg/new.py",
                "value": {"status": "planned", "owner": "someone"},
                "freshness": "verified",
                "evidence": [{"live_verification": {"verified_fields": ["status"]}}],
            }],
            "conflict_keys": set(),
            "unavailable_keys": set(),
            "conflict_rows": [],
            "schema_version": "0.1",
            "project_revision": "a" * 40,
            "registry_hash": "sha256:" + "0" * 64,
        }
        proposals = [{
            "kind": "NODE_ADD", "subject": "pkg/new.py", "node_ids": None,
            "proposed_change": {"title": "t", "summary": "s"},
            "rationale": "r", "evidence": [], "confidence": "low", "uncertainty": [],
        }]
        limits, unresolved = [], []
        kept, limits, unresolved = ca_adapter.apply_context_admission(
            proposals, ca, ca_adapter.FULL, {"pkg/new.py"}, {"na"}, limits, unresolved,
            target_revision="a" * 40)
        line = kept[0]["uncertainty"][-1]
        self.assertIn("status=verified", line)
        self.assertIn("owner=UNVERIFIED", line)
        self.assertIn("claim-t2", line)


if __name__ == "__main__":
    unittest.main()
# -*- coding: utf-8 -*-
"""REAL B integration (P04): the actual code_facts collector from the
validated B+D integration line runs inside C's pipeline �?no mocks for the
final verdict.

The collector is loaded from the real implementation file and registered as
``extensions.code_facts.facts`` in sys.modules (C's installed-B seam). This
is the real B code executing, not a stub. Tests skip with an explicit reason
only when the real implementation is absent from this machine; skips are
recorded in the acceptance matrix, never counted as PASS.

Oracles: S06 (real base declaration delta �?RESPONSIBILITY_CHANGE), S13
(real syntax-bad source �?real skipped semantics), S14 (real revision
mismatch / same-revision cannot bypass), S15 (real unavailable / collector
exception �?honest degradation), real-history end-to-end (Git compare �?real B facts �?C).

Ownership check: C's map_proposal modules use ast ONLY in relations.py
(import analysis is C's own inference domain); declaration parsing remains
B's product alone (plan §5 P05 boundary).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, facts_adapter, model  # noqa: E402

REAL_B_ROOT = Path(os.environ.get(
    "PROJECTMIND_REAL_B_ROOT", r"G:\jiagou\projectmind-integration-bd"))
REAL_B_FACTS = REAL_B_ROOT / "extensions" / "code_facts" / "facts.py"

A_CLASS = "class A:\n    pass\n"
B_CLASS = "class B:\n    pass\n"


def git(cwd, *args):
    out = subprocess.run(["git", "-C", str(cwd), *args], check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


def build_repo(base_files, target_files):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(repo, "init")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for path, content in base_files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    for path, content in target_files.items():
        if content is None:
            (repo / path).unlink()
            continue
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD")
    return repo, base, target, tmp


def install_real_b(test):
    """Register the REAL collector as C's installed-B seam. Returns the
    loaded module. Skips only when the real implementation is absent."""
    if not REAL_B_FACTS.is_file():
        raise unittest.SkipTest(f"real B implementation not found: {REAL_B_FACTS}")
    patcher = mock.patch.dict(sys.modules)
    patcher.start()
    test.addCleanup(patcher.stop)
    spec = importlib.util.spec_from_file_location("projectmind_real_b_facts", REAL_B_FACTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = types.ModuleType("extensions.code_facts")
    package.__path__ = []
    package.facts = module
    sys.modules["extensions.code_facts"] = package
    sys.modules["extensions.code_facts.facts"] = module
    return module


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def two_node_map(entry=None):
    return {
        "note": "m",
        "nodes": [node("na", ["pkg/a.py"], entry=entry), node("nb", ["pkg/b.py"])],
        "edges": [{"from": "na", "to": "nb"}],
    }


class RealBIntegrationTests(unittest.TestCase):
    def test_s02_s13_real_collector_supplied_pipeline(self):
        real = install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS,
             "pkg/bad.py": "def broken(:\n"},
        )
        self.addCleanup(tmp.cleanup)
        # Real collector against a real pinned revision: bad.py comes back in
        # skipped with the collector's own reason �?REAL skipped semantics.
        facts = real.collect_code_facts(repo, target, ["pkg/a.py", "pkg/b.py", "pkg/bad.py"])
        self.assertEqual(facts["revision"], target)
        self.assertEqual({f["path"] for f in facts["files"]}, {"pkg/a.py", "pkg/b.py"})
        self.assertEqual([s["path"] for s in facts["skipped"]], ["pkg/bad.py"])
        self.assertTrue(facts["skipped"][0]["reason"])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/bad.py", "status": "added"}],
            "code_facts": facts,
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
        # REAL skipped source: HUMAN_REQUIRED, no strong candidate depends on it.
        self.assertTrue(any(u["subject"] == "pkg/bad.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))
        self.assertEqual(
            [p for p in res["proposals"] if p["subject"] == "pkg/bad.py"], [])

    def test_s06_real_base_delta_gives_responsibility_change(self):
        install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": "def main():\n    return 1\n", "pkg/b.py": B_CLASS},
            {"pkg/a.py": "def run():\n    return 2\n", "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        # code_facts absent �?C collects target AND base through the REAL
        # installed collector; the declaration delta (main gone) is real.
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "current_map": two_node_map(entry="pkg/a.py · main()"),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["facts_source"], "installed")
        resp = [p for p in res["proposals"] if p["kind"] == "RESPONSIBILITY_CHANGE"]
        self.assertEqual(len(resp), 1)
        self.assertEqual(resp[0]["subject"], "na")
        self.assertEqual(resp[0]["status"], "PROPOSED")
        self.assertTrue(resp[0]["human_required"])
        evidence_text = json.dumps(resp[0]["evidence"], ensure_ascii=False)
        self.assertIn("main", evidence_text)
        self.assertIn(target[:8], evidence_text)

    def test_s14_real_revision_mismatch_rejected_same_revision_safe(self):
        real = install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# touched\n", "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        stale = real.collect_code_facts(repo, base, ["pkg/a.py", "pkg/b.py"])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "code_facts": stale,
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        with self.assertRaises(facts_adapter.FactsMismatch):
            engine.suggest_map(repo, request)
        # Same revision: gates run, then zero proposals (invariant 13).
        same = real.collect_code_facts(repo, target, ["pkg/a.py", "pkg/b.py"])
        request_same = {
            "base_revision": target,
            "target_revision": target,
            "changed_paths": [],
            "code_facts": same,
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request_same)
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(n["reason"] == "same_revision" for n in res["no_proposal"]))

    def test_real_wanted_paths_removed_path_strictness(self):
        real = install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/gone.py": B_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/gone.py": None, "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        # Real B is strict: a wanted path absent from the pinned tree rejects
        # the whole call (CodeFactsError) �?documented interface behavior.
        with self.assertRaises(real.CodeFactsError):
            real.collect_code_facts(repo, target, ["pkg/a.py", "pkg/gone.py"])
        # C never hands removed paths to the collector: engine's wanted list
        # only contains added/modified/renamed paths, so the pipeline runs.
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/gone.py", "status": "removed"}],
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["facts_source"], "installed")

    def test_s15_real_collector_unavailable_and_exception(self):
        # Unavailable: without the real module C degrades honestly and the
        # B-free channels (rename link) still fire.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": None, "pkg/a2.py": A_CLASS, "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a2.py", "status": "renamed",
                               "old_path": "pkg/a.py"}],
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["facts_source"], "none")
        self.assertEqual(res["status"], "degraded")
        links = [p for p in res["proposals"] if p["kind"] == "IMPLEMENTATION_LINK_CHANGE"]
        self.assertEqual(len(links), 1)
        # Collector exception: real B loaded, but the target is not a repo �?        # CodeFactsError �?degraded with limits, never fabricated facts.
        install_real_b(self)
        with mock.patch.dict(sys.modules):
            bogus = Path(tempfile.mkdtemp())  # not a git repository
            request_bad = {
                "base_revision": base,
                "target_revision": "a" * 40,
                "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
                "current_map": two_node_map(),
                "prior_decisions": [],
            }
            res_bad = engine.suggest_map(bogus, request_bad)
            self.assertEqual(res_bad["request"]["facts_source"], "none")
            self.assertEqual(res_bad["proposals"], [])
            self.assertTrue(any("degraded" in str(l).lower() or "unavailable" in str(l).lower()
                                or "降级" in str(l) for l in res_bad["limits"]))

    def test_real_history_end_to_end_deterministic_no_map_write(self):
        install_real_b(self)
        repo = ROOT
        target = git(repo, "rev-parse", "HEAD")
        base = git(repo, "rev-parse", "HEAD~5")
        raw = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-status", "-M", base, target],
            check=True, capture_output=True, text=True).stdout
        changed = []
        for line in raw.splitlines():
            parts = line.split("\t")
            if parts[0].startswith("R"):
                changed.append({"path": parts[2], "status": "renamed",
                                "old_path": parts[1]})
            elif parts[0] == "A":
                changed.append({"path": parts[1], "status": "added"})
            elif parts[0] == "M":
                changed.append({"path": parts[1], "status": "modified"})
            elif parts[0] == "D":
                changed.append({"path": parts[1], "status": "removed"})
        self.assertTrue(changed)
        real_map = {
            "note": "overnight real-history smoke",
            "nodes": [node("na", ["extensions/map_proposal/model.py"]),
                      node("ne", ["extensions/map_proposal/engine.py"])],
            "edges": [{"from": "na", "to": "ne"}],
        }
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": changed,
            "current_map": real_map,
            "prior_decisions": [],
        }
        map_files = [ROOT / "extensions" / "map_proposal" / name
                     for name in ("model.py", "engine.py")]
        before = {p: p.read_bytes() for p in map_files}
        first = engine.suggest_map(repo, request)
        second = engine.suggest_map(repo, request)
        after = {p: p.read_bytes() for p in map_files}
        self.assertEqual(before, after)  # no map write (S29)
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))  # deterministic
        for proposal in first["proposals"]:
            self.assertIn(proposal["kind"], model.PROPOSAL_KINDS)
            self.assertEqual(proposal["status"], "PROPOSED")
            self.assertTrue(proposal["human_required"])
            self.assertNotIn("position", proposal["proposed_change"])
            self.assertTrue(proposal["evidence"])
            self.assertNotIn("position", json.dumps(proposal))


if __name__ == "__main__":
    unittest.main()
diff --git a/tests/test_w3_relations.py b/tests/test_w3_relations.py
index cdef2ad..c491bfd 100644
--- a/tests/test_w3_relations.py
+++ b/tests/test_w3_relations.py
@@ -191,13 +191,18 @@ class RelationChannelTests(unittest.TestCase):
         self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"], [])
 
     def test_x13_import_rewrite_churn_no_relation(self):
+        # F06 contract: "同一规范化目标的写法变换不产生关系变化". The AST
+        # channel diffs RESOLVED import-target sets, so `import os` →
+        # `from os import path` (no repo-internal relation change) yields no
+        # signal at all — stronger than the old signal-then-suppress churn
+        # guard, whose "churn" limit diagnostic no longer exists.
         res = self.run_engine(
             {"pkg/a.py": "import os\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
             {"pkg/a.py": "from os import path\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
             two_node_map(),
         )
         self.assertEqual(res["proposals"], [])
-        self.assertTrue(any("churn" in l for l in res["limits"]))
+        self.assertEqual([l for l in res["limits"] if "import" in l], [])
 
     def test_x02_dynamic_import_unknown_unresolved(self):
         res = self.run_engine(
@@ -232,6 +237,92 @@ class RelationChannelTests(unittest.TestCase):
              if p["kind"] in ("RELATION_ADD", "RELATION_REMOVE_CANDIDATE")], [])
         self.assertTrue(any(u["subject"] == "pkg/a.py" for u in res["unresolved"]))
 
+    def test_adversarial_1a_relative_from_dot_import_submodule(self):
+        # Adversarial 1a (silent miss at 78c2751): `from . import b` must
+        # resolve .b against the source package and yield RELATION_ADD.
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
+            {"pkg/a.py": A_CLASS + "from . import b\n", "pkg/b.py": B_CLASS,
+             "pkg/__init__.py": ""},
+            two_node_map(),
+        )
+        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
+        self.assertEqual(len(adds), 1)
+        self.assertEqual((adds[0]["proposed_change"]["from"],
+                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
+
+    def test_adversarial_1b_relative_from_dot_module_import(self):
+        # Adversarial 1b (silent miss at 78c2751): `from .b import B`.
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
+            {"pkg/a.py": A_CLASS + "from .b import B\n", "pkg/b.py": B_CLASS,
+             "pkg/__init__.py": ""},
+            two_node_map(),
+        )
+        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
+        self.assertEqual(len(adds), 1)
+        self.assertEqual((adds[0]["proposed_change"]["from"],
+                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
+
+    def test_adversarial_3_from_package_import_submodule(self):
+        # Adversarial 3 (silent miss at 78c2751): `from pkg import b` where
+        # b is the submodule pkg/b.py — alias expansion must propose pkg.b.
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
+            {"pkg/a.py": A_CLASS + "from pkg import b\n", "pkg/b.py": B_CLASS,
+             "pkg/__init__.py": ""},
+            two_node_map(),
+        )
+        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
+        self.assertEqual(len(adds), 1)
+        self.assertEqual((adds[0]["proposed_change"]["from"],
+                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
+
+    def test_multiline_parenthesized_from_import(self):
+        # Adversarial 4 (silent miss at 78c2751), valid form: parenthesized
+        # multiline from-imports are AST-native, no line-based extractor.
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS + "from pkg.b import (\n    B,\n)\n", "pkg/b.py": B_CLASS},
+            two_node_map(),
+        )
+        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
+        self.assertEqual(len(adds), 1)
+        self.assertEqual((adds[0]["proposed_change"]["from"],
+                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
+
+    def test_invalid_multiline_import_is_unknown_not_silent(self):
+        # Adversarial 4 original form was a SyntaxError (`import (\n...`):
+        # unsupported/invalid syntax must surface as UNKNOWN (unresolved +
+        # limits), never as silent no-change (C-3).
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS + "import (\n    pkg.b,\n)\n", "pkg/b.py": B_CLASS},
+            two_node_map(),
+        )
+        self.assertEqual(res["proposals"], [])
+        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
+                            for u in res["unresolved"]))
+        self.assertTrue(any("import signal extraction unavailable" in l
+                            for l in res["limits"]))
+
+    def test_s03_domain_proof_is_ast_not_text(self):
+        # Mutation M4 (DROP L05 regression) showed no test bound the domain
+        # removal proof to AST: a remaining source file whose only "import"
+        # is docstring text must NOT retain the relation, so the removal
+        # candidate for the source that truly dropped the import still fires.
+        res = self.run_engine(
+            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS,
+             "pkg/a2.py": '"""from pkg.b import B"""\n' + A_CLASS, "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS,
+             "pkg/a2.py": '"""from pkg.b import B"""\n' + A_CLASS, "pkg/b.py": B_CLASS},
+            two_node_map(extra_na_paths=["pkg/a2.py"]),
+        )
+        removals = [p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"]
+        self.assertEqual(len(removals), 1)
+        self.assertEqual((removals[0]["proposed_change"]["from"],
+                          removals[0]["proposed_change"]["to"]), ("na", "nb"))
+
     def test_relation_add_determinism(self):
         base_files = {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS}
         target_files = {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS}
diff --git a/tests/test_w4_ca_trust.py b/tests/test_w4_ca_trust.py
index 3abdef4..5f08ec6 100644
--- a/tests/test_w4_ca_trust.py
+++ b/tests/test_w4_ca_trust.py
@@ -30,9 +30,13 @@ def node(node_id, paths):
     }
 
 
-def base_request(target, map_nodes, changed, facts_files, pack=None, prior=None):
+def base_request(target, map_nodes, changed, facts_files, pack=None, prior=None,
+                 base="c" * 40):
+    # `base` defaults to a syntactically-valid-but-nonexistent revision for
+    # pure ca_adapter-level tests; repo-backed AdmissionTests pass the real
+    # base so the (honest) import channel is not degraded by the fixture.
     return {
-        "base_revision": "c" * 40,
+        "base_revision": base,
         "target_revision": target,
         "changed_paths": changed,
         "code_facts": {"revision": target, "files": facts_files, "skipped": []},
@@ -145,7 +149,7 @@ class AdmissionTests(unittest.TestCase):
 
     def run_engine(self, pack):
         request = base_request(self.target, self.map_nodes, self.changed,
-                               self.facts_files, pack=pack)
+                               self.facts_files, pack=pack, base=self.base)
         with with_validator(passing_validator):
             return engine.suggest_map(self.repo, request)
 
@@ -169,9 +173,44 @@ class AdmissionTests(unittest.TestCase):
         self.assertNotIn("context_claim",
                          {e["kind"] for u in res["unresolved"] for e in u["evidence"]})
 
+    def test_s25_poison_never_attaches_when_proposals_exist(self):
+        # Mutation M3 (F03 regression) showed the no-attach invariant was only
+        # asserted on proposal-free results. Oracle S25 instantiated with a
+        # real candidate: a validator-passing neutral-key poison must not
+        # enter any proposal's evidence or rationale even when proposals exist.
+        pack = {
+            "schema_version": 1,
+            "current_state": {
+                "current_by_scope": [
+                    {"key": "team.focus.v1", "scope": "global",
+                     "value": "PR 35 is CLOSED and merged", "freshness": "verified"},
+                ],
+            },
+            "known_conflicts": [],
+        }
+        request = base_request(
+            self.target,
+            self.map_nodes,
+            [{"path": "pkg/a.py", "status": "modified"},
+             {"path": "pkg/new.py", "status": "added"}],
+            self.facts_files
+            + [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
+            pack=pack,
+            base=self.base,
+        )
+        with with_validator(passing_validator):
+            res = engine.suggest_map(self.repo, request)
+        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
+        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])
+        for proposal in res["proposals"]:
+            for evidence in proposal["evidence"]:
+                self.assertNotEqual(evidence["kind"], "context_claim")
+                self.assertNotIn("PR 35 is CLOSED", str(evidence.get("detail", "")))
+            self.assertNotIn("PR 35 is CLOSED", proposal["rationale"])
+
     def test_s24_invalid_pack_degrades_but_independent_candidates_survive(self):
         request = base_request(self.target, self.map_nodes, self.changed,
-                               self.facts_files,
+                               self.facts_files, base=self.base,
                                pack={"schema_version": 1, "nodes": "broken"})
         with with_validator(rejecting_validator):
             res = engine.suggest_map(self.repo, request)
@@ -198,6 +237,7 @@ class AdmissionTests(unittest.TestCase):
             self.facts_files
             + [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
             pack=pack,
+            base=self.base,
         )
         with with_validator(passing_validator):
             res = engine.suggest_map(self.repo, request)
@@ -217,7 +257,8 @@ class AdmissionTests(unittest.TestCase):
             ],
         }
         request = base_request(self.target, [node("node-a", ["pkg/a.py"])],
-                               self.changed, self.facts_files, pack=pack)
+                               self.changed, self.facts_files, pack=pack,
+                               base=self.base)
         with with_validator(passing_validator):
             res = engine.suggest_map(self.repo, request)
         # node-a must not be suppressed by node-api conflict text
# -*- coding: utf-8 -*-
"""Read-only Git access for C (P05, ported from LOCAL diff_model._git).

Environment is cleaned of GIT_* overrides, lazy fetch and external diffs are
disabled, every read is pinned to an explicit revision. Nothing here writes to
the repository or the working tree.
"""
from __future__ import annotations

import os
import subprocess


class DiffSignalError(ValueError):
    """A pinned Git read failed; the caller must degrade, never guess."""


def git(repo, *args) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "LC_ALL": "C",
        }
    )
    try:
        result = subprocess.run(
            ["git", "--no-lazy-fetch", "-C", str(repo), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiffSignalError("Git 读取失败或超�?) from exc
    if result.returncode:
        raise DiffSignalError("无法读取指定提交的内�?)
    return result.stdout


def ls_tree_names(repo, revision) -> set:
    """All repo-relative paths present at a pinned revision (one process)."""
    raw = git(repo, "ls-tree", "-r", "--name-only", "-z", revision)
    return {name for name in raw.decode("utf-8", errors="replace").split("\0") if name}


def read_blob(repo, revision, path) -> str:
    raw = git(repo, "show", f"{revision}:{path}")
    return raw.decode("utf-8", errors="replace")


def diff_patches(repo, base_revision, target_revision, paths) -> bytes:
    if not paths:
        return b""
    return git(
        repo,
        "diff",
        "--no-ext-diff",
        "-U0",
        base_revision,
        target_revision,
        "--",
        *sorted(set(paths)),
    )

codex
冻结 HEAD 与目标 SHA 一致。AST 改写和测试强化已核对；我发现 T1 的标量值处理可能导致异常，正在用内存探针验证，同时检查新增 alias 解析是否会误报子模块依赖。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "python -B -c \"from extensions.map_proposal import ca_adapter as c, relations as r; from unittest.mock import patch; import ast; row={'key':'team.note','scope':'path:pkg/a.py','value':'review this file','claim_id':'s','freshness':'unverified','evidence':[]}; ca={'claims':[row],'conflict_keys':set(),'unavailable_keys':set(),'conflict_rows':[],'project_revision':'a'*40}; p={'subject':'pkg/a.py','proposed_change':{},'evidence':[],'uncertainty':[]}; exec('try:\\n c.apply_context_admission([p],ca,c.FULL,{\\\"pkg/a.py\\\"},set(),[],[],target_revision=\\\"a\\\"*40)\\nexcept Exception as e:\\n print(type(e).__name__+\\\": \\\"+str(e))'); blobs={('base','pkg/a.py'):'',('target','pkg/a.py'):'from pkg import b\\n'}; known={'pkg/a.py','pkg/b.py','pkg/__init__.py'}; exec('with patch.object(r.gitio,\\\"read_blob\\\",side_effect=lambda repo,rev,path: blobs[(rev,path)]):\\n print(r._file_relation_events(None,\\\"base\\\",\\\"target\\\",{\\\"path\\\":\\\"pkg/a.py\\\",\\\"status\\\":\\\"modified\\\"},known))'); print('Python import semantics with existing attribute:', __import__('os',fromlist=['path']).path.__name__)\"; rg -n 'def _context_line|claim_value_text\\(value\\)|static.add|pack_trusted|conflict_rows|def test_p05b|SkipTest|REAL_.*ROOT|before =|map_files' extensions/map_proposal/ca_adapter.py extensions/map_proposal/relations.py tests/test_real*; Get-Content extensions/map_proposal/engine.py" in G:\jiagou\projectmind-c-convergence
 succeeded in 367ms:
  File "<string>", line 1
    from extensions.map_proposal import ca_adapter as c, relations as r; from unittest.mock import patch; import ast; row={'key':'team.note','scope':'path:pkg/a.py','value':'review this file','claim_id':'s','freshness':'unverified','evidence':[]}; ca={'claims':[row],'conflict_keys':set(),'unavailable_keys':set(),'conflict_rows':[],'project_revision':'a'*40}; p={'subject':'pkg/a.py','proposed_change':{},'evidence':[],'uncertainty':[]}; exec('try:\n c.apply_context_admission([p],ca,c.FULL,{" pkg/a.py\},set(),[],[],target_revision=\a\*40)\nexcept
                                                                                                                                                                                                                                                                                                                                                                                                                                                            ^
SyntaxError: unterminated string literal (detected at line 1)
rg: tests/test_real*: 文件名、目录名或卷标语法不正确。 (os error 123)
extensions/map_proposal/relations.py:86:                static.add(alias.name)
extensions/map_proposal/relations.py:90:                static.add(prefix)
extensions/map_proposal/relations.py:93:                    static.add(alias.name)
extensions/map_proposal/relations.py:95:                    static.add(prefix + alias.name)
extensions/map_proposal/relations.py:97:                    static.add(f"{prefix}.{alias.name}")
extensions/map_proposal/ca_adapter.py:49:    "conflict_rows": [],
extensions/map_proposal/ca_adapter.py:113:        "conflict_rows": [row for row in _rows(pack, "known_conflicts") if isinstance(row, dict)],
extensions/map_proposal/ca_adapter.py:184:    pack_trusted = claims_for_context is not None
extensions/map_proposal/ca_adapter.py:187:    for row in ca["conflict_rows"]:
extensions/map_proposal/ca_adapter.py:247:    if pack_trusted and claims_for_context:
extensions/map_proposal/ca_adapter.py:334:def _context_line(claim_row, project_revision):
extensions/map_proposal/ca_adapter.py:341:        detail = claim_value_text(value)[:80]
# -*- coding: utf-8 -*-
"""C convergence engine �?single canonical pipeline (R01/R06/R07 skeleton).

Pipeline (invariant order):
  request/path/pin validation �?Core compare adaptation �?B gate �?map intake
  �?independent signal channels (declaration / import / map / existence) �?  unified admission (skipped, evidence, conflicts, CA trust) �?four-bucket
  canonical result �?legacy compatibility projection.

W1 status: gates, canonical result, identity and projection are live; signal
channels are wired but empty until W2/W3 land. No map write ever happens here.
"""
from __future__ import annotations

from extensions.map_proposal import analysis, ca_adapter, facts_adapter, model, relations, gitio


def suggest_map(repo, data) -> dict:
    request = model.validate_request(model.adapt_core_compare(data))
    if request["current_map"] is None:
        raise model.RequestError("current_map 缺失：C 需要当前人工地图原文，不得�?snapshot 偷补")
    current_map = model.validate_map(request["current_map"])

    target = request["target_revision"]
    base = request["base_revision"]

    # Installed-B collection focuses on paths that can exist at target.
    wanted = [
        c["path"]
        for c in request["changed_paths"]
        if c["status"] in ("added", "modified", "renamed")
    ]
    facts, limits = facts_adapter.load_code_facts(request["code_facts"], repo, target, wanted)

    # W4: the pack is validated (real validator) before anything else and
    # consumed only through the admission layer; no claim is attached to
    # proposal evidence in this build (R04).
    ca, ca_mode, ca_limits = ca_adapter.load_context(request["context_pack"], target)
    limits.extend(ca_limits)

    changed_paths = set()
    for change in request["changed_paths"]:
        changed_paths.add(change["path"])
        if change["old_path"]:
            changed_paths.add(change["old_path"])

    proposals = []
    unresolved = facts_adapter.skipped_unresolved(changed_paths & facts["skipped"], target)
    no_proposal = []
    limits = _dedupe(limits)

    indexes = analysis.build_indexes(current_map)

    # Signal channels run independently (R01); a declaration-channel verdict on
    # one file never ends another channel's analysis of the same file (F05).
    # A changed path B skipped never feeds any strong candidate channel (F04);
    # its HUMAN_REQUIRED unresolved entry is already emitted above.
    # base==target: gates above already ran; every channel stays silent and the
    # zero-proposal same-revision branch below applies (invariant 13).
    modified_py_paths = [
        c["path"]
        for c in request["changed_paths"]
        if c["status"] == "modified" and c["path"].endswith(".py")
        and c["path"] not in facts["skipped"]
    ]
    base_facts = {"files": {}, "skipped": set(), "available": False}
    if base != target and modified_py_paths:
        base_facts, base_limits = facts_adapter.load_code_facts(None, repo, base, modified_py_paths)
        limits.extend(base_limits)

    if base != target:
        for change in request["changed_paths"]:
            path = change["path"]
            old_path = change.get("old_path")
            if path in facts["skipped"] or (old_path and old_path in facts["skipped"]):
                continue
            if change["status"] == "renamed":
                analysis.handle_renamed(change, base, target, indexes, facts, proposals, no_proposal)
            elif change["status"] == "added":
                analysis.handle_added(change, target, indexes, facts, proposals, unresolved, no_proposal)
            elif change["status"] == "modified":
                analysis.handle_modified(
                    change, target, base, indexes, facts, base_facts, proposals, unresolved, no_proposal
                )
            # removed paths are handled by the stale-map existence channel below.

        # R03: independent import-relation channel �?runs regardless of
        # declaration-channel verdicts (F05); skipped sources never feed it.
        # Full change dicts are passed so the channel can anchor the base
        # side of a rename at old_path and treat added files as empty bases.
        relation_changes = [
            c
            for c in request["changed_paths"]
            if c["path"].endswith(".py")
            and c["path"] not in facts["skipped"]
            and c["status"] in ("added", "modified", "renamed")
        ]
        known_paths = set(facts["files"]) | changed_paths | set(indexes["node_by_path"])
        relations.handle_relations(repo, base, target, indexes, facts, known_paths,
                                   relation_changes, proposals, unresolved, limits)

        # R05: stale-map target existence, independent of B availability.
        analysis.handle_stale_map(repo, base, target, request["changed_paths"], indexes,
                                  proposals, limits)
        limits = _dedupe(limits)

        # F20: human REJECTED subject/kind pairs stay suppressed.
        proposals, limits = analysis.apply_prior_decisions(
            proposals, request["prior_decisions"], limits
        )

        # R04: CA admission �?conflict routing, evidence trust boundary, and
        # P05B typed consumption (T1/T2 context, T3 independent verification
        # of implementation head claims against C's own pin).
        proposals, limits, unresolved = ca_adapter.apply_context_admission(
            proposals, ca, ca_mode, changed_paths, indexes["node_ids"], limits,
            unresolved, target_revision=target)

        # Single publication exit (invariant 2): every candidate goes through the
        # canonical proposal constructor with its invariants.
        proposals = [
            model.make_proposal(
                target,
                item["kind"],
                item["subject"],
                item["proposed_change"],
                item["rationale"],
                item["evidence"],
                item["confidence"],
                item["uncertainty"],
            )
            for item in proposals
        ]

    if base == target:
        # Invariant 13: gates above already ran; zero proposals, and map drift
        # is explicitly out of scope for a same-revision diff judgment.
        no_proposal.append(
            {
                "reason": "same_revision",
                "note": "base==target：已完成输入与事实一致性校验，零提案；地图漂移不属于本次差异判�?,
            }
        )
    elif not proposals and facts["available"]:
        no_proposal.append(
            {
                "reason": "no_cross_channel_signals",
                "note": "changed_paths 与地�?代码事实无交叉信�?,
            }
        )

    return _canonical_result(
        base=base,
        target=target,
        facts=facts,
        current_map=current_map,
        proposals=proposals,
        unresolved=unresolved,
        no_proposal=no_proposal,
        limits=limits,
        ca=ca,
        ca_mode=ca_mode,
    )


def _dedupe(values):
    seen = {}
    for item in values:
        seen.setdefault(str(item), None)
    return list(seen)


def _canonical_result(base, target, facts, current_map, proposals, unresolved,
                      no_proposal, limits, ca=None, ca_mode=ca_adapter.DEGRADED):
    proposals = sorted(proposals, key=lambda p: (p["kind"], p["subject"], p["proposal_id"]))
    unresolved = sorted(unresolved, key=lambda u: str(u.get("subject", "")))
    no_proposal = sorted(no_proposal, key=lambda n: str(n.get("reason", "")))

    # Honest status (R07): only rule generation exists; a request without a
    # real model run must never be labelled ai_candidate. Degraded is explicit
    # when the B dependency is unavailable.
    if not facts["available"]:
        status = "degraded"
    elif proposals:
        status = "rule_candidate"
    else:
        status = "empty"

    note_bits = []
    if not facts["available"]:
        note_bits.append("代码事实不可用，已降级运�?)
    note_bits.append(f"规则生成 {len(proposals)} 个候�?)
    note = "�?.join(note_bits)

    result = {
        "status": status,
        "revision": target,
        "candidates": _legacy_candidates(proposals),
        "note": note,
        "request": {
            "base_revision": base,
            "target_revision": target,
            "facts_source": facts["source"],
            "map_has_version_identity": current_map["has_version_identity"],
            "context_mode": ca_mode,
        },
        "proposals": proposals,
        "unresolved": unresolved,
        "no_proposal": no_proposal,
        "limits": limits,
    }
    if ca_mode == ca_adapter.FULL and ca is not None:
        result["context_authority"] = {
            "schema_version": ca["schema_version"],
            "project_revision": ca["project_revision"],
            "registry_hash": ca["registry_hash"],
        }
    return result


def _legacy_candidates(proposals):
    """K03: the old candidates field is a projection of already-admitted
    canonical NODE_ADD proposals �?it never carries extra or un-gated items."""
    out = []
    for proposal in proposals:
        if proposal["kind"] != "NODE_ADD":
            continue
        change = proposal["proposed_change"]
        out.append(
            {
                "title": change.get("title", proposal["subject"]),
                "summary": change.get("summary", proposal["rationale"]),
                "evidencePaths": sorted(
                    {e["path"] for e in proposal["evidence"] if e.get("path")}
                ),
                "unknowns": list(proposal["uncertainty"]),
            }
        )
    return out

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
from extensions.map_proposal import ca_adapter as c, relations as r
from unittest.mock import patch
row={'key':'team.note','scope':'path:pkg/a.py','value':'review this file','claim_id':'s','freshness':'unverified','evidence':[]}
ca={'claims':[row],'conflict_keys':set(),'unavailable_keys':set(),'conflict_rows':[],'project_revision':'a'*40}
p={'subject':'pkg/a.py','proposed_change':{},'evidence':[],'uncertainty':[]}
try:
 c.apply_context_admission([p],ca,c.FULL,{'pkg/a.py'},set(),[],[],target_revision='a'*40)
except Exception as e:
 print(type(e).__name__+': '+str(e))
blobs={('base','pkg/a.py'):'',('target','pkg/a.py'):'from pkg import b\\n'}
known={'pkg/a.py','pkg/b.py','pkg/__init__.py'}
with patch.object(r.gitio,'read_blob',side_effect=lambda repo,rev,path: blobs[(rev,path)]):
 print(r._file_relation_events(None,'base','target',{'path':'pkg/a.py','status':'modified'},known))
import sys, types
pkg=types.ModuleType('probe_pkg'); pkg.__path__=[]; pkg.b=42
sys.modules['probe_pkg']=pkg
exec('from probe_pkg import b', {})
print('attribute import loaded child:', 'probe_pkg.b' in sys.modules)
'@ | python -B -; rg -n 'def test_p05b|SkipTest|REAL_.*ROOT|before =|map_files' tests/test_real_b_integration.py tests/test_real_ca_integration.py; git show 78c2751:extensions/map_proposal/relations.py" in G:\jiagou\projectmind-c-convergence
 succeeded in 427ms:
AttributeError: 'str' object has no attribute 'get'
{'path': 'pkg/a.py', 'added': {'pkg/__init__.py': ['pkg'], 'pkg/b.py': ['pkg.b']}, 'removed': {}, 'dynamic': []}
attribute import loaded child: False
tests/test_real_b_integration.py:39:REAL_B_ROOT = Path(os.environ.get(
tests/test_real_b_integration.py:40:    "PROJECTMIND_REAL_B_ROOT", r"G:\jiagou\projectmind-integration-bd"))
tests/test_real_b_integration.py:41:REAL_B_FACTS = REAL_B_ROOT / "extensions" / "code_facts" / "facts.py"
tests/test_real_b_integration.py:81:        raise unittest.SkipTest(f"real B implementation not found: {REAL_B_FACTS}")
tests/test_real_b_integration.py:306:        map_files = [ROOT / "extensions" / "map_proposal" / name
tests/test_real_b_integration.py:308:        before = {p: p.read_bytes() for p in map_files}
tests/test_real_b_integration.py:311:        after = {p: p.read_bytes() for p in map_files}
tests/test_real_ca_integration.py:34:REAL_CA_ROOT = Path(os.environ.get(
tests/test_real_ca_integration.py:35:    "PROJECTMIND_REAL_CA_ROOT", r"G:\jiagou\projectmind-context-authority"))
tests/test_real_ca_integration.py:36:REAL_CA_PACKAGE = REAL_CA_ROOT / "extensions" / "context_authority" / "context_pack.py"
tests/test_real_ca_integration.py:74:        raise unittest.SkipTest(f"real CA implementation not found: {REAL_CA_PACKAGE}")
tests/test_real_ca_integration.py:79:    real_extensions_dir = str(REAL_CA_ROOT / "extensions")
tests/test_real_ca_integration.py:309:    def test_p05b_t1_context_enrichment_labeled_relevant_only(self):
tests/test_real_ca_integration.py:351:    def test_p05b_t3_head_contradiction_marks_pack_untrusted(self):
tests/test_real_ca_integration.py:389:    def test_p05b_t3_head_confirmed_against_pin(self):
tests/test_real_ca_integration.py:421:    def test_p05b_t2_field_level_support_labels(self):
# -*- coding: utf-8 -*-
"""Independent import-relation channel (R03, W3).

Signal source is the pinned diff; the *proof* is always an AST walk of the
pinned blobs (DROP L05: a regex on patch text is only a candidate-signal
extractor — docstring/comment import text never becomes a relation, a parse
failure never counts as "zero imports"). Declaration-channel verdicts never
gate this channel (F05): "declarations unchanged" does not mean "no import
signal" (X01/X11).

Removal proof domain is the whole map-node evidence domain (R03): a relation
removal candidate requires an existing map edge and ALL .py files of the
source node's evidence domain free of imports into the target domain at
target, with at least one such import at base (S03, X12 multi-source).
"""
from __future__ import annotations

import ast
import posixpath
import re

from extensions.map_proposal import gitio
from extensions.map_proposal.analysis import diff_evidence, map_node_evidence
from extensions.map_proposal.facts_adapter import path_eligibility
from extensions.map_proposal.model import make_evidence

_ADDED_STATIC = re.compile(r"^\+\s*(?:from\s+([\w.]+)\s+import\s+(.+)|import\s+([\w.,\s]+))")
_ADDED_DYNAMIC = re.compile(r"^\+\s*.*(?:importlib\.import_module|__import__)\s*\(")
_REMOVED_STATIC = re.compile(r"^-\s*(?:from\s+([\w.]+)\s+import\s+(.+)|import\s+([\w.,\s]+))")


def _modules(module, names):
    """Candidate module strings referenced by one import statement."""
    if module is not None:
        return [module]
    return [n.strip().split(" as ")[0].strip() for n in names.split(",") if n.strip()]


def import_signals(repo, base_revision, target_revision, changed_py_paths):
    """Candidate import events from the pinned patch (regex = candidates only)."""
    signals = {"added": [], "removed": [], "dynamic": []}
    if not changed_py_paths:
        return signals
    raw = gitio.diff_patches(repo, base_revision, target_revision, changed_py_paths)
    path = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("--- ") or path is None:
            continue
        added = _ADDED_STATIC.match(line)
        if added:
            module, from_names = added.group(1), added.group(2)
            plain_names = added.group(3) if module is None else None
            for module_name in _modules(module, from_names or plain_names or ""):
                signals["added"].append({"path": path, "module": module_name,
                                         "line": line.lstrip("+- ").strip()[:200]})
            continue
        if _ADDED_DYNAMIC.match(line):
            signals["dynamic"].append({"path": path, "line": line.lstrip("+- ").strip()[:200]})
            continue
        removed = _REMOVED_STATIC.match(line)
        if removed:
            module, from_names = removed.group(1), removed.group(2)
            plain_names = removed.group(3) if module is None else None
            for module_name in _modules(module, from_names or plain_names or ""):
                signals["removed"].append({"path": path, "module": module_name,
                                           "line": line.lstrip("+- ").strip()[:200]})
    return signals


def resolve_module(module, source_path, known_paths):
    """Module string → repo-relative path among known_paths. Absolute forms
    resolve directly; relative import targets resolve against the source
    file's package directory."""
    if not module:
        return None
    if module.startswith("."):
        depth = len(module) - len(module.lstrip("."))
        rest = module.lstrip(".").replace(".", "/")
        base_dir = posixpath.dirname(source_path)
        for _ in range(depth - 1):
            base_dir = posixpath.dirname(base_dir)
        base = posixpath.join(base_dir, rest) if rest else base_dir
    else:
        base = module.replace(".", "/")
    for candidate in (base + ".py", posixpath.join(base, "__init__.py")):
        if candidate in known_paths:
            return candidate
    return None


def imported_paths(repo, revision, source_path):
    """All import targets (resolved among repo paths is the caller's job) —
    returns the set of dotted module strings actually imported, via AST.
    Raises DiffSignalError on read/parse failure (never "zero")."""
    try:
        raw = gitio.read_blob(repo, revision, source_path)
        tree = ast.parse(raw)
    except (gitio.DiffSignalError, SyntaxError, ValueError) as exc:
        raise gitio.DiffSignalError(f"cannot verify imports of {source_path}@{revision[:8]}: "
                                    f"{type(exc).__name__}") from exc
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0) + (node.module or "")
            modules.add(prefix)
            if node.module:
                for alias in node.names:
                    modules.add(f"{node.module}.{alias.name}")
    return modules


def imports_target(repo, revision, source_path, module, target_path, known_paths):
    """True when source_path@revision actually (AST) imports a module that
    resolves to target_path. Raises DiffSignalError when the blob cannot be
    read or parsed."""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        if candidate.lstrip(".") != module.lstrip("."):
            continue
        if resolve_module(candidate.lstrip("."), source_path, known_paths) == target_path:
            return True
    return False


def handle_relations(repo, base, target, indexes, facts, known_paths, relation_paths,
                     proposals, unresolved, limits):
    try:
        signals = import_signals(repo, base, target, relation_paths)
    except gitio.DiffSignalError as exc:
        limits.append(f"import signal extraction failed: {exc}")
        return

    # Churn guard: the same (file, module) gaining and losing an import in one
    # diff is reformatting, not a relation change (X13).
    added_keys = {(s["path"], s["module"]) for s in signals["added"]}
    removed_keys = {(s["path"], s["module"]) for s in signals["removed"]}
    churn = added_keys & removed_keys
    if churn:
        limits.append("import churn suppressed (same module added and removed): "
                      + ", ".join(sorted(f"{p}:{m}" for p, m in churn)))
    signals["added"] = [s for s in signals["added"] if (s["path"], s["module"]) not in churn]
    signals["removed"] = [s for s in signals["removed"] if (s["path"], s["module"]) not in churn]

    for signal in signals["dynamic"]:
        if path_eligibility(signal["path"], facts) != "skipped":
            unresolved.append(
                {
                    "subject": signal["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, signal["path"],
                                               f"dynamic import: {signal['line']}")],
                    "note": "动态/字符串构造 import：依赖信号不足，不足以建立关系候选",
                }
            )

    emitted_pairs = set()
    for signal in signals["added"]:
        target_path = resolve_module(signal["module"], signal["path"], known_paths)
        if target_path is None:
            continue
        if path_eligibility(signal["path"], facts) == "skipped" or \
                path_eligibility(target_path, facts) == "skipped":
            continue
        source_owners = indexes["node_by_path"].get(signal["path"], [])
        target_owners = indexes["node_by_path"].get(target_path, [])
        if not source_owners or not target_owners or set(source_owners) == set(target_owners):
            continue
        # AST proof on the pinned target blob (docstring text never passes).
        try:
            if not imports_target(repo, target, signal["path"], signal["module"],
                                  target_path, known_paths):
                continue
        except gitio.DiffSignalError as exc:
            limits.append(f"import verification unavailable: {exc}")
            unresolved.append(
                {
                    "subject": signal["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, signal["path"], "import signal unverified")],
                    "note": "import 信号无法用 AST 证实（读取/解析失败），进入 UNKNOWN",
                }
            )
            continue
        pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
        if pair in emitted_pairs:
            continue
        emitted_pairs.add(pair)
        uncertainty, confidence = [], "low"
        if len(source_owners) > 1 or len(target_owners) > 1:
            uncertainty.append("multiple candidate nodes on this import edge")
        else:
            confidence = "medium"
        proposals.append(
            {
                "kind": "RELATION_ADD",
                "subject": f"{source_owners[0]}->{target_owners[0]}",
                "node_ids": None,
                "proposed_change": {
                    "from": source_owners[0],
                    "to": target_owners[0],
                    "label": f"import 依赖(候选): {signal['path']} -> {target_path}",
                },
                "rationale": "跨节点证据域新增实际 import（AST 证实）；方向与语义需人工确认",
                "evidence": [
                    diff_evidence(target, signal["path"], f"import added: {signal['line']}"),
                    diff_evidence(target, target_path, f"imported by {signal['path']}"),
                    map_node_evidence(source_owners[0], f"covers {signal['path']}"),
                    map_node_evidence(target_owners[0], f"covers {target_path}"),
                ],
                "confidence": confidence,
                "uncertainty": uncertainty,
            }
        )

    for signal in signals["removed"]:
        target_path = resolve_module(signal["module"], signal["path"], known_paths)
        if target_path is None:
            continue
        if path_eligibility(signal["path"], facts) == "skipped" or \
                path_eligibility(target_path, facts) == "skipped":
            continue
        source_owners = indexes["node_by_path"].get(signal["path"], [])
        target_owners = indexes["node_by_path"].get(target_path, [])
        if not source_owners or not target_owners or set(source_owners) == set(target_owners):
            continue
        # Removal needs an existing map edge between the two domains (R03).
        edge_exists = any(
            (source_owner, target_owner) in indexes["edge_set"]
            for source_owner in source_owners
            for target_owner in target_owners
        )
        if not edge_exists:
            continue
        pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
        if pair in emitted_pairs:
            continue
        verdict = _domain_import_gone(repo, base, target, indexes, signal["path"],
                                      source_owners, target_path, known_paths, limits)
        if verdict != "gone":
            continue
        emitted_pairs.add(pair)
        proposals.append(
            {
                "kind": "RELATION_REMOVE_CANDIDATE",
                "subject": f"{source_owners[0]}->{target_owners[0]}",
                "node_ids": None,
                "proposed_change": {
                    "from": source_owners[0],
                    "to": target_owners[0],
                    "label": f"import 移除(候选): {signal['path']} -> {target_path}",
                },
                "rationale": "源节点证据域内全部 .py 文件对目标域的静态 import 已消失（AST 证实）；"
                             "是否意味架构关系消失由人判断",
                "evidence": [
                    diff_evidence(base, signal["path"], f"import present at base: {signal['line']}"),
                    diff_evidence(target, signal["path"], "import removed at target"),
                    map_node_evidence(source_owners[0], f"covers {signal['path']}"),
                    map_node_evidence(target_owners[0], f"covers {target_path}"),
                ],
                "confidence": "low",
                "uncertainty": [],
            }
        )


def _domain_import_gone(repo, base, target, indexes, signal_path, source_owners,
                        target_path, known_paths, limits):
    """Removal proof over the FULL source node evidence domain: every .py
    file's imports into target_path must exist at base (somewhere in the
    domain) and be gone at target everywhere. Any read/parse failure →
    'unknown' (never treated as zero, DROP L05)."""
    domain_paths = []
    for owner in source_owners:
        for node in indexes["nodes"]:
            if node["id"] == owner:
                domain_paths.extend(p for p in node["evidence_paths"] if p.endswith(".py"))
    domain_paths = sorted(set(domain_paths))
    if signal_path not in domain_paths:
        domain_paths.append(signal_path)
    if not domain_paths:
        return "insufficient"

    had_import_at_base = False
    for path in domain_paths:
        try:
            at_base = _imports_target_loose(repo, base, path, target_path, known_paths)
            at_target = _imports_target_loose(repo, target, path, target_path, known_paths)
        except gitio.DiffSignalError as exc:
            limits.append(f"import removal proof unavailable: {exc}")
            return "unknown"
        if at_base:
            had_import_at_base = True
        if at_target:
            return "retained"
    return "gone" if had_import_at_base else "insufficient"


def _imports_target_loose(repo, revision, source_path, target_path, known_paths):
    """Does any AST import of source_path@revision resolve to target_path?"""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        absolute = candidate.lstrip(".")
        if resolve_module(absolute, source_path, known_paths) == target_path:
            return True
    return False

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
from extensions.map_proposal import relations as r, ca_adapter as c
from unittest.mock import patch
blobs={('base','pkg/a.py'):\"__import__('pkg.b')\\n\",('target','pkg/a.py'):\"__import__('pkg.c')\\n\"}
with patch.object(r.gitio,'read_blob',side_effect=lambda repo,rev,path:blobs[(rev,path)]):
 print('dynamic changed:',r._file_relation_events(None,'base','target',{'path':'pkg/a.py','status':'modified'},{'pkg/a.py','pkg/b.py','pkg/c.py'}))
ca={'claims':[{'key':'implementation.head','value':{'head':'b'*40},'claim_id':'bad','scope':'global'}],'conflict_keys':{'architecture.role'},'unavailable_keys':set(),'conflict_rows':[{'key':'architecture.role','scope':'path:pkg/a.py','value':'conflict'}]}
p={'subject':'pkg/a.py','kind':'NODE_ADD','proposed_change':{},'evidence':[{'path':'pkg/a.py'}]}
kept,limits,unresolved=c.apply_context_admission([p],ca,c.FULL,{'pkg/a.py'},set(),[],[],target_revision='a'*40)
print('untrusted pack still suppresses:',len(kept),[u['subject'] for u in unresolved])
'@ | python -B -; Get-Content extensions/map_proposal/extension.py; Get-Content tests/test_real_ca_integration.py | Select-Object -Skip 350 -First 105; rg -n 'dynamic|AST|F06|未知|UNKNOWN|11\\.' extensions/map_proposal/convergence/CONTRACT_MANIFEST.md extensions/map_proposal/convergence/ORACLE_MANIFEST.md; git status --short" in G:\jiagou\projectmind-c-convergence
 succeeded in 468ms:
dynamic changed: {'path': 'pkg/a.py', 'added': {}, 'removed': {}, 'dynamic': []}
untrusted pack still suppresses: 0 ['claim:bad', 'conflict:architecture.role', 'pkg/a.py']
# -*- coding: utf-8 -*-
"""Map Proposal extension (Role C) �?convergence handler seam (K01).

The handler keeps the registered route, the extension identity and the
ExtensionHost contract. All C logic lives in the single canonical scheduler
(engine.suggest_map); there is no second candidate engine and no shared
mutable request state between calls. Input errors are controlled rejections;
the legacy envelope is a projection of the canonical four-bucket result (K03).
"""

from http import HTTPStatus
from pathlib import Path

from extension_host import ExtensionError

from extensions.map_proposal import engine, model
from extensions.map_proposal.facts_adapter import FactsMismatch

EXTENSION = {
    "title": "项目地图提案 (Map Proposal)",
    "description": "基于 pinned Git diff、B 代码事实、当前人工地图与可�?Context Authority 底座，提出六类候选提案；不写正式地图�?,
}


def handle(context, method: str, data: dict) -> dict:
    if method not in ("POST", "GET"):
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, "此扩展仅支持 POST �?GET 请求")

    try:
        return engine.suggest_map(Path(context.repo), data or {})
    except (model.RequestError, FactsMismatch) as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    except ValueError as exc:
        # Internal invariant violation (proposal shape, evidence kinds) must
        # not surface internals or secrets as a seemingly valid response.
        raise ExtensionError(HTTPStatus.INTERNAL_SERVER_ERROR, "候选发布不变式被违�?) from exc
    def test_p05b_t3_head_contradiction_marks_pack_untrusted(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        wrong_head = "b" * 40
        claims = [
            claim("claim-head-wrong", "implementation.target_head", "VERIFIED_FACT",
                  "global", {"head": wrong_head}, target, ref="registry import"),
            # Would be T1-eligible if the pack were trusted �?it must NOT be.
            claim("claim-t1-muted", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertTrue(any("context contradiction" in l and wrong_head in l and target in l
                            for l in res["limits"]))
        self.assertTrue(any("pack claims no longer consumed" in l for l in res["limits"]))
        self.assertTrue(any(u["subject"] == "claim:claim-head-wrong"
                            and u["reason"] == "HUMAN_REQUIRED" for u in res["unresolved"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertFalse(any("CA 上下�? in u for u in node_adds[0]["uncertainty"]))
        self.assertNotIn("owner plans a rename", json.dumps(res["proposals"], ensure_ascii=False))

    def test_p05b_t3_head_confirmed_against_pin(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-head-ok", "implementation.target_head", "VERIFIED_FACT",
                  "global", {"head": target}, target, ref="registry import"),
            claim("claim-t1-alive", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertTrue(any("independently confirmed" in l for l in res["limits"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertTrue(any("CA 上下�? in u and "claim-t1-alive" in u
                            for u in node_adds[0]["uncertainty"]))

    def test_p05b_t2_field_level_support_labels(self):
        # T2 admission-layer semantics (S22): dict value with live_verification
        # �?verified fields labelled verified, others UNVERIFIED. Real live
        # verifiers need network and stay a recorded limit; the field map
        # contract is CA's own.
        ca = {
            "claims": [{
                "claim_id": "claim-t2",
                "key": "architecture.pkg_new.status",
                "scope": "path:pkg/new.py",
                "value": {"status": "planned", "owner": "someone"},
                "freshness": "verified",
                "evidence": [{"live_verification": {"verified_fields": ["status"]}}],
            }],
            "conflict_keys": set(),
            "unavailable_keys": set(),
            "conflict_rows": [],
            "schema_version": "0.1",
            "project_revision": "a" * 40,
            "registry_hash": "sha256:" + "0" * 64,
        }
        proposals = [{
            "kind": "NODE_ADD", "subject": "pkg/new.py", "node_ids": None,
            "proposed_change": {"title": "t", "summary": "s"},
            "rationale": "r", "evidence": [], "confidence": "low", "uncertainty": [],
        }]
        limits, unresolved = [], []
        kept, limits, unresolved = ca_adapter.apply_context_admission(
            proposals, ca, ca_adapter.FULL, {"pkg/new.py"}, {"na"}, limits, unresolved,
            target_revision="a" * 40)
        line = kept[0]["uncertainty"][-1]
        self.assertIn("status=verified", line)
        self.assertIn("owner=UNVERIFIED", line)
        self.assertIn("claim-t2", line)

extensions/map_proposal/convergence/ORACLE_MANIFEST.md:22:| S16 | A16 stale map | 早于 base 删除、target 全 evidence 缺失仍有 stale removal candidate；读取未知 ≠ 缺失。base==target 零 proposal + map drift limit。 | A16-valid-map `4f95f010...`、F11/F15 |
extensions/map_proposal/convergence/ORACLE_MANIFEST.md:24:| S18 | A18 missing evidence | 新文件但 facts/diff 证据不足: unresolved UNKNOWN、零强候选；B 没条目 ≠ 架构不存在。 | A18; 无声明/缺关键证据 |
extensions/map_proposal/convergence/ORACLE_MANIFEST.md:26:| S20 | A20 stale claim | validated stale 与其他非现行分区不进 context_claim；相关消费需求有 limits/UNKNOWN。 | A20; stale/proposal/research/history 分区 |
extensions/map_proposal/convergence/ORACLE_MANIFEST.md:29:| S23 | A23 unavailable | 合法 unavailable/stale fixture 先 validator PASS；C 不伪作坏包 DEGRADED；相关值排除且明确 UNKNOWN/limits。 | A23 `b3addc5a...`; 替换旧 C_A23 自测 |
extensions/map_proposal/convergence/ORACLE_MANIFEST.md:31:| S25 | A25 coherent poison | 结构与 digest 合法的 poison 不进 evidence/rationale；高影响事实有独立真值或 UNKNOWN；矛盾记录 claim_id/双方值，pack 不再可信。 | A25、X05/X16/X17 `ea8cbd8f...`(X17); 中性 key/自由文本、核验不可用 |
extensions/map_proposal/convergence/ORACLE_MANIFEST.md:44:- 动态/相对等不支持信号必须有 UNKNOWN 正面断言。F18 无交叉信号、F19 动态依赖、F20 人工否决、X07 mode、X09 ID collision、多文件关系删除证明为 30 项内部必要变体。
extensions/map_proposal/convergence/CONTRACT_MANIFEST.md:8:1. 输入 = pinned Git diff + B 声明事实 + 当前人工 Project Map + 可选 CA；输出 = `proposals / unresolved / no_proposal / limits` + 请求与事实底座追踪。`UNKNOWN` 进 unresolved，不进强 proposal。
extensions/map_proposal/convergence/CONTRACT_MANIFEST.md:16:9. 依赖信号来自实际 pinned Git diff。允许 base/target import AST 验证信号、排除字符串/docstring；不得借此重做 B 声明解析。声明未变 ≠ import 未变。
extensions/map_proposal/convergence/CONTRACT_MANIFEST.md:18:11. CA 只读 current_by_scope；verified_fields 按字段判定。非现行分区、conflict/unavailable key 不进 proposal context evidence。revision 对应/PR 状态/contract shape/implementation 状态须独立 git/gh 核验；state/merged/draft 分别核对；不可用 = UNKNOWN；矛盾以独立证据为准、记录 claim_id 与双方值、pack 不再可信。

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n 'target_dynamic|base_dynamic|dynamic.add|def claim_value_text|def _independent_verification|for row in ca|pack_trusted|detail = claim' extensions/map_proposal/relations.py extensions/map_proposal/ca_adapter.py; Get-Content tests/test_real_b_integration.py | Select-Object -First 110; rg -n 'value|validate.*claim|current_by_scope' G:/jiagou/projectmind-context-authority/extensions/context_authority/context_pack.py | Select-Object -First 35; rg -n 'write|open\\(|save|accept|position' extensions/map_proposal --glob '*.py'" in G:\jiagou\projectmind-c-convergence
 succeeded in 392ms:
extensions/map_proposal/ca_adapter.py:120:def claim_value_text(claim):
extensions/map_proposal/ca_adapter.py:184:    pack_trusted = claims_for_context is not None
extensions/map_proposal/ca_adapter.py:187:    for row in ca["conflict_rows"]:
extensions/map_proposal/ca_adapter.py:247:    if pack_trusted and claims_for_context:
extensions/map_proposal/ca_adapter.py:270:def _independent_verification(ca, target_revision, limits, unresolved):
extensions/map_proposal/ca_adapter.py:341:        detail = claim_value_text(value)[:80]
extensions/map_proposal/relations.py:101:                dynamic.add("__import__")
extensions/map_proposal/relations.py:103:                dynamic.add("importlib.import_module")
extensions/map_proposal/relations.py:137:        base_dynamic = _scan_imports(_parse_blob(repo, base, base_ref))[1]
extensions/map_proposal/relations.py:139:        base_resolved, base_dynamic = {}, set()
extensions/map_proposal/relations.py:140:    target_static, target_dynamic = _scan_imports(_parse_blob(repo, target, path))
extensions/map_proposal/relations.py:150:        "dynamic": sorted(target_dynamic - base_dynamic),
# -*- coding: utf-8 -*-
"""REAL B integration (P04): the actual code_facts collector from the
validated B+D integration line runs inside C's pipeline �?no mocks for the
final verdict.

The collector is loaded from the real implementation file and registered as
``extensions.code_facts.facts`` in sys.modules (C's installed-B seam). This
is the real B code executing, not a stub. Tests skip with an explicit reason
only when the real implementation is absent from this machine; skips are
recorded in the acceptance matrix, never counted as PASS.

Oracles: S06 (real base declaration delta �?RESPONSIBILITY_CHANGE), S13
(real syntax-bad source �?real skipped semantics), S14 (real revision
mismatch / same-revision cannot bypass), S15 (real unavailable / collector
exception �?honest degradation), real-history end-to-end (Git compare �?real B facts �?C).

Ownership check: C's map_proposal modules use ast ONLY in relations.py
(import analysis is C's own inference domain); declaration parsing remains
B's product alone (plan §5 P05 boundary).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, facts_adapter, model  # noqa: E402

REAL_B_ROOT = Path(os.environ.get(
    "PROJECTMIND_REAL_B_ROOT", r"G:\jiagou\projectmind-integration-bd"))
REAL_B_FACTS = REAL_B_ROOT / "extensions" / "code_facts" / "facts.py"

A_CLASS = "class A:\n    pass\n"
B_CLASS = "class B:\n    pass\n"


def git(cwd, *args):
    out = subprocess.run(["git", "-C", str(cwd), *args], check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


def build_repo(base_files, target_files):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(repo, "init")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for path, content in base_files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    for path, content in target_files.items():
        if content is None:
            (repo / path).unlink()
            continue
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD")
    return repo, base, target, tmp


def install_real_b(test):
    """Register the REAL collector as C's installed-B seam. Returns the
    loaded module. Skips only when the real implementation is absent."""
    if not REAL_B_FACTS.is_file():
        raise unittest.SkipTest(f"real B implementation not found: {REAL_B_FACTS}")
    patcher = mock.patch.dict(sys.modules)
    patcher.start()
    test.addCleanup(patcher.stop)
    spec = importlib.util.spec_from_file_location("projectmind_real_b_facts", REAL_B_FACTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = types.ModuleType("extensions.code_facts")
    package.__path__ = []
    package.facts = module
    sys.modules["extensions.code_facts"] = package
    sys.modules["extensions.code_facts.facts"] = module
    return module


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def two_node_map(entry=None):
    return {
        "note": "m",
        "nodes": [node("na", ["pkg/a.py"], entry=entry), node("nb", ["pkg/b.py"])],
        "edges": [{"from": "na", "to": "nb"}],
    }
17:                                                validate_json_value)
42:def _canonical(value) -> str:
43:    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
87:           "value": copy.deepcopy(row["value"]), "source": source,
107:    values = {item["live_verification"].get("freshness", "verified") for item in evidence}
108:    return next(iter(values)) if len(values) == 1 else "mixed"
124:    rows = state.get("current_by_scope", [{"key": k, **v} for k, v in state["current"].items()])
126:        value = row.get("value")
127:        if isinstance(value, dict) and value.get("status") in ("PR_OPEN", "OPEN"):
128:            rules.append(f"PR #{value.get('pr', 'unknown')} is OPEN - OPEN does not mean merged; "
141:        rules.append("Verification is unavailable for some claims - stored values are not live verification")
169:    rows = state.get("current_by_scope", [{"key": k, **v} for k, v in state["current"].items()])
190:                                      for k in ("key", "scope", "type", "value", "source")},
225:            "current_state": {"current": current, "current_by_scope": current_rows,
280:    require(isinstance(cs, dict) and set(cs) == {"current", "current_by_scope", "counts", "registry_hash"}, "invalid current_state")
281:    require(isinstance(cs["current"], dict) and isinstance(cs["current_by_scope"], list), "invalid current projections")
285:        required = {"claim_id", "key", "scope", "type", "value", "source", "revision", "claim_revision", "source_revision"}
294:        validate_json_value(item["value"])
308:        for value in (item["claim_revision"], item["source_revision"]):
309:            require(value is None or (isinstance(value, str) and bool(value)), "invalid evidence revision")
326:    for item in references.values():
336:                            ("key", "scope", "type", "value", "source", "claim_revision", "source_revision")), "derivation provenance contradiction")
340:        require(isinstance(row, dict) and {"key", "scope", "type", "value", "source"} <= set(row), "incomplete claim row")
347:            require(all(evidence[f] == row[f] for f in ("key", "scope", "value")), "claim/evidence contradiction")
353:            require(set(row) <= {"key", "scope", "type", "types", "value", "source", "claim_ids", "evidence",
367:            allowed = {"claim_id", "key", "scope", "type", "state", "value", "source", "revision", "created_at",
368:                       "verified_at", "notes", "supersedes", "superseded_by", "stale_reason", "live_value",
374:    for row in cs["current_by_scope"]:
380:    projected = _current_projection(cs["current_by_scope"], pack["known_conflicts"], pack["verification_unavailable"])
385:            require(pack[section] == [row for row in cs["current_by_scope"] if row["type"] == ctype], f"{section} contradicts current")
416:        values = set()
421:            values.add(_canonical(row["value"]))
428:            require(len(values) >= 2, "conflict alternatives do not differ")
438:    expected_counts = {"current": len(cs["current_by_scope"]), "conflicts": len(pack["known_conflicts"]),
441:    require(cs["counts"] == expected_counts and all(type(n) is int for n in cs["counts"].values()), "counts contradict sections")
extensions/map_proposal\relations.py:24:Known edge: a rewrite between from-import shapes can add/drop the bare
extensions/map_proposal\model.py:274:    if "position" in proposed_change:
extensions/map_proposal\model.py:275:        raise ValueError("proposed_change 不得包含 position")
extensions/map_proposal\gitio.py:5:disabled, every read is pinned to an explicit revision. Nothing here writes to
extensions/map_proposal\engine.py:11:channels are wired but empty until W2/W3 land. No map write ever happens here.

codex
内存探针已复现三个问题：相关字符串 claim 触发 `AttributeError`；已有动态 import 改换目标后不产生 UNKNOWN；pack 被判定不可信后，冲突记录仍能压制候选。另一个精度问题是：`from pkg import b` 会被解析为 `pkg/b.py` 依赖，即使 `b` 是包已定义的普通属性。全套测试会创建临时仓库，本次只读审查未重跑。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content extensions/map_proposal/convergence/CONTRACT_MANIFEST.md | Select-Object -Skip 5 -First 17; Get-Content tests/audit_probes.py | Select-Object -First 45; Get-Content tests/audit_w3_adversarial.py | Select-Object -First 30; git diff --check 78c2751 53f3580' in G:\jiagou\projectmind-c-convergence
 succeeded in 402ms:

1. 输入 = pinned Git diff + B 声明事实 + 当前人工 Project Map + 可�?CA；输�?= `proposals / unresolved / no_proposal / limits` + 请求与事实底座追踪。`UNKNOWN` �?unresolved，不进强 proposal�?2. 六类候�? `NODE_ADD / RELATION_ADD / RELATION_REMOVE_CANDIDATE / IMPLEMENTATION_LINK_CHANGE / NODE_REMOVE_CANDIDATE / RESPONSIBILITY_CHANGE`。每项完整字段、非空可定位 revision/path evidence、confidence、uncertainty、`status=PROPOSED`、`human_required=true`�?3. C 不写正式地图、不建议 position、不自行 accept/reject、不仲裁 CA conflict、不复制 B 声明解析、不编辑 CA registry、不接管 D worklog。职�?架构归属/关系含义 = INFERENCE；声�?路径/diff = FACT�?4. base/target 必须完整 40/64 位小�?SHA。缺 pin、HEAD、短 SHA 一律拒绝；不得�?snapshot 偷补。地图无版本身份，target SHA 不能证明地图适用�?5. compare 来源�?A/caller �?changed_paths。Core `baseRevision / targetRevision / changes[{code,path,oldPath?}]` 经显式适配映射；C 不另建文件差异口径。只�?pinned patch/blob，不从工作树补证据�?6. 地图�?Core `{note,nodes,edges}` 接收；非�?nodes �?title/summary/entryPoint/position/evidence 约束不得被测试替身放宽。输入保�?position；候�?proposed_change 不含 position�?7. B 事实仅含 revision/files/skipped 与声�?name/kind/line；无 import/签名/调用�?职责。所有目标事实来源验�?revision == target（含安装 B 返回值、同版本比较、空 diff）。必�?base 声明证据�?B 独立 pinned base 收集并标 base 角色�?8. changed 文件�?B skipped �?HUMAN_REQUIRED unresolved；不得继续作为节�?关系强候选的事实基础。B 不可�?�?limits；可运行安全 diff↔map；需 B 的新增节点进 unresolved，不虚构 code_fact�?9. 依赖信号来自实际 pinned Git diff。允�?base/target import AST 验证信号、排除字符串/docstring；不得借此重做 B 声明解析。声明未�?�?import 未变�?10. Context Pack 先真�?`validate_context_pack(pack, expected_revision=C 独立 pin)`。失败整包弃用，显式 DEGRADED/limits 后可�?pack 运行�?硬停�?= 停止消费�?pack，不是终�?C 服务�?11. CA 只读 current_by_scope；verified_fields 按字段判定。非现行分区、conflict/unavailable key 不进 proposal context evidence。revision 对应/PR 状�?contract shape/implementation 状态须独立 git/gh 核验；state/merged/draft 分别核对；不可用 = UNKNOWN；矛盾以独立证据为准、记�?claim_id 与双方值、pack 不再可信�?12. 相关 conflict �?unresolved HUMAN_REQUIRED；C 不选边。未覆盖 �?不存在；不解�?do_not_assume 中的数字。相同固定输�?+ 固定独立观察 = 相同输出；不嵌时间戳/随机值�?13. `base==target` 先完成必需输入/事实一致性校验，再返回零 proposal，并说明 map drift 不属于本次差异判断。人�?REJECTED、同 subject/kind 且理由未变的候选遵�?F20 抑制；无交叉信号不制造人工任务�?
## 收敛后单一决策路径

请求/路径/pin 校验 �?Core compare 适配 �?B �?CA 入口校验 �?独立收集声明变化/import 变化/地图路径映射/目标存在�?�?按候选来源统一检�?skipped、证据、冲突、CA 准入 �?四桶输出 �?兼容字段投影�?
各信号通道独立运行；任何单一通道不得�?声明没变"结束整个文件分析。结果发布只有一个出口：不做两套引擎 union，不在未完成准入检查时向旧 candidates 字段写候选�?
# -*- coding: utf-8 -*-
"""Anti-false-green probe: reproduce the five original core defects on the
FROZEN old implementations (old FAIL) and verify the convergence HEAD behavior
(new PASS) with the same fixtures. No mutation of either implementation.

Runs against:
- TEAM frozen extension via git show 3bd980d:extensions/map_proposal/extension.py
- LOCAL frozen repo (read-only) via PYTHONPATH
- convergence HEAD via repo imports
"""
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONV_ROOT = HERE.parent
LOCAL_ROOT = Path("C:/Users/李则�?AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local")
TEAM_SHA = "3bd980ded7a9cc727c1f00c84cf3c2b89c574e40"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True).stdout


def build_repo(base_files, target_files):
    tmp = tempfile.mkdtemp()
    repo = Path(tmp)
    git(repo, "init")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    write_tree(repo, base_files)
    git(repo, "add", "-A")
    git(repo, "commit", "--allow-empty", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").decode().strip()
    write_tree(repo, target_files)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD").decode().strip()
    return repo, base, target

# -*- coding: utf-8 -*-
"""Adversarial probes for the W3 import-relation channel (audit task 9).
Cases were NOT designed with the implementation in view; results are recorded
as-is. Each case builds a real temp git repo and runs the convergence engine.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine  # noqa: E402
from tests.test_w3_relations import build_repo, node  # noqa: E402

MAP2 = {
    "note": "m",
    "nodes": [
        node("na", ["pkg/a.py"]),
        node("nb", ["pkg/b.py"]),
    ],
    "edges": [{"from": "na", "to": "nb"}],
}
MAP_NOEDGE = {**MAP2, "edges": []}


def facts_for(target, paths):
    return {
        "revision": target,

codex
**78c2751..53f3580**

Reviewed the frozen target and exact range, read-only.

**BLOCKER:** None introduced in this range.

**HIGH**

1. **Valid scalar context claims crash admission.** [ca_adapter.py:341](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/ca_adapter.py:341) passes `value` into `claim_value_text()`, which expects a claim dictionary. A relevant `team.note` claim with a string value raises `AttributeError: 'str' object has no attribute 'get'`, preventing otherwise valid proposals from returning. Reproduced with an in-memory admission probe.

2. **Changed dynamic imports become silent absence.** [relations.py:150](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:150) subtracts sets containing only API names. Changing `__import__('pkg.b')` to `__import__('pkg.c')`, or adding another call to an already present API, yields no dynamic signal. The changed dependency receives no UNKNOWN/unresolved entry, violating C-3. Reproduced with mocked pinned blobs.

3. **A contradicted pack still controls conflict admission.** [ca_adapter.py:187](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/ca_adapter.py:187) processes `conflict_rows` after independent verification declares the pack untrusted. Only T1 enrichment checks `pack_trusted`. A wrong-head claim combined with a relevant conflict still removes an independently supported proposal. Reproduced in memory; this violates invariant 11’s stop-consumption requirement.

**MEDIUM**

4. **Alias expansion fabricates submodule dependencies.** [relations.py:95](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:95) treats every from-import alias as a module candidate. If `pkg/__init__.py` defines `b = 42` and `pkg/b.py` also exists, `from pkg import b` imports the attribute, but C resolves and reports a dependency on `pkg/b.py`, potentially with medium confidence and no uncertainty. This is an introduced precision regression beyond the declared package-prefix removal limitation.

**LOW:** None separately reported.

**FALSE_GREEN_RISK**

- T1 tests cover dictionary values; relevant scalar claims are missing.
- Dynamic-import tests miss changed arguments and additional calls using the same API.
- The contradiction test covers muted T1 enrichment, but omits conflicting rows.
- Alias recall positives lack attribute-shadowing negatives.
- Real B/CA tests can skip when external implementations are absent and load mutable external worktrees.
- The real-history “map hash” test hashes implementation files, so that particular assertion does not verify formal-map preservation.

**CONTRACT_REGRESSIONS**

C-3, invariant 11, and relation precision regress as described above. No introduced skipped-evidence leak, proposal-evidence poison attachment, duplicated B declaration parsing, formal-map write path, position proposal, or automatic acceptance was found. X13’s diagnostic change follows F06; the W4 base-revision correction and added mutation tests strengthen coverage. No unjustified oracle weakening was found.

**SECURITY_FINDINGS**

No introduced credential exposure or filesystem-write path found. Untrusted context can nevertheless trigger the admission crash or continue suppressing proposals after contradiction.

Verification: static review, read-only in-memory probes, and `git diff --check`. The reported 121-test run and mutation results were not independently rerun. A30 remains outside this range’s runtime.

**VERDICT: FAIL**
tokens used
69,743
**78c2751..53f3580**

Reviewed the frozen target and exact range, read-only.

**BLOCKER:** None introduced in this range.

**HIGH**

1. **Valid scalar context claims crash admission.** [ca_adapter.py:341](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/ca_adapter.py:341) passes `value` into `claim_value_text()`, which expects a claim dictionary. A relevant `team.note` claim with a string value raises `AttributeError: 'str' object has no attribute 'get'`, preventing otherwise valid proposals from returning. Reproduced with an in-memory admission probe.

2. **Changed dynamic imports become silent absence.** [relations.py:150](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:150) subtracts sets containing only API names. Changing `__import__('pkg.b')` to `__import__('pkg.c')`, or adding another call to an already present API, yields no dynamic signal. The changed dependency receives no UNKNOWN/unresolved entry, violating C-3. Reproduced with mocked pinned blobs.

3. **A contradicted pack still controls conflict admission.** [ca_adapter.py:187](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/ca_adapter.py:187) processes `conflict_rows` after independent verification declares the pack untrusted. Only T1 enrichment checks `pack_trusted`. A wrong-head claim combined with a relevant conflict still removes an independently supported proposal. Reproduced in memory; this violates invariant 11’s stop-consumption requirement.

**MEDIUM**

4. **Alias expansion fabricates submodule dependencies.** [relations.py:95](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:95) treats every from-import alias as a module candidate. If `pkg/__init__.py` defines `b = 42` and `pkg/b.py` also exists, `from pkg import b` imports the attribute, but C resolves and reports a dependency on `pkg/b.py`, potentially with medium confidence and no uncertainty. This is an introduced precision regression beyond the declared package-prefix removal limitation.

**LOW:** None separately reported.

**FALSE_GREEN_RISK**

- T1 tests cover dictionary values; relevant scalar claims are missing.
- Dynamic-import tests miss changed arguments and additional calls using the same API.
- The contradiction test covers muted T1 enrichment, but omits conflicting rows.
- Alias recall positives lack attribute-shadowing negatives.
- Real B/CA tests can skip when external implementations are absent and load mutable external worktrees.
- The real-history “map hash” test hashes implementation files, so that particular assertion does not verify formal-map preservation.

**CONTRACT_REGRESSIONS**

C-3, invariant 11, and relation precision regress as described above. No introduced skipped-evidence leak, proposal-evidence poison attachment, duplicated B declaration parsing, formal-map write path, position proposal, or automatic acceptance was found. X13’s diagnostic change follows F06; the W4 base-revision correction and added mutation tests strengthen coverage. No unjustified oracle weakening was found.

**SECURITY_FINDINGS**

No introduced credential exposure or filesystem-write path found. Untrusted context can nevertheless trigger the admission crash or continue suppressing proposals after contradiction.

Verification: static review, read-only in-memory probes, and `git diff --check`. The reported 121-test run and mutation results were not independently rerun. A30 remains outside this range’s runtime.

**VERDICT: FAIL**
