Reading additional input from stdin...
2026-10-04T17:34:22.992909Z ERROR codex_models_manager::manager: failed to refresh available models: request timed out
2026-10-04T17:34:22.994227Z ERROR codex_models_manager::manager: failed to refresh available models: request timed out
OpenAI Codex v0.160.0
--------
workdir: G:\jiagou\projectmind-c-convergence
model: gpt-6.1-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: medium
reasoning summaries: none
session id: 01a107fb-1587-7b53-aedd-940dec021d8f
--------
user
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

Verify each fix in the actual code at dda5246 (git show dda5246:... or the working tree). Re-check specifically: (a) no new C-3 / invariant-11 violation was introduced by the fixes themselves; (b) the from-alias downgrade does not break legitimate prefix-derived RELATION_ADD positives; (c) the dynamic-tag change does not turn repeated identical dynamic calls into duplicate unresolved noise. Output findings in the requested format.
warning: Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.
  user (C:\Users\李则兴\.codex\config.toml): `features.rmcp_client` is ignored.
warning: Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.
  user (C:\Users\李则兴\.codex\config.toml): `features.rmcp_client` is ignored.
2026-10-04T17:34:25.199844Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
ERROR: Reconnecting... 2/5
ERROR: Reconnecting... 3/5
ERROR: Reconnecting... 4/5
ERROR: Reconnecting... 5/5
warning: Falling back from WebSockets to HTTPS transport. request timed out
codex
我会按增量范围只核验这轮修复及回归保护，先读取审查规范，再检查 dda5246 的代码与测试，重点核对你列出的三个额外约束。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content README.md; Get-Content docs/standards/AGENT_STANDARD.md; Get-Content docs/standards/TEAM_SOP.md; Get-Content C:/Users/李则兴/.codex/skills/code-review/SKILL.md' in G:\jiagou\projectmind-c-convergence
 succeeded in 418ms:
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

codex
我会使用 code-review 技能，并行核对规范与修复要求；最终报告沿用你指定的格式，范围固定为 53f3580..dda5246。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse HEAD 53f3580 dda5246; git log --oneline 53f3580..dda5246; git diff --stat 53f3580 dda5246; git diff 53f3580 dda5246; Get-Content -Encoding utf8 docs/standards/COLLABORATION_CONTRACT.md; Get-Content -Encoding utf8 docs/standards/MVP_INTERFACES.md' in G:\jiagou\projectmind-c-convergence
 succeeded in 487ms:
 M extensions/map_proposal/analysis.py
 M extensions/map_proposal/engine.py
 M tests/test_p06_matrix_closure.py
dda524607562e11eb07fc201bf1f52ee3ad48763
53f3580bf2af1738bd0b8d6e443e83ff1d57736c
dda524607562e11eb07fc201bf1f52ee3ad48763
dda5246 convergence: fix Codex round-1 findings (3 HIGH + 1 MEDIUM) with regression guards
c0a8958 convergence: P06 matrix closure — S08/S12/S17/S18/S27 variants, subdirectory rename, seam error boundary
 extensions/map_proposal/ca_adapter.py |  12 +-
 extensions/map_proposal/relations.py  |  65 ++++++--
 tests/test_p06_matrix_closure.py      | 284 ++++++++++++++++++++++++++++++++++
 tests/test_real_b_integration.py      |   5 +-
 tests/test_real_ca_integration.py     |  14 ++
 tests/test_w3_relations.py            |  20 +++
 6 files changed, 378 insertions(+), 22 deletions(-)
diff --git a/extensions/map_proposal/ca_adapter.py b/extensions/map_proposal/ca_adapter.py
index 9da1857..0abe085 100644
--- a/extensions/map_proposal/ca_adapter.py
+++ b/extensions/map_proposal/ca_adapter.py
@@ -182,9 +182,14 @@ def apply_context_admission(proposals, ca, ca_mode, changed_paths, node_ids,
     claims_for_context = _independent_verification(
         ca, target_revision, limits, unresolved)
     pack_trusted = claims_for_context is not None
+    if not pack_trusted:
+        # Invariant 11: a pack contradicted by independent observation is no
+        # longer trusted — its conflict rows stop suppressing proposals too;
+        # the contradiction itself is already routed to human review.
+        limits.append("context pack contradicted; conflict rows not consumed")
 
     kept = list(proposals)
-    for row in ca["conflict_rows"]:
+    for row in (ca["conflict_rows"] if pack_trusted else []):
         if not isinstance(row, dict):
             continue
         row_text = " ".join(
@@ -333,12 +338,13 @@ def _proposal_tokens(proposal):
 
 def _context_line(claim_row, project_revision):
     """Labeled T1/T2 context line: provenance always shown, never evidence."""
-    value = claim_row.get("value")
     verification = field_verification(claim_row)
     if verification:
         detail = "fields [" + "; ".join(f"{k}={v}" for k, v in sorted(verification.items())) + "]"
     else:
-        detail = claim_value_text(value)[:80]
+        # claim_value_text takes the CLAIM row and renders claim["value"]
+        # safely for scalar and dict values alike (Codex HIGH-1).
+        detail = claim_value_text(claim_row)[:80]
     freshness = claim_row.get("freshness", "unverified")
     return (f"CA 上下文[{freshness}] {claim_row.get('key')}@{claim_row.get('scope')}：{detail}"
             f"（人工参考，非事实证据；claim {claim_row.get('claim_id')}，"
diff --git a/extensions/map_proposal/relations.py b/extensions/map_proposal/relations.py
index 0c0b493..3b3556d 100644
--- a/extensions/map_proposal/relations.py
+++ b/extensions/map_proposal/relations.py
@@ -72,14 +72,19 @@ def _parse_blob(repo, revision, source_path):
 
 
 def _scan_imports(tree):
-    """(static module strings, dynamic import tags) from one parsed module.
+    """(static module strings, dynamic import tags, from-alias-derived
+    candidates) from one parsed module.
 
     ImportFrom contributes its package prefix AND each prefix-qualified alias
     so `from pkg import b` (b a submodule) and `from . import b` carry the
     submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
-    Aliased and parenthesized/multiline forms are AST-native. Docstrings,
-    comments and string literals never appear here."""
-    static, dynamic = set(), set()
+    Alias-derived candidates are reported separately (Codex MEDIUM-4):
+    `from pkg import b` may bind an attribute defined in pkg/__init__ rather
+    than the submodule pkg/b.py, and C cannot parse declarations to know
+    (O-1) — such relations must stay explicitly uncertain. Aliased and
+    parenthesized/multiline forms are AST-native. Docstrings, comments and
+    string literals never appear here."""
+    static, dynamic, from_aliases = set(), set(), set()
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
@@ -91,23 +96,35 @@ def _scan_imports(tree):
             for alias in node.names:
                 if not prefix:
                     static.add(alias.name)
-                elif prefix.endswith("."):
-                    static.add(prefix + alias.name)
-                else:
-                    static.add(f"{prefix}.{alias.name}")
+                    continue
+                candidate = prefix + alias.name if prefix.endswith(".") \
+                    else f"{prefix}.{alias.name}"
+                static.add(candidate)
+                from_aliases.add(candidate)
         elif isinstance(node, ast.Call):
             func = node.func
             if isinstance(func, ast.Name) and func.id == "__import__":
-                dynamic.add("__import__")
+                dynamic.add(_dynamic_tag(node, "__import__"))
             elif isinstance(func, ast.Attribute) and func.attr == "import_module":
-                dynamic.add("importlib.import_module")
-    return static, dynamic
+                dynamic.add(_dynamic_tag(node, "importlib.import_module"))
+    return static, dynamic, from_aliases
+
+
+def _dynamic_tag(call_node, api):
+    """Dynamic import tag includes the string target when statically visible
+    (Codex HIGH-2: only diffing API names made `__import__('pkg.b')` →
+    `__import__('pkg.c')` a silent absence, violating C-3)."""
+    if call_node.args:
+        arg = call_node.args[0]
+        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
+            return f"{api}:{arg.value}"
+    return api
 
 
 def imported_paths(repo, revision, source_path):
     """Dotted module strings actually imported by source_path@revision (AST).
     Raises DiffSignalError on read/parse failure."""
-    static, _ = _scan_imports(_parse_blob(repo, revision, source_path))
+    static, _, _ = _scan_imports(_parse_blob(repo, revision, source_path))
     return static
 
 
@@ -137,15 +154,24 @@ def _file_relation_events(repo, base, target, change, known_paths):
         base_dynamic = _scan_imports(_parse_blob(repo, base, base_ref))[1]
     else:
         base_resolved, base_dynamic = {}, set()
-    target_static, target_dynamic = _scan_imports(_parse_blob(repo, target, path))
+    target_static, target_dynamic, target_from_aliases = _scan_imports(
+        _parse_blob(repo, target, path))
     target_resolved = {}
     for module in sorted(target_static):
         resolved = resolve_module(module, path, known_paths)
         if resolved:
             target_resolved.setdefault(resolved, []).append(module)
+    added = {p: mods for p, mods in target_resolved.items() if p not in base_resolved}
     return {
         "path": path,
-        "added": {p: mods for p, mods in target_resolved.items() if p not in base_resolved},
+        "added": added,
+        # Codex MEDIUM-4: a resolved target reached ONLY through from-import
+        # alias expansion may actually be a package-__init__ attribute — the
+        # proposal must carry that ambiguity, never medium confidence.
+        "added_from_derived": {
+            p: all(m in target_from_aliases for m in mods)
+            for p, mods in added.items()
+        },
         "removed": {p: mods for p, mods in base_resolved.items() if p not in target_resolved},
         "dynamic": sorted(target_dynamic - base_dynamic),
     }
@@ -184,11 +210,16 @@ def handle_relations(repo, base, target, indexes, facts, known_paths, relation_c
                 continue
             emitted_pairs.add(pair)
             modules = "、".join(sorted(event["added"][target_path]))
-            uncertainty, confidence = [], "low"
-            if len(source_owners) > 1 or len(target_owners) > 1:
+            uncertainty = []
+            multi_owner = len(source_owners) > 1 or len(target_owners) > 1
+            if multi_owner:
                 uncertainty.append("multiple candidate nodes on this import edge")
+            if event["added_from_derived"].get(target_path):
+                uncertainty.append(
+                    "from-import 目标可能是包 __init__ 中的同名属性而非子模块，需人工确认")
+                confidence = "low"
             else:
-                confidence = "medium"
+                confidence = "low" if multi_owner else "medium"
             proposals.append(
                 {
                     "kind": "RELATION_ADD",
diff --git a/tests/test_p06_matrix_closure.py b/tests/test_p06_matrix_closure.py
new file mode 100644
index 0000000..6e25161
--- /dev/null
+++ b/tests/test_p06_matrix_closure.py
@@ -0,0 +1,284 @@
+# -*- coding: utf-8 -*-
+"""P06 matrix closure: PARTIAL S-matrix variants (S08/S12/S17/S18/S27),
+subdirectory rename, and the extension-seam error boundary (400/500,
+malicious map text, no silent worktree fallback).
+
+Oracles from C_CONVERGENCE_PLAN §8 and C_SELF_AUDIT remaining-PARTIAL list.
+"""
+import json
+import sys
+import tempfile
+import unittest
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parents[1]
+sys.path.insert(0, str(ROOT))
+
+from extensions.map_proposal import engine, model  # noqa: E402
+
+
+def git(cwd, *args):
+    out = subprocess_run(["git", "-C", str(cwd), *args])
+    return out.strip()
+
+
+def subprocess_run(args):
+    import subprocess
+    out = subprocess.run(args, check=True, capture_output=True, text=True)
+    return out.stdout.strip()
+
+
+def build_repo(base_files, target_files):
+    tmp = tempfile.TemporaryDirectory()
+    repo = Path(tmp.name)
+    git(repo, "init")
+    git(repo, "config", "user.email", "t@example.com")
+    git(repo, "config", "user.name", "t")
+    for path, content in base_files.items():
+        (repo / path).parent.mkdir(parents=True, exist_ok=True)
+        (repo / path).write_text(content, encoding="utf-8")
+    git(repo, "add", "-A")
+    git(repo, "commit", "-m", "base")
+    base = git(repo, "rev-parse", "HEAD")
+    for path, content in target_files.items():
+        (repo / path).parent.mkdir(parents=True, exist_ok=True)
+        (repo / path).write_text(content, encoding="utf-8")
+    git(repo, "add", "-A")
+    git(repo, "commit", "-m", "target")
+    target = git(repo, "rev-parse", "HEAD")
+    return repo, base, target, tmp
+
+
+def node(node_id, paths, entry=None):
+    return {
+        "id": node_id,
+        "title": f"T-{node_id}",
+        "summary": "s",
+        "entryPoint": entry or f"{paths[0]} · main()",
+        "evidence": [{"path": p, "reason": "r"} for p in paths],
+    }
+
+
+def run_engine(repo, base, target, changed, map_data, facts_files, skipped=None):
+    request = {
+        "base_revision": base,
+        "target_revision": target,
+        "changed_paths": changed,
+        "code_facts": {"revision": target, "files": facts_files,
+                       "skipped": skipped or []},
+        "current_map": map_data,
+        "prior_decisions": [],
+    }
+    return engine.suggest_map(repo, request)
+
+
+def two_node_map(extra_na=()):
+    return {
+        "note": "m",
+        "nodes": [node("na", ["pkg/a.py", *extra_na]), node("nb", ["pkg/b.py"])],
+        "edges": [{"from": "na", "to": "nb"}],
+    }
+
+
+A = "class A:\n    pass\n"
+B = "class B:\n    pass\n"
+
+
+class S08FormattingOnly(unittest.TestCase):
+    def test_s08_line_and_quote_drift_only_zero_proposals(self):
+        # Line-number and quote-style drift, declarations byte-identical:
+        # zero proposals with an explicit no-cross-signal reason (A08).
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": 'x = "one"\n' + A, "pkg/b.py": B},
+            {"pkg/a.py": "x = 'one'\n\n\n" + A, "pkg/b.py": B},
+        )
+        self.addCleanup(tmp.cleanup)
+        res = run_engine(repo, base, target,
+                         [{"path": "pkg/a.py", "status": "modified"}],
+                         two_node_map(),
+                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
+                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
+        self.assertEqual(res["proposals"], [])
+        self.assertTrue(any(n.get("reason") for n in res["no_proposal"]))
+
+
+class S12TestNoise(unittest.TestCase):
+    def test_s12_test_and_generated_noise_no_business_candidates(self):
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": A, "pkg/b.py": B, "tests/test_a.py": "def test_old():\n    pass\n"},
+            {"pkg/a.py": A, "pkg/b.py": B,
+             "tests/test_a.py": "def test_new():\n    pass\n",
+             "docs/generated/schema.py": "GEN = 1\n"},
+        )
+        self.addCleanup(tmp.cleanup)
+        res = run_engine(repo, base, target,
+                         [{"path": "tests/test_a.py", "status": "modified"},
+                          {"path": "docs/generated/schema.py", "status": "added"}],
+                         two_node_map(),
+                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
+                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]},
+                          {"path": "tests/test_a.py", "entries": [{"name": "test_new", "kind": "function", "line": 1}]},
+                          {"path": "docs/generated/schema.py", "entries": [{"name": "GEN", "kind": "function", "line": 1}]}])
+        self.assertEqual(res["proposals"], [])
+
+
+class S17MultiOwnerAmbiguity(unittest.TestCase):
+    def test_s17_multi_owner_relation_ends_low_confidence_not_arbitrary(self):
+        # A17 beyond rename: an endpoint path covered by TWO map nodes →
+        # low-confidence candidate with the ambiguity uncertainty, never an
+        # arbitrary single-owner pick.
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": A, "pkg/a2.py": A, "pkg/b.py": B, "pkg/b2.py": B},
+            {"pkg/a.py": A + "from pkg.b import B\n", "pkg/a2.py": A,
+             "pkg/b.py": B, "pkg/b2.py": B},
+        )
+        self.addCleanup(tmp.cleanup)
+        map_data = {
+            "note": "m",
+            "nodes": [node("na", ["pkg/a.py"]),
+                      node("na2", ["pkg/a.py", "pkg/a2.py"]),
+                      node("nb", ["pkg/b.py"]),
+                      node("nb2", ["pkg/b.py", "pkg/b2.py"])],
+            "edges": [],
+        }
+        res = run_engine(repo, base, target,
+                         [{"path": "pkg/a.py", "status": "modified"}],
+                         map_data,
+                         [{"path": p, "entries": [{"name": "X", "kind": "class", "line": 1}]}
+                          for p in ("pkg/a.py", "pkg/a2.py", "pkg/b.py", "pkg/b2.py")])
+        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
+        self.assertEqual(len(adds), 1)
+        self.assertEqual(adds[0]["confidence"], "low")
+        self.assertTrue(any("multiple candidate nodes" in u
+                            for u in adds[0]["uncertainty"]))
+
+
+class S18MissingEvidence(unittest.TestCase):
+    def test_s18_added_file_without_b_entries_unresolved_unknown(self):
+        # Added file, but B returns no declaration entries: unresolved UNKNOWN,
+        # zero strong candidates — "B 无条目 ≠ 架构上不存在" (A18/C-3).
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": A, "pkg/b.py": B},
+            {"pkg/a.py": A, "pkg/b.py": B, "pkg/ghost.py": "class G:\n    pass\n"},
+        )
+        self.addCleanup(tmp.cleanup)
+        res = run_engine(repo, base, target,
+                         [{"path": "pkg/ghost.py", "status": "added"}],
+                         two_node_map(),
+                         # B facts deliberately omit pkg/ghost.py entries
+                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
+                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
+        self.assertEqual(res["proposals"], [])
+        self.assertTrue(any(u["subject"] == "pkg/ghost.py" for u in res["unresolved"]))
+
+
+class S04SubdirectoryRename(unittest.TestCase):
+    def test_s04_subdirectory_move_link_change(self):
+        repo, base, target, tmp = build_repo(
+            {"pkg/sub/a.py": A, "pkg/b.py": B},
+            {"pkg/sub2/a.py": A, "pkg/b.py": B},
+        )
+        self.addCleanup(tmp.cleanup)
+        map_data = {
+            "note": "m",
+            "nodes": [node("na", ["pkg/sub/a.py"]), node("nb", ["pkg/b.py"])],
+            "edges": [],
+        }
+        res = run_engine(repo, base, target,
+                         [{"path": "pkg/sub2/a.py", "status": "renamed",
+                           "old_path": "pkg/sub/a.py"}],
+                         map_data,
+                         [{"path": "pkg/sub2/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
+                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
+        links = [p for p in res["proposals"] if p["kind"] == "IMPLEMENTATION_LINK_CHANGE"]
+        self.assertEqual(len(links), 1)
+        # R06 identity: link-change subjects carry the old repo path and the
+        # affected map node id in proposed_change.
+        self.assertEqual(links[0]["subject"], "pkg/sub/a.py")
+        self.assertEqual(links[0]["proposed_change"]["node_id"], "na")
+        self.assertEqual(
+            [p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])
+
+
+class S27MalformedWithContext(unittest.TestCase):
+    def test_s27_malformed_map_evidence_inside_valid_context_rejected(self):
+        # valid-context malformed_payload_map: a structurally invalid node
+        # (evidence item without path) inside an otherwise valid request is a
+        # controlled rejection (A27). Note: whether Core's map schema REQUIRES
+        # title/summary/entryPoint per node is NOT defined by the contract —
+        # recorded as HUMAN_DECISION_REQUIRED_MAP_NODE_FIELDS (P07), not
+        # invented here.
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": A, "pkg/b.py": B},
+            {"pkg/a.py": A + "# t\n", "pkg/b.py": B},
+        )
+        self.addCleanup(tmp.cleanup)
+        map_data = two_node_map()
+        map_data["nodes"].append(
+            {"id": "bad", "title": "t", "summary": "s",
+             "entryPoint": "pkg/a.py · f()", "position": {"x": 1, "y": 2},
+             "evidence": [{"reason": "no path key"}]})
+        with self.assertRaises(model.RequestError):
+            run_engine(repo, base, target,
+                       [{"path": "pkg/a.py", "status": "modified"}],
+                       map_data,
+                       [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}])
+
+
+class ExtensionSeamBoundary(unittest.TestCase):
+    """Handler-level error mapping and hostile map text (A27/A28 at the seam)."""
+
+    def setUp(self):
+        from extensions.map_proposal import extension
+        self.extension = extension
+
+    def _ctx(self, repo):
+        class Ctx:
+            pass
+        ctx = Ctx()
+        ctx.repo = str(repo)
+        return ctx
+
+    def _repo_with_commit(self):
+        # target differs from base (comment line) so the second commit is real
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": A}, {"pkg/a.py": A + "# touched\n"})
+        self.addCleanup(tmp.cleanup)
+        return repo, base, target
+
+    def test_malicious_map_text_controlled_rejection_not_crash(self):
+        repo, base, target = self._repo_with_commit()
+        hostile = {
+            "note": "x" * 10000,
+            "nodes": [{"id": "../escape", "title": "t", "summary": "s",
+                       "entryPoint": "../../etc/passwd · f()",
+                       "position": {"x": 1, "y": 2},
+                       "evidence": [{"path": "../../etc/passwd", "reason": "r"}]}],
+            "edges": [],
+        }
+        data = {"base_revision": base, "target_revision": target,
+                "changed_paths": [], "code_facts": None, "current_map": hostile}
+        from extension_host import ExtensionError
+        with self.assertRaises(ExtensionError) as caught:
+            self.extension.handle(self._ctx(repo), "POST", data)
+        self.assertEqual(caught.exception.status.value, 400)
+
+    def test_missing_pin_is_400_not_head_fallback(self):
+        repo, base, target = self._repo_with_commit()
+        from extension_host import ExtensionError
+        data = {"changed_paths": [], "code_facts": None,
+                "current_map": {"note": "n", "nodes": [], "edges": []}}
+        with self.assertRaises(ExtensionError) as caught:
+            self.extension.handle(self._ctx(repo), "POST", data)
+        self.assertEqual(caught.exception.status.value, 400)
+
+    def test_get_method_allowed_post_only_others_rejected(self):
+        repo, base, target = self._repo_with_commit()
+        from extension_host import ExtensionError
+        with self.assertRaises(ExtensionError) as caught:
+            self.extension.handle(self._ctx(repo), "DELETE", {})
+        self.assertEqual(caught.exception.status.value, 405)
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/tests/test_real_b_integration.py b/tests/test_real_b_integration.py
index 315d30a..dd9e99f 100644
--- a/tests/test_real_b_integration.py
+++ b/tests/test_real_b_integration.py
@@ -303,8 +303,9 @@ class RealBIntegrationTests(unittest.TestCase):
             "current_map": real_map,
             "prior_decisions": [],
         }
-        map_files = [ROOT / "extensions" / "map_proposal" / name
-                     for name in ("model.py", "engine.py")]
+        # Hash the FORMAL map file (Codex false-green fix: hashing
+        # implementation files did not verify formal-map preservation).
+        map_files = [ROOT / "data" / "project-map.json"]
         before = {p: p.read_bytes() for p in map_files}
         first = engine.suggest_map(repo, request)
         second = engine.suggest_map(repo, request)
diff --git a/tests/test_real_ca_integration.py b/tests/test_real_ca_integration.py
index 536a5f3..14de46c 100644
--- a/tests/test_real_ca_integration.py
+++ b/tests/test_real_ca_integration.py
@@ -317,6 +317,10 @@ class RealCAIntegrationTests(unittest.TestCase):
             # Relevant low-impact claim (mentions the touched path) → T1 line.
             claim("claim-t1-relevant", "architecture.pkg_new.note", "HUMAN_DECISION",
                   "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
+            # Scalar-value claim (Codex HIGH-1 regression guard: a string
+            # value once crashed admission with AttributeError).
+            claim("claim-t1-scalar", "team.focus.overnight", "HUMAN_DECISION",
+                  "path:pkg/new.py", "owner plans a rename here", target),
             # Irrelevant claim (mentions nothing touched) → no annotation.
             claim("claim-t1-irrelevant", "architecture.pkg_zzz.note", "HUMAN_DECISION",
                   "global", {"note": "unrelated module note"}, target),
@@ -342,6 +346,8 @@ class RealCAIntegrationTests(unittest.TestCase):
         self.assertIn("architecture.pkg_new.note", uncertainty)
         self.assertIn("人工参考，非事实证据", uncertainty)
         self.assertNotIn("claim-t1-irrelevant", uncertainty)
+        self.assertIn("owner plans a rename here", uncertainty)  # scalar value rendered
+        self.assertNotIn("AttributeError", uncertainty)
         # Context never contaminates evidence or rationale (S-2/E-4).
         self.assertNotIn("context_claim",
                          {e["kind"] for p in res["proposals"] for e in p["evidence"]})
@@ -362,6 +368,12 @@ class RealCAIntegrationTests(unittest.TestCase):
             # Would be T1-eligible if the pack were trusted — it must NOT be.
             claim("claim-t1-muted", "architecture.pkg_new.note", "HUMAN_DECISION",
                   "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
+            # A relevant CONFLICT row in the contradicted pack must also stop
+            # suppressing proposals (Codex HIGH-3: invariant 11 stop-consumption).
+            claim("claim-conf-a", "architecture.pkg_new.role", "HUMAN_DECISION",
+                  "path:pkg/new.py", "role: router", target),
+            claim("claim-conf-b", "architecture.pkg_new.role", "HUMAN_DECISION",
+                  "path:pkg/new.py", "role: adapter", target),
         ]
         pack, real = build_real_pack(self, repo, target, claims)
         request = {
@@ -381,6 +393,8 @@ class RealCAIntegrationTests(unittest.TestCase):
         self.assertTrue(any("pack claims no longer consumed" in l for l in res["limits"]))
         self.assertTrue(any(u["subject"] == "claim:claim-head-wrong"
                             and u["reason"] == "HUMAN_REQUIRED" for u in res["unresolved"]))
+        # The contradicted pack's conflict row must NOT suppress the candidate.
+        self.assertFalse(any(u["subject"].startswith("conflict:") for u in res["unresolved"]))
         node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
         self.assertEqual(len(node_adds), 1)
         self.assertFalse(any("CA 上下文" in u for u in node_adds[0]["uncertainty"]))
diff --git a/tests/test_w3_relations.py b/tests/test_w3_relations.py
index c491bfd..ddeaae2 100644
--- a/tests/test_w3_relations.py
+++ b/tests/test_w3_relations.py
@@ -215,6 +215,21 @@ class RelationChannelTests(unittest.TestCase):
         self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                             for u in res["unresolved"]))
 
+    def test_x02_changed_dynamic_target_is_not_silent(self):
+        # Codex HIGH-2 regression guard: changing the dynamically imported
+        # target (same API, new module) must surface UNKNOWN again — API-name
+        # sets alone were silently equal, hiding the changed dependency (C-3).
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module('pkg.c')\n",
+             "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module('pkg.b')\n",
+             "pkg/b.py": B_CLASS},
+            two_node_map(),
+        )
+        self.assertEqual(res["proposals"], [])
+        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
+                            for u in res["unresolved"]))
+
     def test_parse_failure_is_unknown_not_zero(self):
         res = self.run_engine(
             {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
@@ -277,6 +292,11 @@ class RelationChannelTests(unittest.TestCase):
         self.assertEqual(len(adds), 1)
         self.assertEqual((adds[0]["proposed_change"]["from"],
                           adds[0]["proposed_change"]["to"]), ("na", "nb"))
+        # Codex MEDIUM-4: the target was reached ONLY through alias expansion
+        # and `b` could be an attribute of pkg/__init__ — the candidate must
+        # stay low-confidence with the ambiguity named, never medium.
+        self.assertEqual(adds[0]["confidence"], "low")
+        self.assertTrue(any("__init__" in u for u in adds[0]["uncertainty"]))
 
     def test_multiline_parenthesized_from_import(self):
         # Adversarial 4 (silent miss at 78c2751), valid form: parenthesized
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

2026-10-04T17:36:49.222083Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
2026-10-04T17:37:00.029726Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "C-3|invariant|不变量|动态|dynamic" docs extensions/map_proposal/ca_adapter.py tests/test_w3_relations.py; git show dda5246:extensions/map_proposal/relations.py; git show dda5246:extensions/map_proposal/ca_adapter.py; git diff 53f3580 dda5246 -- tests/test_real_b_integration.py tests/test_real_ca_integration.py tests/test_w3_relations.py' in G:\jiagou\projectmind-c-convergence
 succeeded in 199ms:
tests/test_w3_relations.py:6:text is never a relation), X02 (dynamic import → UNKNOWN unresolved), X13
tests/test_w3_relations.py:207:    def test_x02_dynamic_import_unknown_unresolved(self):
tests/test_w3_relations.py:218:    def test_x02_changed_dynamic_target_is_not_silent(self):
tests/test_w3_relations.py:219:        # Codex HIGH-2 regression guard: changing the dynamically imported
tests/test_w3_relations.py:221:        # sets alone were silently equal, hiding the changed dependency (C-3).
tests/test_w3_relations.py:317:        # limits), never as silent no-change (C-3).
extensions/map_proposal/ca_adapter.py:26:    claims stop being consumed entirely (invariant 11).
docs\standards\MVP_INTERFACES.md:5:## 共同词汇与不变量
# -*- coding: utf-8 -*-
"""Independent import-relation channel (R03, W3).

Signal AND proof are the same artifact: a per-file AST diff of the pinned
base blob against the pinned target blob. The diff patch is not parsed at
all — a regex on patch text was only ever a candidate extractor (DROP L05)
and its line-based form silently missed relative imports, from-submodule
imports and multiline imports (adversarial cases 1a/1b/3/4, 2026-10-04).
Blob read/parse failure raises DiffSignalError → UNKNOWN/unresolved, never
"zero imports" (C-3). Declaration-channel verdicts never gate this channel
(F05): "declarations unchanged" does not mean "no import signal" (X01/X11).

Resolution is a heuristic (dotted path ∩ known repo paths); modules that
resolve outside the repo (stdlib/site-packages) are not architecture
relations. Known resolution limits (namespace packages, src-layout) mean an
unresolved repo-internal import can stay invisible — recorded limit, does
not fabricate a relation.

Removal proof domain is the whole map-node evidence domain (R03): a relation
removal candidate requires an existing map edge and ALL .py files of the
source node's evidence domain free of imports into the target domain at
target, with at least one such import at base (S03, X12 multi-source).

Known edge: a rewrite between from-import shapes can add/drop the bare
package-prefix candidate (e.g. `from . import b` → `from .b import B`), so
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


def _parse_blob(repo, revision, source_path):
    """Pinned blob → AST. Raises DiffSignalError on read/parse failure
    (UNKNOWN, never silent zero)."""
    try:
        raw = gitio.read_blob(repo, revision, source_path)
        return ast.parse(raw)
    except (gitio.DiffSignalError, SyntaxError, ValueError) as exc:
        raise gitio.DiffSignalError(f"cannot verify imports of {source_path}@{revision[:8]}: "
                                    f"{type(exc).__name__}") from exc


def _scan_imports(tree):
    """(static module strings, dynamic import tags, from-alias-derived
    candidates) from one parsed module.

    ImportFrom contributes its package prefix AND each prefix-qualified alias
    so `from pkg import b` (b a submodule) and `from . import b` carry the
    submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
    Alias-derived candidates are reported separately (Codex MEDIUM-4):
    `from pkg import b` may bind an attribute defined in pkg/__init__ rather
    than the submodule pkg/b.py, and C cannot parse declarations to know
    (O-1) — such relations must stay explicitly uncertain. Aliased and
    parenthesized/multiline forms are AST-native. Docstrings, comments and
    string literals never appear here."""
    static, dynamic, from_aliases = set(), set(), set()
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
                    continue
                candidate = prefix + alias.name if prefix.endswith(".") \
                    else f"{prefix}.{alias.name}"
                static.add(candidate)
                from_aliases.add(candidate)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "__import__":
                dynamic.add(_dynamic_tag(node, "__import__"))
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                dynamic.add(_dynamic_tag(node, "importlib.import_module"))
    return static, dynamic, from_aliases


def _dynamic_tag(call_node, api):
    """Dynamic import tag includes the string target when statically visible
    (Codex HIGH-2: only diffing API names made `__import__('pkg.b')` →
    `__import__('pkg.c')` a silent absence, violating C-3)."""
    if call_node.args:
        arg = call_node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
            return f"{api}:{arg.value}"
    return api


def imported_paths(repo, revision, source_path):
    """Dotted module strings actually imported by source_path@revision (AST).
    Raises DiffSignalError on read/parse failure."""
    static, _, _ = _scan_imports(_parse_blob(repo, revision, source_path))
    return static


def _resolved_imports(repo, revision, source_path, known_paths):
    """resolved repo path → module strings that reach it. Modules resolving
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
    target_static, target_dynamic, target_from_aliases = _scan_imports(
        _parse_blob(repo, target, path))
    target_resolved = {}
    for module in sorted(target_static):
        resolved = resolve_module(module, path, known_paths)
        if resolved:
            target_resolved.setdefault(resolved, []).append(module)
    added = {p: mods for p, mods in target_resolved.items() if p not in base_resolved}
    return {
        "path": path,
        "added": added,
        # Codex MEDIUM-4: a resolved target reached ONLY through from-import
        # alias expansion may actually be a package-__init__ attribute — the
        # proposal must carry that ambiguity, never medium confidence.
        "added_from_derived": {
            p: all(m in target_from_aliases for m in mods)
            for p, mods in added.items()
        },
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
                    "note": "import 信号无法用 AST 证实（读取/解析失败），进入 UNKNOWN",
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
            modules = "、".join(sorted(event["added"][target_path]))
            uncertainty = []
            multi_owner = len(source_owners) > 1 or len(target_owners) > 1
            if multi_owner:
                uncertainty.append("multiple candidate nodes on this import edge")
            if event["added_from_derived"].get(target_path):
                uncertainty.append(
                    "from-import 目标可能是包 __init__ 中的同名属性而非子模块，需人工确认")
                confidence = "low"
            else:
                confidence = "low" if multi_owner else "medium"
            proposals.append(
                {
                    "kind": "RELATION_ADD",
                    "subject": f"{source_owners[0]}->{target_owners[0]}",
                    "node_ids": None,
                    "proposed_change": {
                        "from": source_owners[0],
                        "to": target_owners[0],
                        "label": f"import 依赖(候选): {source_path} -> {target_path}",
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
            modules = "、".join(sorted(event["removed"][target_path]))
            proposals.append(
                {
                    "kind": "RELATION_REMOVE_CANDIDATE",
                    "subject": f"{source_owners[0]}->{target_owners[0]}",
                    "node_ids": None,
                    "proposed_change": {
                        "from": source_owners[0],
                        "to": target_owners[0],
                        "label": f"import 移除(候选): {source_path} -> {target_path}",
                    },
                    "rationale": "源节点证据域内全部 .py 文件对目标域的静态 import 已消失（AST 证实）；"
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
                    "note": "动态/字符串构造 import：依赖信号不足，不足以建立关系候选",
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
    """Does any AST import of source_path@revision resolve to target_path?
    Relative candidates keep their leading dots so resolve_module anchors
    them to the source package."""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        if resolve_module(candidate, source_path, known_paths) == target_path:
            return True
    return False
# -*- coding: utf-8 -*-
"""Context Authority consumption for C (P01 port + R04 admission, W4+P05B).

Protocol:
- PIN: C validates with its own expected_revision (= target_revision).
- VALIDATE: the real CA validator runs first; any failure discards the whole
  pack (no partial use) and C degrades explicitly — independent diff/B/map
  candidates continue (S24).
- SELECT: only current_state.current_by_scope is read; stale/proposal/
  research/history partitions are never consumed (S20); conflict and
  verification-unavailable keys never become evidence (S23).
- EVIDENCE: no claim is ever attached to proposal evidence automatically
  (DROP L01/L02 — no keyword trust heuristics, no first-survivor supplement).
  Typed consumption is the only channel (P05B):
  - T1 context enrichment: a relevant LOW-IMPACT claim (team.*/architecture.*)
    whose key/scope/value mentions a touched path or node adds a labeled
    context line to the proposal's uncertainty — provenance always shown
    (freshness, claim id, pack revision); never enters evidence/rationale.
  - T2 field support: for dict values the per-field verification map is shown
    (field=verified / field=UNVERIFIED, S22); unverified fields are labelled
    and support nothing.
  - T3 independent verification: implementation.* head claims are checked
    against C's own pinned target. Confirmed → the pin speaks for itself;
    unverifiable locally (semantic status, no pin) → UNKNOWN limit, claim not
    consumed; contradicted → claim_id + both values recorded, the pack's
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
    except Exception:  # noqa: BLE001 — CA not installed on this base
        limits.append("context authority extension unavailable; running DEGRADED_NO_CONTEXT")
        return _empty_context(), DEGRADED, limits
    try:
        validate_context_pack(pack, expected_revision=target_revision)
    except Exception as exc:  # noqa: BLE001 — any validation failure discards the whole pack
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
    """Row-level verified freshness ≠ every field verified: returns the
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
    if not pack_trusted:
        # Invariant 11: a pack contradicted by independent observation is no
        # longer trusted — its conflict rows stop suppressing proposals too;
        # the contradiction itself is already routed to human review.
        limits.append("context pack contradicted; conflict rows not consumed")

    kept = list(proposals)
    for row in (ca["conflict_rows"] if pack_trusted else []):
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
                "note": f"CA 主张与 C 的独立观察矛盾（主张 head {head}，pinned target "
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
    verification = field_verification(claim_row)
    if verification:
        detail = "fields [" + "; ".join(f"{k}={v}" for k, v in sorted(verification.items())) + "]"
    else:
        # claim_value_text takes the CLAIM row and renders claim["value"]
        # safely for scalar and dict values alike (Codex HIGH-1).
        detail = claim_value_text(claim_row)[:80]
    freshness = claim_row.get("freshness", "unverified")
    return (f"CA 上下文[{freshness}] {claim_row.get('key')}@{claim_row.get('scope')}：{detail}"
            f"（人工参考，非事实证据；claim {claim_row.get('claim_id')}，"
            f"pack {str(project_revision)[:8]}）")
diff --git a/tests/test_real_b_integration.py b/tests/test_real_b_integration.py
index 315d30a..dd9e99f 100644
--- a/tests/test_real_b_integration.py
+++ b/tests/test_real_b_integration.py
@@ -303,8 +303,9 @@ class RealBIntegrationTests(unittest.TestCase):
             "current_map": real_map,
             "prior_decisions": [],
         }
-        map_files = [ROOT / "extensions" / "map_proposal" / name
-                     for name in ("model.py", "engine.py")]
+        # Hash the FORMAL map file (Codex false-green fix: hashing
+        # implementation files did not verify formal-map preservation).
+        map_files = [ROOT / "data" / "project-map.json"]
         before = {p: p.read_bytes() for p in map_files}
         first = engine.suggest_map(repo, request)
         second = engine.suggest_map(repo, request)
diff --git a/tests/test_real_ca_integration.py b/tests/test_real_ca_integration.py
index 536a5f3..14de46c 100644
--- a/tests/test_real_ca_integration.py
+++ b/tests/test_real_ca_integration.py
@@ -317,6 +317,10 @@ class RealCAIntegrationTests(unittest.TestCase):
             # Relevant low-impact claim (mentions the touched path) → T1 line.
             claim("claim-t1-relevant", "architecture.pkg_new.note", "HUMAN_DECISION",
                   "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
+            # Scalar-value claim (Codex HIGH-1 regression guard: a string
+            # value once crashed admission with AttributeError).
+            claim("claim-t1-scalar", "team.focus.overnight", "HUMAN_DECISION",
+                  "path:pkg/new.py", "owner plans a rename here", target),
             # Irrelevant claim (mentions nothing touched) → no annotation.
             claim("claim-t1-irrelevant", "architecture.pkg_zzz.note", "HUMAN_DECISION",
                   "global", {"note": "unrelated module note"}, target),
@@ -342,6 +346,8 @@ class RealCAIntegrationTests(unittest.TestCase):
         self.assertIn("architecture.pkg_new.note", uncertainty)
         self.assertIn("人工参考，非事实证据", uncertainty)
         self.assertNotIn("claim-t1-irrelevant", uncertainty)
+        self.assertIn("owner plans a rename here", uncertainty)  # scalar value rendered
+        self.assertNotIn("AttributeError", uncertainty)
         # Context never contaminates evidence or rationale (S-2/E-4).
         self.assertNotIn("context_claim",
                          {e["kind"] for p in res["proposals"] for e in p["evidence"]})
@@ -362,6 +368,12 @@ class RealCAIntegrationTests(unittest.TestCase):
             # Would be T1-eligible if the pack were trusted — it must NOT be.
             claim("claim-t1-muted", "architecture.pkg_new.note", "HUMAN_DECISION",
                   "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
+            # A relevant CONFLICT row in the contradicted pack must also stop
+            # suppressing proposals (Codex HIGH-3: invariant 11 stop-consumption).
+            claim("claim-conf-a", "architecture.pkg_new.role", "HUMAN_DECISION",
+                  "path:pkg/new.py", "role: router", target),
+            claim("claim-conf-b", "architecture.pkg_new.role", "HUMAN_DECISION",
+                  "path:pkg/new.py", "role: adapter", target),
         ]
         pack, real = build_real_pack(self, repo, target, claims)
         request = {
@@ -381,6 +393,8 @@ class RealCAIntegrationTests(unittest.TestCase):
         self.assertTrue(any("pack claims no longer consumed" in l for l in res["limits"]))
         self.assertTrue(any(u["subject"] == "claim:claim-head-wrong"
                             and u["reason"] == "HUMAN_REQUIRED" for u in res["unresolved"]))
+        # The contradicted pack's conflict row must NOT suppress the candidate.
+        self.assertFalse(any(u["subject"].startswith("conflict:") for u in res["unresolved"]))
         node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
         self.assertEqual(len(node_adds), 1)
         self.assertFalse(any("CA 上下文" in u for u in node_adds[0]["uncertainty"]))
diff --git a/tests/test_w3_relations.py b/tests/test_w3_relations.py
index c491bfd..ddeaae2 100644
--- a/tests/test_w3_relations.py
+++ b/tests/test_w3_relations.py
@@ -215,6 +215,21 @@ class RelationChannelTests(unittest.TestCase):
         self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                             for u in res["unresolved"]))
 
+    def test_x02_changed_dynamic_target_is_not_silent(self):
+        # Codex HIGH-2 regression guard: changing the dynamically imported
+        # target (same API, new module) must surface UNKNOWN again — API-name
+        # sets alone were silently equal, hiding the changed dependency (C-3).
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module('pkg.c')\n",
+             "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module('pkg.b')\n",
+             "pkg/b.py": B_CLASS},
+            two_node_map(),
+        )
+        self.assertEqual(res["proposals"], [])
+        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
+                            for u in res["unresolved"]))
+
     def test_parse_failure_is_unknown_not_zero(self):
         res = self.run_engine(
             {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
@@ -277,6 +292,11 @@ class RelationChannelTests(unittest.TestCase):
         self.assertEqual(len(adds), 1)
         self.assertEqual((adds[0]["proposed_change"]["from"],
                           adds[0]["proposed_change"]["to"]), ("na", "nb"))
+        # Codex MEDIUM-4: the target was reached ONLY through alias expansion
+        # and `b` could be an attribute of pkg/__init__ — the candidate must
+        # stay low-confidence with the ambiguity named, never medium.
+        self.assertEqual(adds[0]["confidence"], "low")
+        self.assertTrue(any("__init__" in u for u in adds[0]["uncertainty"]))
 
     def test_multiline_parenthesized_from_import(self):
         # Adversarial 4 (silent miss at 78c2751), valid form: parenthesized

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --files -g '*CONVERGENCE*' -g '*AUDIT*' -g '*mutation*' -g '*PLAN*'; git show dda5246:tests/test_w3_relations.py; git show dda5246:tests/test_real_b_integration.py | Select-Object -First 100; git show dda5246:tests/test_real_ca_integration.py | Select-Object -First 110; git show dda5246:extensions/map_proposal/engine.py | Select-Object -Last 200" in G:\jiagou\projectmind-c-convergence
 succeeded in 477ms:
extensions\map_proposal\convergence\COMMON_BASE_PLAN.md
# -*- coding: utf-8 -*-
"""W3 convergence contract tests: the independent import-relation channel.

Oracles: S02 (real RELATION_ADD incl. X01 unchanged-declarations), S03
(relation removal + multi-source remaining import), S11 (docstring import
text is never a relation), X02 (dynamic import → UNKNOWN unresolved), X13
(churn), F04 (skipped source never feeds relations). Blobs are read from a
real temporary git repository so AST proofs run against actual pinned content.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine  # noqa: E402


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def rev_of(cwd):
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def write_tree(repo, files):
    for path, content in files.items():
        target = repo / path
        if content is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build_repo(base_files, target_files):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(repo, "init")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    write_tree(repo, base_files)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = rev_of(repo)
    write_tree(repo, target_files)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = rev_of(repo)
    return repo, base, target, tmp


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def two_node_map(edges=(("na", "nb"),), extra_na_paths=()):
    na_paths = ["pkg/a.py", *extra_na_paths]
    return {
        "note": "m",
        "nodes": [node("na", na_paths), node("nb", ["pkg/b.py"])],
        "edges": [{"from": f, "to": t} for f, t in edges],
    }


def facts_for(target, paths):
    return {
        "revision": target,
        "files": [{"path": p, "entries": [{"name": "X", "kind": "class", "line": 1}]} for p in paths],
        "skipped": [],
    }


def make_request(base, target, map_data, facts=None, skipped=None):
    facts = facts or facts_for(target, ["pkg/a.py", "pkg/b.py"])
    if skipped:
        facts = dict(facts)
        facts["skipped"] = list(skipped)
    return {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
        "code_facts": facts,
        "current_map": map_data,
        "prior_decisions": [],
    }


def with_installed_b(entries_by_path):
    """Mock installed B: base-revision declaration facts for the comparison."""
    from unittest import mock

    def collect(repo, revision, wanted):
        return {
            "revision": revision,
            "files": [{"path": p, "entries": e} for p, e in entries_by_path.items()],
            "skipped": [],
        }

    fake = mock.Mock()
    fake.collect_code_facts = mock.Mock(side_effect=collect)
    return mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake})


A_CLASS = "class A:\n    pass\n"
B_CLASS = "class B:\n    pass\n"


class RelationChannelTests(unittest.TestCase):
    def run_engine(self, base_files, target_files, map_data, facts=None, skipped=None,
                   base_entries=None):
        repo, base, target, tmp = build_repo(base_files, target_files)
        self.addCleanup(tmp.cleanup)
        request = make_request(base, target, map_data, facts=facts, skipped=skipped)
        if base_entries is None:
            return engine.suggest_map(repo, request)
        with with_installed_b(base_entries):
            return engine.suggest_map(repo, request)

    def test_s02_x01_real_import_add_with_unchanged_declarations(self):
        # supplied target facts declare X; the installed-B mock returns the
        # same declarations at base so the declaration channel sees no change
        same = [{"name": "X", "kind": "class", "line": 1}]
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
            base_entries={"pkg/a.py": same, "pkg/b.py": same},
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0]["proposed_change"]["from"], "na")
        self.assertEqual(adds[0]["proposed_change"]["to"], "nb")
        self.assertEqual(adds[0]["confidence"], "medium")
        # declaration channel independently found no declaration change, yet
        # the import channel still fired (F05 independence)
        self.assertTrue(any("no declaration-level change" in n["reason"]
                            for n in res["no_proposal"]))
        self.assertEqual(len(res["proposals"]), 1)

    def test_s11_x03_docstring_import_text_never_a_relation(self):
        docstring = '"""Usage:\nimport pkg.b\n"""\n'
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": docstring + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertEqual(res["proposals"], [])

    def test_s03_x11_last_import_removed_gives_removal_candidate(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        removals = [p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"]
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0]["proposed_change"]["from"], "na")
        self.assertEqual(removals[0]["proposed_change"]["to"], "nb")

    def test_s03_multi_source_remaining_import_no_removal(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS,
             "pkg/a2.py": "from pkg.b import B\n", "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS,
             "pkg/a2.py": "from pkg.b import B\n", "pkg/b.py": B_CLASS},
            two_node_map(extra_na_paths=["pkg/a2.py"]),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"], [])

    def test_removal_requires_existing_map_edge(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(edges=()),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"], [])

    def test_x13_import_rewrite_churn_no_relation(self):
        # F06 contract: "同一规范化目标的写法变换不产生关系变化". The AST
        # channel diffs RESOLVED import-target sets, so `import os` →
        # `from os import path` (no repo-internal relation change) yields no
        # signal at all — stronger than the old signal-then-suppress churn
        # guard, whose "churn" limit diagnostic no longer exists.
        res = self.run_engine(
            {"pkg/a.py": "import os\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from os import path\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual(res["proposals"], [])
        self.assertEqual([l for l in res["limits"] if "import" in l], [])

    def test_x02_dynamic_import_unknown_unresolved(self):
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "import importlib\n\n" + A_CLASS +
             "\nimportlib.import_module('pkg.b')\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))

    def test_x02_changed_dynamic_target_is_not_silent(self):
        # Codex HIGH-2 regression guard: changing the dynamically imported
        # target (same API, new module) must surface UNKNOWN again — API-name
        # sets alone were silently equal, hiding the changed dependency (C-3).
        res = self.run_engine(
            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module('pkg.c')\n",
             "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module('pkg.b')\n",
             "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))

    def test_parse_failure_is_unknown_not_zero(self):
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\ndef broken(:\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any("import 信号无法用 AST 证实" in u["note"] or "AST" in u["note"]
                            for u in res["unresolved"]))

    def test_f04_x21_skipped_source_never_feeds_relations(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
            skipped=[{"path": "pkg/a.py", "reason": "syntax"}],
        )
        self.assertEqual(
            [p for p in res["proposals"]
             if p["kind"] in ("RELATION_ADD", "RELATION_REMOVE_CANDIDATE")], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" for u in res["unresolved"]))

    def test_adversarial_1a_relative_from_dot_import_submodule(self):
        # Adversarial 1a (silent miss at 78c2751): `from . import b` must
        # resolve .b against the source package and yield RELATION_ADD.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
            {"pkg/a.py": A_CLASS + "from . import b\n", "pkg/b.py": B_CLASS,
             "pkg/__init__.py": ""},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_adversarial_1b_relative_from_dot_module_import(self):
        # Adversarial 1b (silent miss at 78c2751): `from .b import B`.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
            {"pkg/a.py": A_CLASS + "from .b import B\n", "pkg/b.py": B_CLASS,
             "pkg/__init__.py": ""},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_adversarial_3_from_package_import_submodule(self):
        # Adversarial 3 (silent miss at 78c2751): `from pkg import b` where
        # b is the submodule pkg/b.py — alias expansion must propose pkg.b.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
            {"pkg/a.py": A_CLASS + "from pkg import b\n", "pkg/b.py": B_CLASS,
             "pkg/__init__.py": ""},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
        # Codex MEDIUM-4: the target was reached ONLY through alias expansion
        # and `b` could be an attribute of pkg/__init__ — the candidate must
        # stay low-confidence with the ambiguity named, never medium.
        self.assertEqual(adds[0]["confidence"], "low")
        self.assertTrue(any("__init__" in u for u in adds[0]["uncertainty"]))

    def test_multiline_parenthesized_from_import(self):
        # Adversarial 4 (silent miss at 78c2751), valid form: parenthesized
        # multiline from-imports are AST-native, no line-based extractor.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "from pkg.b import (\n    B,\n)\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_invalid_multiline_import_is_unknown_not_silent(self):
        # Adversarial 4 original form was a SyntaxError (`import (\n...`):
        # unsupported/invalid syntax must surface as UNKNOWN (unresolved +
        # limits), never as silent no-change (C-3).
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "import (\n    pkg.b,\n)\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))
        self.assertTrue(any("import signal extraction unavailable" in l
                            for l in res["limits"]))

    def test_s03_domain_proof_is_ast_not_text(self):
        # Mutation M4 (DROP L05 regression) showed no test bound the domain
        # removal proof to AST: a remaining source file whose only "import"
        # is docstring text must NOT retain the relation, so the removal
        # candidate for the source that truly dropped the import still fires.
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS,
             "pkg/a2.py": '"""from pkg.b import B"""\n' + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS,
             "pkg/a2.py": '"""from pkg.b import B"""\n' + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(extra_na_paths=["pkg/a2.py"]),
        )
        removals = [p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"]
        self.assertEqual(len(removals), 1)
        self.assertEqual((removals[0]["proposed_change"]["from"],
                          removals[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_relation_add_determinism(self):
        base_files = {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS}
        target_files = {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS}
        repo, base, target, tmp = build_repo(base_files, target_files)
        self.addCleanup(tmp.cleanup)
        request = make_request(base, target, two_node_map())
        first = engine.suggest_map(repo, request)
        second = engine.suggest_map(repo, request)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


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

codex
工作树有未提交修改，因此我会从 Git 对象加载 dda5246，避免把当前工作树内容混入结论。已确认标量上下文和矛盾 pack 的修复位置；接下来验证动态调用去重、关键字参数，以及别名候选与明确 import 同时出现时的置信度。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import subprocess,sys,importlib.abc,importlib.util,ast,copy
from unittest.mock import patch
from pathlib import Path
root=Path.cwd()
def blob(p):
    return subprocess.check_output(['git','show','dda5246:'+p]).decode('utf-8')
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def find_spec(self,name,path=None,target=None):
        if name=='extensions' or name=='extensions.map_proposal':
            return importlib.util.spec_from_loader(name,self,is_package=True)
        if name.startswith('extensions.map_proposal.'):
            return importlib.util.spec_from_loader(name,self)
    def create_module(self,spec): return None
    def exec_module(self,m):
        p=m.__name__.replace('.','/')
        if m.__spec__.submodule_search_locations is not None:
            m.__path__=[str(root/p)];m.__file__=str(root/p/'__init__.py');return
        m.__file__=str(root/(p+'.py'))
        exec(compile(blob(p+'.py'),m.__file__,'exec'),m.__dict__)
sys.meta_path.insert(0,Loader())
from extensions.map_proposal import relations as r,ca_adapter as ca
idx={'node_by_path':{'pkg/a.py':['na'],'pkg/b.py':['nb']},'edge_set':set(),'nodes':[]}
facts={'files':{'pkg/a.py':[],'pkg/b.py':[]},'skipped':set()}
known=set(idx['node_by_path'])|{'pkg/__init__.py'}
def check(base,target):
    def read(repo,rev,path): return base if rev=='base' else target
    p,u,l=[],[],[]
    with patch.object(r.gitio,'read_blob',side_effect=read):
        ev=r._file_relation_events(root,'base','target',{'path':'pkg/a.py','status':'modified'},known)
        r.handle_relations(root,'base','target',idx,facts,known,[{'path':'pkg/a.py','status':'modified'}],p,u,l)
    return {'dynamic':ev['dynamic'],'derived':ev['added_from_derived'],'proposals':[(x['confidence'],x['uncertainty']) for x in p],'unresolved':len(u)}
cases={
'prefix':('', 'from pkg.b import B\\n'),
'alias':('', 'from pkg import b\\n'),
'mixed_prefix_alias':('', 'from pkg import b\\nfrom pkg.b import B\\n'),
'mixed_direct_alias':('', 'from pkg import b\\nimport pkg.b\\n'),
'dynamic_rewrite':(\"importlib.import_module('pkg.c')\\n\", \"importlib.import_module('pkg.b')\\n\"),
'dynamic_keywords':(\"importlib.import_module(name='pkg.c')\\n\", \"importlib.import_module(name='pkg.b')\\n\"),
'dynamic_repeat_added':('', \"__import__('pkg.b')\\n__import__('pkg.b')\\n\"),
'dynamic_repeat_existing':(\"__import__('pkg.b')\\n\", \"__import__('pkg.b')\\n__import__('pkg.b')\\n\")}
for name,(a,b) in cases.items(): print(name,check(a,b))
claim={'key':'team.focus','scope':'path:pkg/new.py','value':'owner plans a rename here','claim_id':'scalar','freshness':'unverified','evidence':[]}
print('scalar_context',ca._context_line(claim,'target'))
proposal={'kind':'NODE_ADD','subject':'pkg/new.py','proposed_change':{},'evidence':[{'path':'pkg/new.py'}],'uncertainty':[]}
pack={'claims':[dict(claim),{'key':'implementation.head','value':{'head':'wrong'},'claim_id':'head'}],'conflict_rows':[{'key':'architecture.role','scope':'path:pkg/new.py','claims':[{'value':'router'},{'value':'adapter'}]}],'conflict_keys':{'architecture.role'},'unavailable_keys':set(),'project_revision':'target'}
p,l,u=ca.apply_context_admission([proposal],pack,ca.FULL,{'pkg/new.py'},set(),[],[],target_revision='target')
assert len(p)==1 and not p[0]['uncertainty'] and [x['subject'] for x in u]==['claim:head']
print('contradicted_conflict_pack: PASS (candidate retained, only contradiction unresolved)')
'@ | python -B -" in G:\jiagou\projectmind-c-convergence
 succeeded in 592ms:
prefix {'dynamic': [], 'derived': {'pkg/b.py': False}, 'proposals': [('medium', [])], 'unresolved': 0}
alias {'dynamic': [], 'derived': {'pkg/__init__.py': False, 'pkg/b.py': True}, 'proposals': [('low', ['from-import 目标可能是包 __init__ 中的同名属性而非子模块，需人工确认'])], 'unresolved': 0}
mixed_prefix_alias {'dynamic': [], 'derived': {'pkg/__init__.py': False, 'pkg/b.py': True}, 'proposals': [('low', ['from-import 目标可能是包 __init__ 中的同名属性而非子模块，需人工确认'])], 'unresolved': 0}
mixed_direct_alias {'dynamic': [], 'derived': {'pkg/__init__.py': False, 'pkg/b.py': True}, 'proposals': [('low', ['from-import 目标可能是包 __init__ 中的同名属性而非子模块，需人工确认'])], 'unresolved': 0}
dynamic_rewrite {'dynamic': ['importlib.import_module:pkg.b'], 'derived': {}, 'proposals': [], 'unresolved': 1}
dynamic_keywords {'dynamic': [], 'derived': {}, 'proposals': [], 'unresolved': 0}
dynamic_repeat_added {'dynamic': ['__import__:pkg.b'], 'derived': {}, 'proposals': [], 'unresolved': 1}
dynamic_repeat_existing {'dynamic': [], 'derived': {}, 'proposals': [], 'unresolved': 0}
scalar_context CA 上下文[unverified] team.focus@path:pkg/new.py：owner plans a rename here（人工参考，非事实证据；claim scalar，pack target）
contradicted_conflict_pack: PASS (candidate retained, only contradiction unresolved)

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only dda5246 extensions/map_proposal/convergence; git show dda5246:tests/test_p06_matrix_closure.py | Select-Object -Last 115; git show dda5246:extensions/map_proposal/relations.py | ForEach-Object -Begin {$n=0} -Process {$n++; if ($n -ge 82 -and $n -le 180) { '"'{0}: {1}' -f "'$n,$_ }}; rg -n --hidden "C-3|invariant 11|不变量 11|独立观察|FAIL|131|MUTATION_CAUGHT" extensions/map_proposal/convergence docs/agents' in G:\jiagou\projectmind-c-convergence
 exited 1 in 425ms:
extensions/map_proposal/convergence/COMMON_BASE_PLAN.md
extensions/map_proposal/convergence/CONTRACT_MANIFEST.md
extensions/map_proposal/convergence/C_ID_MIGRATION.md
extensions/map_proposal/convergence/ORACLE_MANIFEST.md
extensions/map_proposal/convergence/PORT_MANIFEST.md
extensions/map_proposal/convergence/SOURCES_MANIFEST.md
                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "pkg/ghost.py" for u in res["unresolved"]))


class S04SubdirectoryRename(unittest.TestCase):
    def test_s04_subdirectory_move_link_change(self):
        repo, base, target, tmp = build_repo(
            {"pkg/sub/a.py": A, "pkg/b.py": B},
            {"pkg/sub2/a.py": A, "pkg/b.py": B},
        )
        self.addCleanup(tmp.cleanup)
        map_data = {
            "note": "m",
            "nodes": [node("na", ["pkg/sub/a.py"]), node("nb", ["pkg/b.py"])],
            "edges": [],
        }
        res = run_engine(repo, base, target,
                         [{"path": "pkg/sub2/a.py", "status": "renamed",
                           "old_path": "pkg/sub/a.py"}],
                         map_data,
                         [{"path": "pkg/sub2/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
        links = [p for p in res["proposals"] if p["kind"] == "IMPLEMENTATION_LINK_CHANGE"]
        self.assertEqual(len(links), 1)
        # R06 identity: link-change subjects carry the old repo path and the
        # affected map node id in proposed_change.
        self.assertEqual(links[0]["subject"], "pkg/sub/a.py")
        self.assertEqual(links[0]["proposed_change"]["node_id"], "na")
        self.assertEqual(
            [p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])


class S27MalformedWithContext(unittest.TestCase):
    def test_s27_malformed_map_evidence_inside_valid_context_rejected(self):
        # valid-context malformed_payload_map: a structurally invalid node
        # (evidence item without path) inside an otherwise valid request is a
        # controlled rejection (A27). Note: whether Core's map schema REQUIRES
        # title/summary/entryPoint per node is NOT defined by the contract �?        # recorded as HUMAN_DECISION_REQUIRED_MAP_NODE_FIELDS (P07), not
        # invented here.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A, "pkg/b.py": B},
            {"pkg/a.py": A + "# t\n", "pkg/b.py": B},
        )
        self.addCleanup(tmp.cleanup)
        map_data = two_node_map()
        map_data["nodes"].append(
            {"id": "bad", "title": "t", "summary": "s",
             "entryPoint": "pkg/a.py · f()", "position": {"x": 1, "y": 2},
             "evidence": [{"reason": "no path key"}]})
        with self.assertRaises(model.RequestError):
            run_engine(repo, base, target,
                       [{"path": "pkg/a.py", "status": "modified"}],
                       map_data,
                       [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}])


class ExtensionSeamBoundary(unittest.TestCase):
    """Handler-level error mapping and hostile map text (A27/A28 at the seam)."""

    def setUp(self):
        from extensions.map_proposal import extension
        self.extension = extension

    def _ctx(self, repo):
        class Ctx:
            pass
        ctx = Ctx()
        ctx.repo = str(repo)
        return ctx

    def _repo_with_commit(self):
        # target differs from base (comment line) so the second commit is real
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A}, {"pkg/a.py": A + "# touched\n"})
        self.addCleanup(tmp.cleanup)
        return repo, base, target

    def test_malicious_map_text_controlled_rejection_not_crash(self):
        repo, base, target = self._repo_with_commit()
        hostile = {
            "note": "x" * 10000,
            "nodes": [{"id": "../escape", "title": "t", "summary": "s",
                       "entryPoint": "../../etc/passwd · f()",
                       "position": {"x": 1, "y": 2},
                       "evidence": [{"path": "../../etc/passwd", "reason": "r"}]}],
            "edges": [],
        }
        data = {"base_revision": base, "target_revision": target,
                "changed_paths": [], "code_facts": None, "current_map": hostile}
        from extension_host import ExtensionError
        with self.assertRaises(ExtensionError) as caught:
            self.extension.handle(self._ctx(repo), "POST", data)
        self.assertEqual(caught.exception.status.value, 400)

    def test_missing_pin_is_400_not_head_fallback(self):
        repo, base, target = self._repo_with_commit()
        from extension_host import ExtensionError
        data = {"changed_paths": [], "code_facts": None,
                "current_map": {"note": "n", "nodes": [], "edges": []}}
        with self.assertRaises(ExtensionError) as caught:
            self.extension.handle(self._ctx(repo), "POST", data)
        self.assertEqual(caught.exception.status.value, 400)

    def test_get_method_allowed_post_only_others_rejected(self):
        repo, base, target = self._repo_with_commit()
        from extension_host import ExtensionError
        with self.assertRaises(ExtensionError) as caught:
            self.extension.handle(self._ctx(repo), "DELETE", {})
        self.assertEqual(caught.exception.status.value, 405)


if __name__ == "__main__":
    unittest.main()
82:     `from pkg import b` may bind an attribute defined in pkg/__init__ rather
83:     than the submodule pkg/b.py, and C cannot parse declarations to know
84:     (O-1) �?such relations must stay explicitly uncertain. Aliased and
85:     parenthesized/multiline forms are AST-native. Docstrings, comments and
86:     string literals never appear here."""
87:     static, dynamic, from_aliases = set(), set(), set()
88:     for node in ast.walk(tree):
89:         if isinstance(node, ast.Import):
90:             for alias in node.names:
91:                 static.add(alias.name)
92:         elif isinstance(node, ast.ImportFrom):
93:             prefix = "." * (node.level or 0) + (node.module or "")
94:             if prefix:
95:                 static.add(prefix)
96:             for alias in node.names:
97:                 if not prefix:
98:                     static.add(alias.name)
99:                     continue
100:                 candidate = prefix + alias.name if prefix.endswith(".") \
101:                     else f"{prefix}.{alias.name}"
102:                 static.add(candidate)
103:                 from_aliases.add(candidate)
104:         elif isinstance(node, ast.Call):
105:             func = node.func
106:             if isinstance(func, ast.Name) and func.id == "__import__":
107:                 dynamic.add(_dynamic_tag(node, "__import__"))
108:             elif isinstance(func, ast.Attribute) and func.attr == "import_module":
109:                 dynamic.add(_dynamic_tag(node, "importlib.import_module"))
110:     return static, dynamic, from_aliases
111: 
112: 
113: def _dynamic_tag(call_node, api):
114:     """Dynamic import tag includes the string target when statically visible
115:     (Codex HIGH-2: only diffing API names made `__import__('pkg.b')` �?    `__import__('pkg.c')` a silent absence, violating C-3)."""
116:     if call_node.args:
117:         arg = call_node.args[0]
118:         if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
119:             return f"{api}:{arg.value}"
120:     return api
121: 
122: 
123: def imported_paths(repo, revision, source_path):
124:     """Dotted module strings actually imported by source_path@revision (AST).
125:     Raises DiffSignalError on read/parse failure."""
126:     static, _, _ = _scan_imports(_parse_blob(repo, revision, source_path))
127:     return static
128: 
129: 
130: def _resolved_imports(repo, revision, source_path, known_paths):
131:     """resolved repo path �?module strings that reach it. Modules resolving
132:     outside known repo paths are external dependencies, not relations."""
133:     resolved = {}
134:     for module in sorted(imported_paths(repo, revision, source_path)):
135:         target_path = resolve_module(module, source_path, known_paths)
136:         if target_path:
137:             resolved.setdefault(target_path, []).append(module)
138:     return resolved
139: 
140: 
141: def _file_relation_events(repo, base, target, change, known_paths):
142:     """AST-diff one changed .py file's import sets: pinned base blob vs
143:     pinned target blob. `renamed` compares old_path@base with path@target;
144:     `added` has an empty base set; `modified` compares path@base. Raises
145:     DiffSignalError when a needed blob cannot be read or parsed."""
146:     path = change["path"]
147:     status = change["status"]
148:     base_ref = change.get("old_path") if status == "renamed" else None
149:     if base_ref is None and status == "modified":
150:         base_ref = path
151:     if base_ref:
152:         base_resolved = _resolved_imports(repo, base, base_ref, known_paths)
153:         base_dynamic = _scan_imports(_parse_blob(repo, base, base_ref))[1]
154:     else:
155:         base_resolved, base_dynamic = {}, set()
156:     target_static, target_dynamic, target_from_aliases = _scan_imports(
157:         _parse_blob(repo, target, path))
158:     target_resolved = {}
159:     for module in sorted(target_static):
160:         resolved = resolve_module(module, path, known_paths)
161:         if resolved:
162:             target_resolved.setdefault(resolved, []).append(module)
163:     added = {p: mods for p, mods in target_resolved.items() if p not in base_resolved}
164:     return {
165:         "path": path,
166:         "added": added,
167:         # Codex MEDIUM-4: a resolved target reached ONLY through from-import
168:         # alias expansion may actually be a package-__init__ attribute �?the
169:         # proposal must carry that ambiguity, never medium confidence.
170:         "added_from_derived": {
171:             p: all(m in target_from_aliases for m in mods)
172:             for p, mods in added.items()
173:         },
174:         "removed": {p: mods for p, mods in base_resolved.items() if p not in target_resolved},
175:         "dynamic": sorted(target_dynamic - base_dynamic),
176:     }
177: 
178: 
179: def handle_relations(repo, base, target, indexes, facts, known_paths, relation_changes,
180:                      proposals, unresolved, limits):
rg: docs/agents: 系统找不到指定的文件。 (os error 2)
extensions/map_proposal/convergence\CONTRACT_MANIFEST.md:19:12. 相关 conflict 进 unresolved HUMAN_REQUIRED；C 不选边。未覆盖 ≠ 不存在；不解析 do_not_assume 中的数字。相同固定输入 + 固定独立观察 = 相同输出；不嵌时间戳/随机值。

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Encoding utf8 extensions/map_proposal/convergence/CONTRACT_MANIFEST.md; Get-Content -Encoding utf8 extensions/map_proposal/convergence/SOURCES_MANIFEST.md; Get-Content -Encoding utf8 extensions/map_proposal/convergence/ORACLE_MANIFEST.md; Get-Content -Encoding utf8 extensions/map_proposal/convergence/COMMON_BASE_PLAN.md | Select-Object -First 90; git show dda5246:tests/test_real_b_integration.py | Select-Object -Skip 260 -First 70' in G:\jiagou\projectmind-c-convergence
 succeeded in 387ms:
# C Convergence �� Contract Manifest (W0)

��Լ��Դ: `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa`
�淶���: c-readiness/ �� C_PRODUCT_BOUNDARY / C_INPUT_OUTPUT_CONTRACT_PROPOSAL / C_ACCEPTANCE_PLAN / C_B_CODEFACTS_USAGE / C_CONTEXT_SAFETY_RULES / C_CONSUMABLE_INTERFACE��

## ��Ʒ����ʽ��13 ����

1. ���� = pinned Git diff + B ������ʵ + ��ǰ�˹� Project Map + ��ѡ CA����� = `proposals / unresolved / no_proposal / limits` + ��������ʵ����׷�١�`UNKNOWN` �� unresolved������ǿ proposal��
2. �����ѡ: `NODE_ADD / RELATION_ADD / RELATION_REMOVE_CANDIDATE / IMPLEMENTATION_LINK_CHANGE / NODE_REMOVE_CANDIDATE / RESPONSIBILITY_CHANGE`��ÿ�������ֶΡ��ǿտɶ�λ revision/path evidence��confidence��uncertainty��`status=PROPOSED`��`human_required=true`��
3. C ��д��ʽ��ͼ�������� position�������� accept/reject�����ٲ� CA conflict�������� B �������������༭ CA registry�����ӹ� D worklog��ְ��/�ܹ�����/��ϵ���� = INFERENCE������/·��/diff = FACT��
4. base/target �������� 40/64 λСд SHA��ȱ pin��HEAD���� SHA һ�ɾܾ������ô� snapshot ͵������ͼ�ް汾���ݣ�target SHA ����֤����ͼ���á�
5. compare ��Դ�� A/caller �� changed_paths��Core `baseRevision / targetRevision / changes[{code,path,oldPath?}]` ����ʽ����ӳ�䣻C �������ļ�����ھ���ֻ�� pinned patch/blob�����ӹ�������֤�ݡ�
6. ��ͼ�� Core `{note,nodes,edges}` ���գ��ǿ� nodes �� title/summary/entryPoint/position/evidence Լ�����ñ����������ſ������뱣�� position����ѡ proposed_change ���� position��
7. B ��ʵ���� revision/files/skipped ������ name/kind/line���� import/ǩ��/����ͼ/ְ������Ŀ����ʵ��Դ��֤ revision == target������װ B ����ֵ��ͬ�汾�Ƚϡ��� diff������Ҫ base ����֤���� B ���� pinned base �ռ����� base ��ɫ��
8. changed �ļ��� B skipped �� HUMAN_REQUIRED unresolved�����ü�����Ϊ�ڵ�/��ϵǿ��ѡ����ʵ������B ������ �� limits�������а�ȫ diff?map���� B �������ڵ�� unresolved�����鹹 code_fact��
9. �����ź�����ʵ�� pinned Git diff������ base/target import AST ��֤�źš��ų��ַ���/docstring�����ý������ B ��������������δ�� �� import δ�䡣
10. Context Pack ����ʵ `validate_context_pack(pack, expected_revision=C ���� pin)`��ʧ���������ã���ʽ DEGRADED/limits ����� pack ���У�"Ӳֹͣ"= ֹͣ���Ѹ� pack��������ֹ C ����
11. CA ֻ�� current_by_scope��verified_fields ���ֶ��ж��������з�����conflict/unavailable key ���� proposal context evidence��revision ��Ӧ/PR ״̬/contract shape/implementation ״̬����� git/gh ���飻state/merged/draft �ֱ�˶ԣ������� = UNKNOWN��ì���Զ���֤��Ϊ׼����¼ claim_id ��˫��ֵ��pack ���ٿ��š�
12. ��� conflict �� unresolved HUMAN_REQUIRED��C ��ѡ�ߡ�δ���� �� �����ڣ������� do_not_assume �е����֡���ͬ�̶����� + �̶������۲� = ��ͬ�������Ƕʱ���/���ֵ��
13. `base==target` ����ɱ�������/��ʵһ����У�飬�ٷ����� proposal����˵�� map drift �����ڱ��β����жϡ��˹� REJECTED��ͬ subject/kind ������δ��ĺ�ѡ��ѭ F20 ���ƣ��޽����źŲ������˹�����

## ������һ����·��

����/·��/pin У�� �� Core compare ���� �� B �� CA ���У�� �� �����ռ������仯/import �仯/��ͼ·��ӳ��/Ŀ������� �� ����ѡ��Դͳһ��� skipped��֤�ݡ���ͻ��CA ׼�� �� ��Ͱ��� �� �����ֶ�ͶӰ��

���ź�ͨ���������У��κε�һͨ��������"����û��"���������ļ��������������ֻ��һ�����ڣ������������� union������δ���׼����ʱ��� candidates �ֶ�д��ѡ��
# C Convergence �� Source Manifest (W0)

ʵʩ����: `G:/jiagou/C_CONVERGENCE_PLAN.md`����Ŀ¼���� manifest ��Ψһ���Σ���

## 1. Frozen Heads

| ���� | �����ʶ | ��; |
|---|---|---|
| TEAM C | `3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`; branch `feat/role-c-map-proposal`; PR #35; owner `bjtxcy` | C �Ľ��������� baseline������֧ `integration/c-convergence-v1` ����� |
| TEAM C fixed base | `7484d44ddeac3c054ca3ba68f92293d965bb615c` | ʶ�� TEAM C �����Ķ� |
| LOCAL C | `5058c54aa52243c15b286a4922a362c48c941967`; branch `feat/map-proposal-mvp`; PR #34 | �����ο���ѡ������ֲ��Դ |
| LOCAL C-only base | `f43dcaf85141a72265e14946c10fee627e3cc7be` | �ų� LOCAL �����е� B/D/CA ���� |
| ��ͬ��Լ�ĵ� | `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa` | Ψһ��Ʒ��Լ��Դ |
| B ���սӿ� | PR #31 @ `80e091acefd278fda03e188a125147b0aa5eedc5` | ʵ�� Code Facts ���ѱ߽� |
| CA ���սӿ� | PR #29 @ `9ea23491d1849f21bad9f60c1c1ca8df55bb5936` | ʵ�� Context Pack validator/resolver �߽� |

## 2. Frozen Source Roots��ֻ�����к�/���ž���Ӧ��Щ����汾��

- TEAM_ROOT = `C:/Users/������/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/team/LingweiXingzhi-projectmind-core-3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`
- LOCAL_ROOT = `C:/Users/������/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local`
- T.extension = TEAM_ROOT/extensions/map_proposal/extension.py
- L.model = LOCAL_ROOT/extensions/map_proposal/model.py
- L.facts = LOCAL_ROOT/extensions/map_proposal/facts_adapter.py
- L.ca = LOCAL_ROOT/extensions/map_proposal/ca_adapter.py
- L.diff = LOCAL_ROOT/extensions/map_proposal/diff_model.py
- L.engine = LOCAL_ROOT/extensions/map_proposal/engine.py

## 3. ����֤���ļ���SHA-256��

| �ļ� | SHA-256 |
|---|---|
| PROJECTMIND_C_DUAL_IMPLEMENTATION_REVIEW.md | `1c3ce67f8b4bd404c8319362281a4e828b25945354655ec34f969dc4874b8f6c` |
| dual_results.json (58 ��ԭʼ��¼) | `6a14d1a09affb8ffabf092debc7876a90dd4ee337df160c349e33374c2921483` |

## 4. ����ӳ��

- KEEP_FROM_TEAM: K01�CK04���� PORT_MANIFEST.md��
- PORT_FROM_LOCAL: P01�CP09���� PORT_MANIFEST.md��
- REIMPLEMENT: R01�CR07���� PORT_MANIFEST.md��
- DROP_FROM_TEAM: T01�CT06��DROP_FROM_LOCAL: L01�CL12���� PORT_MANIFEST.md��

������� NEITHER_READY / CONFIDENCE=HIGH ���򱾷�֧�ı䡣PR OPEN/Draft ״̬����ʷ�۲죻δ��ʵ����Ҫ���ⲿ��ʵ�������¶������顣

## 5. Integration Branch

`integration/c-convergence-v1` ���Ϊ TEAM C frozen HEAD `3bd980de`��C ʵʩ��Χ�޶�: `extensions/map_proposal/`��C contract/���ɲ��ԡ���Ҫ C �������ĵ������� A/B/D/CA �����ɸ� owner �������������ڱ���֧�޸� `extension_host.py`��
# C Convergence �� Oracle Manifest (W0)

S01�CS30 һһ��Ӧ���� Common Acceptance Matrix A01�CA30��Ŀ��ȫ�� PASS��������ʷ״̬���� oracle��������������ʼ A16 ȱ position��X10 empty-map����ʼ A27-map-shape��������ȱ�ݻ����� oracle��

| ID | Common / ���� | ������Ե�Ŀ����Ϊ | ���� |
|---|---|---|---|
| S01 | A01 real NODE_ADD | ��ģ���� map �������� B ����: ǡ��Ԥ�ڽڵ㣬git_diff + �ɻط� code_fact + map �жϣ�ȫ��/changed-only �������޹ؽڵ㣻PROPOSED/human_required��������ģ�鲻ƾ class �ż������� | A01��X19 |
| S02 | A02 real RELATION_ADD | ����ʵ�ʿ��� import: Ԥ�� from/to �� RELATION_ADD����ȷԴ diff + ���� map ֤�ݣ�����û���Դ����� | A02��X01; class ǰ/�� import |
| S03 | A03 relation removal | ������ import ��ʧ: ��Ӧ���� edge �� REMOVE_CANDIDATE������Դ�� import ���Ƴ���churn ���Ƴ��� | A03��X11/X13; ���ļ�ʣ�� import |
| S04 | A04 implementation link | rename/move: ��Ӧ node ·�����£�old@base/new@target���� NODE_ADD�� | A04; �ƶ���Ŀ¼ |
| S05 | A05 node removal | node ȫ evidence ��ȷ�� target ��ʧ: �����Ŷ�ɾ����ѡ����һ·����������ɾ����ѡ�� | A05; �� evidence ���ֱ��� |
| S06 | A06 responsibility change | entryPoint ��������/��ʧ: ��Ӧ node ����/ʵ�����Ӻ�ѡ������֤���� B ��������ѡ�����ݵ��׸�������š� | A06; ���������� |
| S07 | A07 comment only | ��ǿ proposal����ȷ comments_only ԭ�����޹��˹����� | A07��X20 |
| S08 | A08 formatting only | �� proposal����ʽԭ�򣻲����к�/����Ư��������ְ�� | A08 |
| S09 | A09 helper only | ����ְ��� helper �� NODE_ADD�������������ź���ǿ proposal�� | A09��F10 |
| S10 | A10 internal class only | ����ְ����ڲ� class �� NODE_ADD����ʾ��������ְ����ʵ�� | A10��F9 |
| S11 | A11 docstring only | �� docstring���� import �ı������ϵ/�ڵ�ǿ proposal�������������仯Ҳ���ܰ��ַ����� import�� | A11��X03/X12 |
| S12 | A12 test noise | �� test/generated ������ҵ��ܹ���ѡ�������������˹� unknown��ȷ�� map ���水ʵ��֤�ݡ� | A12; R02/R05 �������� |
| S13 | A13 B skipped | ��ʵ skipped changed Դ HUMAN_REQUIRED���κ�ͨ��/���� candidates ��������Դ��ǿ��ѡ������Դ�Թ����� | A13��X04/X21; ��ʵ collector �﷨��Դ |
| S14 | A14 B mismatch | supplied/installed B mismatch һ���ܿؾܾ���ͬ revision���� changes ���ƹ��� | A14��X06; ��װ B ע�� mismatch |
| S15 | A15 B unavailable | ��ȷ limits/DEGRADED����ȫ diff?map ��֧�����У��� B ����ģ�� unresolved�����鹹 code_fact�� | A15; ���� rename ���� |
| S16 | A16 stale map | ���� base ɾ����target ȫ evidence ȱʧ���� stale removal candidate����ȡδ֪ �� ȱʧ��base==target �� proposal + map drift limit�� | A16-valid-map `4f95f010...`��F11/F15 |
| S17 | A17 ambiguous mapping | �� map owner: ��/�����ŶȲ��� multiple candidate nodes �� unresolved������ϵ�ѡ�� | A17; �� owner rename |
| S18 | A18 missing evidence | ���ļ��� facts/diff ֤�ݲ���: unresolved UNKNOWN����ǿ��ѡ��B û��Ŀ �� �ܹ������ڡ� | A18; ������/ȱ�ؼ�֤�� |
| S19 | A19 CA conflict | relevant key/scope conflict �����κ� proposal evidence����غ�ѡ HUMAN_REQUIRED����ȷ�޹ؽڵ�������Ч��ѡ�� | A19��X14/X15/X18 |
| S20 | A20 stale claim | validated stale �����������з������� context_claim��������������� limits/UNKNOWN�� | A20; stale/proposal/research/history ���� |
| S21 | A21 multi-scope | ��ʵ�Ϸ� pack ͬ key �� scope ����ѡ��㣻�������;�ֱ����ѣ����� current ͶӰ����������� | A21; ������� + �� scope ���� |
| S22 | A22 verified_fields | ֧���ֶ�����֧���ֶηֿ������� UNVERIFIED/��ϡ���������ʵ֧�ţ��� freshness ��������ֵ�� | A22; �� evidence ref���ֶβ��ָ��� |
| S23 | A23 unavailable | �Ϸ� unavailable/stale fixture �� validator PASS��C ��α������ DEGRADED�����ֵ�ų�����ȷ UNKNOWN/limits�� | A23 `b3addc5a...`; �滻�� C_A23 �Բ� |
| S24 | A24 invalid pack | ��ʵ validator �ܾ�: ���������ѡ��� context_claim����ʽ DEGRADED��������Ч diff/B/map ��ѡ�Կɴ��ڡ� | A24; ͬ SHA ȱ�ֶ�/������/�� revision |
| S25 | A25 coherent poison | �ṹ�� digest �Ϸ��� poison ���� evidence/rationale����Ӱ����ʵ�ж�����ֵ�� UNKNOWN��ì�ܼ�¼ claim_id/˫��ֵ��pack ���ٿ��š� | A25��X05/X16/X17 `ea8cbd8f...`(X17); ���� key/�����ı������鲻���� |
| S26 | A26 determinism | �̶����� + �̶��ⲿ�۲��ظ��ֽ�һ�£�ID ������żȻ����˳����ʱ���/������� | A26-repeat��X09; ������� |
| S27 | A27 malformed input | HEAD/�� SHA/�� facts shape/�� map shape/ȱ�ֶ��ܿؾܾ�����װ B �쳣 shape ������������ available�� | A27; valid-context malformed_payload_map |
| S28 | A28 path abuse | changed/old_path/map evidence/facts/entryPoint ȫ��Դ·��Լ�����ܾ�Խ��/����·��/����ȫ���룻������������ repo �ⲹ֤�� | A28; map evidence + rename ˫�� |
| S29 | A29 no map write | ����ǰ����ʽ��ͼ�� source fixture �ļ� hash ���䣻�� save/apply/accept �� position proposed_change�� | ���� no_map_write �ֶ� + ���� hash ���� |
| S30 | A30 Host isolation | ����չ�ɼ��أ���ͨ�쳣�� runtime SystemExit �����������·�ɡ�C �߽��빲�� Host �ֱ���ԡ�**���� A/Core �޸����� PASS��** | ���� Host ���� |

## Fixture ����

- ԭʼ��¼ `request/repo/input_sha256` �ɻָ����룻`results/assertions/summary` �Ƕ���۲죬���ܸ���Ϊ expected output��ÿ�� migrated fixture ���� source record ID/hash + ��Լ���������
- A01�CA06 ������� kind��subject��map node/edge��ʵ��֤�ݡ�status/human_required���������������غ�ѡ�������ϡ�
- B skipped ����ʵ collector �����﷨��Դ��������Դ������B unavailable/mismatch ��Ϸ� B ���طֿ����ԡ�
- CA �������: ���� validator PASS/REJECT���ٲ� C ��Ϊ���������ް�����������ͬʱ�ж�����ѡ������
- ��̬/��ԵȲ�֧���źű����� UNKNOWN ������ԡ�F18 �޽����źš�F19 ��̬������F20 �˹������X07 mode��X09 ID collision�����ļ���ϵɾ��֤��Ϊ 30 ���ڲ���Ҫ���塣

## �ؼ�����ê��

| Record ID | input_sha256 |
|---|---|
| X01-unchanged-decls-real-import | `351d9d86a0cc43fa205957e4a349578449aec5458bdd52ba7ef5947955de78cc` |
| X04-skipped-relation | `2d5d6fc0df62b8fe39112597850a74c344b39b90f48e1c14b4ec7dc933c190dd` |
| X17-hidden-open | `ea8cbdf902699cf3301a8dcee42f2bb719a771bedf726c0f5cd232755f36d8e3` |
| X18-conflict-by-scope | `deb92c02ee7a494bb64157d1ce9c174296bdf1928ace2b7b233901bbaebe2498` |
| A16-valid-map | `4f95f010ada0bb012d82611eb94b2b30c443139fd968288bd3855034794b7726` |
| A23 | `b3addc5ad3f0e2926296d979a85234bfdce4b5f543cc8f687d52962775ba944f` |
# C Convergence �� Common Base Plan & Dependency Registration (W0)

## 1. Common Base

���� common base ��δ�� A/Core owner ��ʽȷ�ϡ�����֧�Ĵ��������� C_CONVERGENCE_PLAN ��11��:

- ʵ����� = TEAM C frozen HEAD `3bd980de`������ baseline���� LOCAL HEAD����
- C-only ��ơ�oracle��port manifest �ѹ̶����������������������ƽ���
- ��ͬ Core ������extension_host / compare seam�������ֿⶳ�� base `7484d44ddeac3c054ca3ba68f92293d965bb615c` �Ľӿڱ�̣����������� rebase ���� SHA �仯��SOURCES_MANIFEST.md ������¼ TEAM source SHA �� C-only diff ��Դ��

## 2. �ⲿ�����Ǽǣ������Ǽǣ��������� gate��

| ���� | Oracle | Owner | ״̬ | �� C ��Ӱ�� |
|---|---|---|---|---|
| **D1 (A30/F12): ���� Host runtime SystemExit ����** | S30: ����չ���ɣ�������չ��ͨ Exception �� runtime SystemExit �ֱ�ע�룬���� route �Կɵ��ã�����ֻ�� load �� C �ڲ� catch | A/Core owner���޸� extension_host.py ���ṩ���� oracle �ĸ���ִ�л��ƣ� | **BLOCKER �� δ���ʱ���岻�ܱ� 30/30 PASS** | C ���޸� extension_host.py��C ֻ�������� B/CA �����߽�ĸ�����ԡ�S30 ��� EXTERNAL_BLOCKED ֱ������������ء� |
| D2: B Code Facts �ӿڣ�PR #31 @ `80e091ac`�� | S13�CS15 ����ʵ collector ��Ϊ | B owner | ����ӿ���Ϊ���ձ߽磻����ʱ���¶������� | R02 ���� revision/files/skipped ��Լ��� |
| D3: CA Context Pack validator/resolver��PR #29 @ `9ea23491`�� | S19�CS25 ����ʵ validator ��Ϊ | CA owner | ����ӿ���Ϊ���ձ߽磻����ʱ���¶������� | P01/R04 ����ʵ validate_context_pack |
| D4: Core compare �� C route �˵��� | S29 + ����չ smoke | A/Core owner + TEAM C owner | �� W6 | pinned ���� + ����ͶӰ + ��ʽ��ͼ hash ���� |

## 3. �ύ���У����� C_CONVERGENCE_PLAN ��11.4��

convergence: establish W0 contract oracle �� complete W1 input and evidence gates �� implement W2 diff-map reasoning �� implement W3 relation analysis �� implement W4 CA trust �� implement W5 compatibility and identity �� W6 integration suite��

ÿ�׶ζ��� commit������ owner �������ˡ�normal push only���� force push��

## 4. Gate ���ѣ�C_CONVERGENCE_PLAN ��10 ժҪ��

- 30/30 PASS �������� READY ����S30 δ����ʱ���� gate ������������ C �ڲ� catch �����
- ���� kind ���� evidence��PROPOSED��human_required���� position���޵�ͼд�롣
- poison/conflict/stale/unavailable/δ֧���ⲿ��ʵ���� proposal ǿ֤�ݡ�
- C ��ʵʩ diff ������/��д B��CA registry��D��Core Host��
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
        # Hash the FORMAL map file (Codex false-green fix: hashing
        # implementation files did not verify formal-map preservation).
        map_files = [ROOT / "data" / "project-map.json"]
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

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg --files G:/jiagou/projectmind-validation-review | rg 'C_PRODUCT_BOUNDARY|C_CONTEXT_SAFETY|C_INPUT_OUTPUT'; git status --short" in G:\jiagou\projectmind-c-convergence
 succeeded in 360ms:
G:/jiagou/projectmind-validation-review\c-readiness\C_PRODUCT_BOUNDARY.md
G:/jiagou/projectmind-validation-review\c-readiness\C_INPUT_OUTPUT_CONTRACT_PROPOSAL.md
G:/jiagou/projectmind-validation-review\c-readiness\C_CONTEXT_SAFETY_RULES.md
 M extensions/map_proposal/analysis.py
 M extensions/map_proposal/engine.py
 M tests/test_p06_matrix_closure.py

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git -C G:/jiagou/projectmind-validation-review show e43203ba6cc678e9d7726eb897d51b3acfcb9baa:c-readiness/C_PRODUCT_BOUNDARY.md | Select-String -Pattern 'C-3' -Context 2,10; git -C G:/jiagou/projectmind-validation-review show e43203ba6cc678e9d7726eb897d51b3acfcb9baa:c-readiness/C_CONTEXT_SAFETY_RULES.md | Select-String -Pattern '矛盾|不再|独立' -Context 2,3" in G:\jiagou\projectmind-c-convergence
 succeeded in 370ms:
codex
定点执行复现了两个缺口：`import_module(name='…')` 的目标变化仍不会进入 unresolved；同一文件同时含别名导入和明确的模块导入时，明确依赖也会被降为 low。重复的相同动态调用去重正常，标量上下文渲染和矛盾 pack 的冲突禁用也通过了定点检查。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import subprocess
for p in ['c-readiness/C_PRODUCT_BOUNDARY.md','c-readiness/C_CONTEXT_SAFETY_RULES.md']:
 s=subprocess.check_output(['git','-C','G:/jiagou/projectmind-validation-review','show','e43203ba6cc678e9d7726eb897d51b3acfcb9baa:'+p]).decode('utf-8')
 lines=s.splitlines()
 for i,line in enumerate(lines):
  if 'C-3' in line or ('pack' in line.lower() and ('不再' in line or '矛盾' in line)):
   print(p, i+1, '\\n'.join(lines[max(0,i-1):i+7]))
'@ | python -B -" in G:\jiagou\projectmind-c-convergence
 succeeded in 439ms:
codex
**53f3580..dda5246**

Reviewed committed target objects only; excluded dirty working-tree changes.

**Findings by severity**

- **HIGH — HIGH-2 remains incomplete.** [_dynamic_tag](/G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:116) reads only positional arguments. Changing `importlib.import_module(name='pkg.c')` to `importlib.import_module(name='pkg.b')` produces `dynamic=[]` and zero unresolved entries. This valid, statically visible target change still violates C-3. Recognize the `name` keyword and add a regression guard.

- **MEDIUM — alias downgrade also downgrades explicit imports.** [Alias provenance tracking](/G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:103) loses provenance when identical module strings arise through different import forms. Adding both `from pkg import b` and `from pkg.b import B` marks `pkg/b.py` as entirely alias-derived and emits **low** confidence with attribute ambiguity. The same happens with `import pkg.b` alongside the alias import. Track explicit/prefix provenance separately; downgrade only targets lacking that support.

**FALSE_GREEN_RISK**

Existing guards miss keyword dynamic targets and mixed alias/explicit provenance. Consequently, the reported green suites can coexist with both reproduced defects.

The formal-map preservation guard now compares bytes of `data/project-map.json`, correcting the previous wrong-file check. Full and mutation suites were not independently rerun: they require filesystem writes unavailable in this read-only environment. Verification used target-loaded code and in-memory blob probes.

**CONTRACT_REGRESSIONS**

- HIGH-1 scalar rendering: verified fixed.
- HIGH-3 contradicted-pack conflict suppression: verified fixed; independent candidate survives, with only contradiction unresolved.
- MEDIUM-4 alias-only ambiguity: verified fixed, but mixed provenance regresses as described above.
- Pure `from pkg.b import B`: remains **medium**.
- Repeated identical dynamic calls: one unresolved when newly added; zero additional noise when already present.
- Invariant 11: no new violation found. C-3 remains violated by keyword target changes.

**SECURITY_FINDINGS**

None identified in this incremental range.

**VERDICT: FAIL** — 1 HIGH residual defect and 1 MEDIUM regression.
tokens used
60,305
**53f3580..dda5246**

Reviewed committed target objects only; excluded dirty working-tree changes.

**Findings by severity**

- **HIGH — HIGH-2 remains incomplete.** [_dynamic_tag](/G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:116) reads only positional arguments. Changing `importlib.import_module(name='pkg.c')` to `importlib.import_module(name='pkg.b')` produces `dynamic=[]` and zero unresolved entries. This valid, statically visible target change still violates C-3. Recognize the `name` keyword and add a regression guard.

- **MEDIUM — alias downgrade also downgrades explicit imports.** [Alias provenance tracking](/G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:103) loses provenance when identical module strings arise through different import forms. Adding both `from pkg import b` and `from pkg.b import B` marks `pkg/b.py` as entirely alias-derived and emits **low** confidence with attribute ambiguity. The same happens with `import pkg.b` alongside the alias import. Track explicit/prefix provenance separately; downgrade only targets lacking that support.

**FALSE_GREEN_RISK**

Existing guards miss keyword dynamic targets and mixed alias/explicit provenance. Consequently, the reported green suites can coexist with both reproduced defects.

The formal-map preservation guard now compares bytes of `data/project-map.json`, correcting the previous wrong-file check. Full and mutation suites were not independently rerun: they require filesystem writes unavailable in this read-only environment. Verification used target-loaded code and in-memory blob probes.

**CONTRACT_REGRESSIONS**

- HIGH-1 scalar rendering: verified fixed.
- HIGH-3 contradicted-pack conflict suppression: verified fixed; independent candidate survives, with only contradiction unresolved.
- MEDIUM-4 alias-only ambiguity: verified fixed, but mixed provenance regresses as described above.
- Pure `from pkg.b import B`: remains **medium**.
- Repeated identical dynamic calls: one unresolved when newly added; zero additional noise when already present.
- Invariant 11: no new violation found. C-3 remains violated by keyword target changes.

**SECURITY_FINDINGS**

None identified in this incremental range.

**VERDICT: FAIL** — 1 HIGH residual defect and 1 MEDIUM regression.
