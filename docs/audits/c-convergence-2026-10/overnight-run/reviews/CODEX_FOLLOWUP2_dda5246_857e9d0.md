Reading additional input from stdin...
2026-10-04T17:44:02.597851Z ERROR codex_models_manager::manager: failed to refresh available models: request timed out
OpenAI Codex v0.160.0
--------
workdir: G:\jiagou\projectmind-c-convergence
model: gpt-6.1-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: medium
reasoning summaries: none
session id: 01a10803-ed8f-7550-9187-3f7f5e57ae5d
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

FOLLOW-UP ROUND 2 (final targeted round per the review-limit protocol). Range: dda5246..857e9d0. Your round-2 findings were: (HIGH) _dynamic_tag missed name= keyword dynamic targets — now recognized in relations.py _dynamic_tag with guard test_x02_changed_dynamic_keyword_target_is_not_silent; (MEDIUM) alias downgrade applied to strings with mixed provenance — provenance is now plain-vs-alias per occurrence in _scan_imports/_file_relation_events with guard test_mixed_provenance_from_and_explicit_import_keeps_medium. Verify ONLY these two fixes in the committed code at 857e9d0 and state whether each is resolved. Then give the overall verdict for the whole audited history 78c2751..857e9d0: PASS | PASS_WITH_LIMITS | FAIL with any remaining findings.
warning: Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.
  user (C:\Users\李则兴\.codex\config.toml): `features.rmcp_client` is ignored.
warning: Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.
  user (C:\Users\李则兴\.codex\config.toml): `features.rmcp_client` is ignored.
2026-10-04T17:44:04.864633Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
ERROR: Reconnecting... 2/5
ERROR: Reconnecting... 3/5
ERROR: Reconnecting... 4/5
ERROR: Reconnecting... 5/5
warning: Falling back from WebSockets to HTTPS transport. request timed out
codex
我会只核验 `dda5246..857e9d0` 的两项修复及回归测试，再据此给出整个已审历史的最终结论。先读取仓库审查规范；全程只读。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content README.md; Get-Content docs/standards/AGENT_STANDARD.md; Get-Content docs/standards/TEAM_SOP.md; Get-Content C:/Users/李则兴/.codex/skills/code-review/SKILL.md' in G:\jiagou\projectmind-c-convergence
 succeeded in 220ms:
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
我会使用 `code-review` 技能，分别检查规范符合性和修复正确性；两条审查线都限定在这两项修复。最终报告按你要求的格式输出。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse HEAD dda5246 857e9d0; git log dda5246..857e9d0 --oneline; git diff dda5246 857e9d0 --stat; git diff dda5246 857e9d0' in G:\jiagou\projectmind-c-convergence
 succeeded in 247ms:
?? tests/acceptance_matrix.py
857e9d0019759466a82dfeae2aa8291f0f3e1b56
dda524607562e11eb07fc201bf1f52ee3ad48763
857e9d0019759466a82dfeae2aa8291f0f3e1b56
857e9d0 convergence: fix Codex round-2 findings — keyword dynamic targets + mixed-provenance alias downgrade
b9c2994 convergence: P07 — unparseable map entryPoints become visible degradation (R8/G-3)
 extensions/map_proposal/analysis.py  |  8 ++++++-
 extensions/map_proposal/engine.py    |  5 +++++
 extensions/map_proposal/relations.py | 43 +++++++++++++++++++++---------------
 tests/test_p06_matrix_closure.py     | 40 +++++++++++++++++++++++++++++++++
 tests/test_w3_relations.py           | 28 +++++++++++++++++++++++
 5 files changed, 105 insertions(+), 19 deletions(-)
diff --git a/extensions/map_proposal/analysis.py b/extensions/map_proposal/analysis.py
index 0452423..55c5f30 100644
--- a/extensions/map_proposal/analysis.py
+++ b/extensions/map_proposal/analysis.py
@@ -26,16 +26,21 @@ TOP_LEVEL_KINDS = ("class", "function", "async_function")
 
 
 def build_indexes(current_map):
-    """P02 node/entry indexes over the validated map."""
+    """P02 node/entry indexes over the validated map. Nodes whose entryPoint
+    cannot be parsed are reported (not silently skipped) so the RESPONSIBILITY
+    channel's inactivity is visible (R8/G-3)."""
     node_by_path = {}
     for node in current_map["nodes"]:
         for path in node["evidence_paths"]:
             node_by_path.setdefault(path, []).append(node["id"])
     entry_lookup = {}
+    unparseable_entry_points = []
     for node in current_map["nodes"]:
         path, func = parse_entry_point(node["entry_point"])
         if path:
             entry_lookup[(node["id"], path)] = func
+        else:
+            unparseable_entry_points.append(node["id"])
     node_ids = {node["id"] for node in current_map["nodes"]}
     return {
         "nodes": current_map["nodes"],
@@ -43,6 +48,7 @@ def build_indexes(current_map):
         "entry_lookup": entry_lookup,
         "node_ids": node_ids,
         "edge_set": {(edge["from"], edge["to"]) for edge in current_map["edges"]},
+        "unparseable_entry_points": unparseable_entry_points,
     }
 
 
diff --git a/extensions/map_proposal/engine.py b/extensions/map_proposal/engine.py
index 434b471..f028f8e 100644
--- a/extensions/map_proposal/engine.py
+++ b/extensions/map_proposal/engine.py
@@ -50,6 +50,11 @@ def suggest_map(repo, data) -> dict:
     limits = _dedupe(limits)
 
     indexes = analysis.build_indexes(current_map)
+    if indexes["unparseable_entry_points"]:
+        limits.append(
+            "map entryPoint 格式无法解析（期望 'path · func()' 或以 .py 结尾的路径）："
+            + ", ".join(sorted(indexes["unparseable_entry_points"]))
+            + "；这些节点的职责变化（RESPONSIBILITY）通道不会触发（诚实降级，G-3）")
 
     # Signal channels run independently (R01); a declaration-channel verdict on
     # one file never ends another channel's analysis of the same file (F05).
diff --git a/extensions/map_proposal/relations.py b/extensions/map_proposal/relations.py
index 3b3556d..a28f65d 100644
--- a/extensions/map_proposal/relations.py
+++ b/extensions/map_proposal/relations.py
@@ -72,50 +72,54 @@ def _parse_blob(repo, revision, source_path):
 
 
 def _scan_imports(tree):
-    """(static module strings, dynamic import tags, from-alias-derived
-    candidates) from one parsed module.
+    """(static module strings, dynamic import tags, plain-provenance strings)
+    from one parsed module.
 
     ImportFrom contributes its package prefix AND each prefix-qualified alias
     so `from pkg import b` (b a submodule) and `from . import b` carry the
     submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
-    Alias-derived candidates are reported separately (Codex MEDIUM-4):
-    `from pkg import b` may bind an attribute defined in pkg/__init__ rather
-    than the submodule pkg/b.py, and C cannot parse declarations to know
-    (O-1) — such relations must stay explicitly uncertain. Aliased and
-    parenthesized/multiline forms are AST-native. Docstrings, comments and
-    string literals never appear here."""
-    static, dynamic, from_aliases = set(), set(), set()
+    `plain` carries every string introduced OUTSIDE alias expansion (Import
+    names and ImportFrom prefixes); a candidate that also has plain
+    provenance must NOT be alias-downgraded, because the same string can
+    arise from an explicit import in another statement (Codex round-2
+    MEDIUM). Aliased and parenthesized/multiline forms are AST-native.
+    Docstrings, comments and string literals never appear here."""
+    static, dynamic, plain = set(), set(), set()
     for node in ast.walk(tree):
         if isinstance(node, ast.Import):
             for alias in node.names:
                 static.add(alias.name)
+                plain.add(alias.name)
         elif isinstance(node, ast.ImportFrom):
             prefix = "." * (node.level or 0) + (node.module or "")
             if prefix:
                 static.add(prefix)
+                plain.add(prefix)
             for alias in node.names:
                 if not prefix:
                     static.add(alias.name)
+                    plain.add(alias.name)
                     continue
                 candidate = prefix + alias.name if prefix.endswith(".") \
                     else f"{prefix}.{alias.name}"
                 static.add(candidate)
-                from_aliases.add(candidate)
         elif isinstance(node, ast.Call):
             func = node.func
             if isinstance(func, ast.Name) and func.id == "__import__":
                 dynamic.add(_dynamic_tag(node, "__import__"))
             elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                 dynamic.add(_dynamic_tag(node, "importlib.import_module"))
-    return static, dynamic, from_aliases
+    return static, dynamic, plain
 
 
 def _dynamic_tag(call_node, api):
-    """Dynamic import tag includes the string target when statically visible
+    """Dynamic import tag includes the statically visible string target
     (Codex HIGH-2: only diffing API names made `__import__('pkg.b')` →
-    `__import__('pkg.c')` a silent absence, violating C-3)."""
-    if call_node.args:
-        arg = call_node.args[0]
+    `__import__('pkg.c')` a silent absence, violating C-3). Both positional
+    and `name=` keyword forms are recognized."""
+    candidates = list(call_node.args)
+    candidates.extend(kw.value for kw in call_node.keywords if kw.arg == "name")
+    for arg in candidates:
         if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
             return f"{api}:{arg.value}"
     return api
@@ -154,7 +158,7 @@ def _file_relation_events(repo, base, target, change, known_paths):
         base_dynamic = _scan_imports(_parse_blob(repo, base, base_ref))[1]
     else:
         base_resolved, base_dynamic = {}, set()
-    target_static, target_dynamic, target_from_aliases = _scan_imports(
+    target_static, target_dynamic, target_plain = _scan_imports(
         _parse_blob(repo, target, path))
     target_resolved = {}
     for module in sorted(target_static):
@@ -167,9 +171,12 @@ def _file_relation_events(repo, base, target, change, known_paths):
         "added": added,
         # Codex MEDIUM-4: a resolved target reached ONLY through from-import
         # alias expansion may actually be a package-__init__ attribute — the
-        # proposal must carry that ambiguity, never medium confidence.
+        # proposal must carry that ambiguity, never medium confidence. A
+        # candidate string with plain provenance (an Import name or an
+        # ImportFrom prefix anywhere in the file) is NOT downgraded (Codex
+        # round-2 MEDIUM: same string, different import forms).
         "added_from_derived": {
-            p: all(m in target_from_aliases for m in mods)
+            p: all(m not in target_plain for m in mods)
             for p, mods in added.items()
         },
         "removed": {p: mods for p, mods in base_resolved.items() if p not in target_resolved},
diff --git a/tests/test_p06_matrix_closure.py b/tests/test_p06_matrix_closure.py
index 6e25161..447b1d8 100644
--- a/tests/test_p06_matrix_closure.py
+++ b/tests/test_p06_matrix_closure.py
@@ -82,6 +82,8 @@ def two_node_map(extra_na=()):
 
 A = "class A:\n    pass\n"
 B = "class B:\n    pass\n"
+MAIN_FN = "def main():\n    return 1\n"
+RUN_FN = "def run():\n    return 2\n"
 
 
 class S08FormattingOnly(unittest.TestCase):
@@ -280,5 +282,43 @@ class ExtensionSeamBoundary(unittest.TestCase):
         self.assertEqual(caught.exception.status.value, 405)
 
 
+class P07EntryPointDiagnostics(unittest.TestCase):
+    def test_unparseable_entry_point_is_visible_degradation_not_silence(self):
+        # R8/G-3: a map whose entryPoint strings do not match the contract
+        # format used to kill the RESPONSIBILITY channel silently. The
+        # channel's inactivity must now be visible in limits.
+        repo, base, target, tmp = build_repo(
+            {"pkg/a.py": MAIN_FN, "pkg/b.py": B},
+            {"pkg/a.py": RUN_FN, "pkg/b.py": B},
+        )
+        self.addCleanup(tmp.cleanup)
+        map_data = {
+            "note": "m",
+            "nodes": [node("na", ["pkg/a.py"], entry="主入口"),
+                      node("nb", ["pkg/b.py"])],
+            "edges": [],
+        }
+        res = run_engine(repo, base, target,
+                         [{"path": "pkg/a.py", "status": "modified"}],
+                         map_data,
+                         [{"path": "pkg/a.py", "entries": [{"name": "run", "kind": "function", "line": 1}]}],
+                         )
+        self.assertTrue(any("entryPoint 格式无法解析" in l and "na" in l
+                            for l in res["limits"]))
+        # A properly formatted entryPoint produces no diagnostic.
+        map_data2 = {
+            "note": "m",
+            "nodes": [node("na", ["pkg/a.py"], entry="pkg/a.py · main()"),
+                      node("nb", ["pkg/b.py"])],
+            "edges": [],
+        }
+        res2 = run_engine(repo, base, target,
+                          [{"path": "pkg/a.py", "status": "modified"}],
+                          map_data2,
+                          [{"path": "pkg/a.py", "entries": [{"name": "run", "kind": "function", "line": 1}]}],
+                          )
+        self.assertFalse(any("entryPoint 格式无法解析" in l for l in res2["limits"]))
+
+
 if __name__ == "__main__":
     unittest.main()
diff --git a/tests/test_w3_relations.py b/tests/test_w3_relations.py
index ddeaae2..b462614 100644
--- a/tests/test_w3_relations.py
+++ b/tests/test_w3_relations.py
@@ -230,6 +230,20 @@ class RelationChannelTests(unittest.TestCase):
         self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                             for u in res["unresolved"]))
 
+    def test_x02_changed_dynamic_keyword_target_is_not_silent(self):
+        # Codex round-2 HIGH residual: `importlib.import_module(name=...)`
+        # keyword form must be tracked like the positional form.
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module(name='pkg.c')\n",
+             "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module(name='pkg.b')\n",
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
@@ -298,6 +312,20 @@ class RelationChannelTests(unittest.TestCase):
         self.assertEqual(adds[0]["confidence"], "low")
         self.assertTrue(any("__init__" in u for u in adds[0]["uncertainty"]))
 
+    def test_mixed_provenance_from_and_explicit_import_keeps_medium(self):
+        # Codex round-2 MEDIUM regression guard: when the same module string
+        # also has plain provenance (`import pkg.b` or the `from pkg.b`
+        # prefix), the alias-only downgrade must NOT apply.
+        res = self.run_engine(
+            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
+            {"pkg/a.py": A_CLASS + "from pkg import b\nimport pkg.b\n", "pkg/b.py": B_CLASS},
+            two_node_map(),
+        )
+        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
+        self.assertEqual(len(adds), 1)
+        self.assertEqual(adds[0]["confidence"], "medium")
+        self.assertFalse(any("__init__" in u for u in adds[0]["uncertainty"]))
+
     def test_multiline_parenthesized_from_import(self):
         # Adversarial 4 (silent miss at 78c2751), valid form: parenthesized
         # multiline from-imports are AST-native, no line-based extractor.

2026-10-04T17:46:31.931479Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
2026-10-04T17:46:41.885568Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server hyper3d: OAuth refresh token was rejected: Server returned error response: invalid_grant: grant request is invalid
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Encoding utf8 extensions/map_proposal/relations.py; Get-Content -Encoding utf8 tests/test_w3_relations.py' in G:\jiagou\projectmind-c-convergence
 succeeded in 206ms:
# -*- coding: utf-8 -*-
"""Independent import-relation channel (R03, W3).

Signal AND proof are the same artifact: a per-file AST diff of the pinned
base blob against the pinned target blob. The diff patch is not parsed at
all �� a regex on patch text was only ever a candidate extractor (DROP L05)
and its line-based form silently missed relative imports, from-submodule
imports and multiline imports (adversarial cases 1a/1b/3/4, 2026-10-04).
Blob read/parse failure raises DiffSignalError �� UNKNOWN/unresolved, never
"zero imports" (C-3). Declaration-channel verdicts never gate this channel
(F05): "declarations unchanged" does not mean "no import signal" (X01/X11).

Resolution is a heuristic (dotted path �� known repo paths); modules that
resolve outside the repo (stdlib/site-packages) are not architecture
relations. Known resolution limits (namespace packages, src-layout) mean an
unresolved repo-internal import can stay invisible �� recorded limit, does
not fabricate a relation.

Removal proof domain is the whole map-node evidence domain (R03): a relation
removal candidate requires an existing map edge and ALL .py files of the
source node's evidence domain free of imports into the target domain at
target, with at least one such import at base (S03, X12 multi-source).

Known edge: a rewrite between from-import shapes can add/drop the bare
package-prefix candidate (e.g. `from . import b` �� `from .b import B`), so
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
    """Module string �� repo-relative path among known_paths. Absolute forms
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
    """Pinned blob �� AST. Raises DiffSignalError on read/parse failure
    (UNKNOWN, never silent zero)."""
    try:
        raw = gitio.read_blob(repo, revision, source_path)
        return ast.parse(raw)
    except (gitio.DiffSignalError, SyntaxError, ValueError) as exc:
        raise gitio.DiffSignalError(f"cannot verify imports of {source_path}@{revision[:8]}: "
                                    f"{type(exc).__name__}") from exc


def _scan_imports(tree):
    """(static module strings, dynamic import tags, plain-provenance strings)
    from one parsed module.

    ImportFrom contributes its package prefix AND each prefix-qualified alias
    so `from pkg import b` (b a submodule) and `from . import b` carry the
    submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
    `plain` carries every string introduced OUTSIDE alias expansion (Import
    names and ImportFrom prefixes); a candidate that also has plain
    provenance must NOT be alias-downgraded, because the same string can
    arise from an explicit import in another statement (Codex round-2
    MEDIUM). Aliased and parenthesized/multiline forms are AST-native.
    Docstrings, comments and string literals never appear here."""
    static, dynamic, plain = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.add(alias.name)
                plain.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0) + (node.module or "")
            if prefix:
                static.add(prefix)
                plain.add(prefix)
            for alias in node.names:
                if not prefix:
                    static.add(alias.name)
                    plain.add(alias.name)
                    continue
                candidate = prefix + alias.name if prefix.endswith(".") \
                    else f"{prefix}.{alias.name}"
                static.add(candidate)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "__import__":
                dynamic.add(_dynamic_tag(node, "__import__"))
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                dynamic.add(_dynamic_tag(node, "importlib.import_module"))
    return static, dynamic, plain


def _dynamic_tag(call_node, api):
    """Dynamic import tag includes the statically visible string target
    (Codex HIGH-2: only diffing API names made `__import__('pkg.b')` ��
    `__import__('pkg.c')` a silent absence, violating C-3). Both positional
    and `name=` keyword forms are recognized."""
    candidates = list(call_node.args)
    candidates.extend(kw.value for kw in call_node.keywords if kw.arg == "name")
    for arg in candidates:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
            return f"{api}:{arg.value}"
    return api


def imported_paths(repo, revision, source_path):
    """Dotted module strings actually imported by source_path@revision (AST).
    Raises DiffSignalError on read/parse failure."""
    static, _, _ = _scan_imports(_parse_blob(repo, revision, source_path))
    return static


def _resolved_imports(repo, revision, source_path, known_paths):
    """resolved repo path �� module strings that reach it. Modules resolving
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
    target_static, target_dynamic, target_plain = _scan_imports(
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
        # alias expansion may actually be a package-__init__ attribute �� the
        # proposal must carry that ambiguity, never medium confidence. A
        # candidate string with plain provenance (an Import name or an
        # ImportFrom prefix anywhere in the file) is NOT downgraded (Codex
        # round-2 MEDIUM: same string, different import forms).
        "added_from_derived": {
            p: all(m not in target_plain for m in mods)
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
                    "note": "import �ź��޷��� AST ֤ʵ����ȡ/����ʧ�ܣ������� UNKNOWN",
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
            modules = "��".join(sorted(event["added"][target_path]))
            uncertainty = []
            multi_owner = len(source_owners) > 1 or len(target_owners) > 1
            if multi_owner:
                uncertainty.append("multiple candidate nodes on this import edge")
            if event["added_from_derived"].get(target_path):
                uncertainty.append(
                    "from-import Ŀ������ǰ� __init__ �е�ͬ�����Զ�����ģ�飬���˹�ȷ��")
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
                        "label": f"import ����(��ѡ): {source_path} -> {target_path}",
                    },
                    "rationale": "��ڵ�֤��������ʵ�� import��AST ֤ʵ�����������������˹�ȷ��",
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
            modules = "��".join(sorted(event["removed"][target_path]))
            proposals.append(
                {
                    "kind": "RELATION_REMOVE_CANDIDATE",
                    "subject": f"{source_owners[0]}->{target_owners[0]}",
                    "node_ids": None,
                    "proposed_change": {
                        "from": source_owners[0],
                        "to": target_owners[0],
                        "label": f"import �Ƴ�(��ѡ): {source_path} -> {target_path}",
                    },
                    "rationale": "Դ�ڵ�֤������ȫ�� .py �ļ���Ŀ����ľ�̬ import ����ʧ��AST ֤ʵ����"
                                 "�Ƿ���ζ�ܹ���ϵ��ʧ�����ж�",
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
                    "note": "��̬/�ַ������� import�������źŲ��㣬�����Խ�����ϵ��ѡ",
                }
            )


def _domain_import_gone(repo, base, target, indexes, signal_path, source_owners,
                        target_path, known_paths, limits):
    """Removal proof over the FULL source node evidence domain: every .py
    file's imports into target_path must exist at base (somewhere in the
    domain) and be gone at target everywhere. Any read/parse failure ��
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
"""W3 convergence contract tests: the independent import-relation channel.

Oracles: S02 (real RELATION_ADD incl. X01 unchanged-declarations), S03
(relation removal + multi-source remaining import), S11 (docstring import
text is never a relation), X02 (dynamic import �� UNKNOWN unresolved), X13
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
        "entryPoint": entry or f"{paths[0]} �� main()",
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
        # F06 contract: "ͬһ�淶��Ŀ���д���任��������ϵ�仯". The AST
        # channel diffs RESOLVED import-target sets, so `import os` ��
        # `from os import path` (no repo-internal relation change) yields no
        # signal at all �� stronger than the old signal-then-suppress churn
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
        # target (same API, new module) must surface UNKNOWN again �� API-name
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

    def test_x02_changed_dynamic_keyword_target_is_not_silent(self):
        # Codex round-2 HIGH residual: `importlib.import_module(name=...)`
        # keyword form must be tracked like the positional form.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module(name='pkg.c')\n",
             "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "import importlib\nimportlib.import_module(name='pkg.b')\n",
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
        self.assertTrue(any("import �ź��޷��� AST ֤ʵ" in u["note"] or "AST" in u["note"]
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
        # b is the submodule pkg/b.py �� alias expansion must propose pkg.b.
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
        # and `b` could be an attribute of pkg/__init__ �� the candidate must
        # stay low-confidence with the ambiguity named, never medium.
        self.assertEqual(adds[0]["confidence"], "low")
        self.assertTrue(any("__init__" in u for u in adds[0]["uncertainty"]))

    def test_mixed_provenance_from_and_explicit_import_keeps_medium(self):
        # Codex round-2 MEDIUM regression guard: when the same module string
        # also has plain provenance (`import pkg.b` or the `from pkg.b`
        # prefix), the alias-only downgrade must NOT apply.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "from pkg import b\nimport pkg.b\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0]["confidence"], "medium")
        self.assertFalse(any("__init__" in u for u in adds[0]["uncertainty"]))

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

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Encoding utf8 extensions/map_proposal/engine.py; Get-Content -Encoding utf8 extensions/map_proposal/gitio.py; Get-Content -Encoding utf8 extensions/map_proposal/facts_adapter.py | Select-Object -First 100; git diff 857e9d0 -- extensions/map_proposal/relations.py tests/test_w3_relations.py; rg -n "def _dynamic_tag|candidates =|def test_x02_changed_dynamic_keyword|def test_mixed_provenance|added_from_derived|target_plain" extensions/map_proposal/relations.py tests/test_w3_relations.py' in G:\jiagou\projectmind-c-convergence
 succeeded in 406ms:
# -*- coding: utf-8 -*-
"""C convergence engine �� single canonical pipeline (R01/R06/R07 skeleton).

Pipeline (invariant order):
  request/path/pin validation �� Core compare adaptation �� B gate �� map intake
  �� independent signal channels (declaration / import / map / existence) ��
  unified admission (skipped, evidence, conflicts, CA trust) �� four-bucket
  canonical result �� legacy compatibility projection.

W1 status: gates, canonical result, identity and projection are live; signal
channels are wired but empty until W2/W3 land. No map write ever happens here.
"""
from __future__ import annotations

from extensions.map_proposal import analysis, ca_adapter, facts_adapter, model, relations, gitio


def suggest_map(repo, data) -> dict:
    request = model.validate_request(model.adapt_core_compare(data))
    if request["current_map"] is None:
        raise model.RequestError("current_map ȱʧ��C ��Ҫ��ǰ�˹���ͼԭ�ģ����ô� snapshot ͵��")
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
    if indexes["unparseable_entry_points"]:
        limits.append(
            "map entryPoint ��ʽ�޷����������� 'path �� func()' ���� .py ��β��·������"
            + ", ".join(sorted(indexes["unparseable_entry_points"]))
            + "����Щ�ڵ��ְ��仯��RESPONSIBILITY��ͨ�����ᴥ������ʵ������G-3��")

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

        # R03: independent import-relation channel �� runs regardless of
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

        # R04: CA admission �� conflict routing, evidence trust boundary, and
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
                "note": "base==target���������������ʵһ����У�飬���᰸����ͼƯ�Ʋ����ڱ��β����ж�",
            }
        )
    elif not proposals and facts["available"]:
        no_proposal.append(
            {
                "reason": "no_cross_channel_signals",
                "note": "changed_paths ���ͼ/������ʵ�޽����ź�",
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
        note_bits.append("������ʵ�����ã��ѽ�������")
    note_bits.append(f"�������� {len(proposals)} ����ѡ")
    note = "��".join(note_bits)

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
    canonical NODE_ADD proposals �� it never carries extra or un-gated items."""
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
        raise DiffSignalError("Git ��ȡʧ�ܻ�ʱ") from exc
    if result.returncode:
        raise DiffSignalError("�޷���ȡָ���ύ������")
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
# -*- coding: utf-8 -*-
"""B / Code Facts adaptation and the unified fact-availability gate (R02).

Every execution path verifies code_facts.revision == target_revision before any
early exit �� supplied facts, installed B on normal requests, same-revision
requests and empty change sets all pass through this gate (F07, DROP L06).
skipped is never treated as facts; C never assumes dependencies / call-graph /
signatures / responsibility from B.
"""
from __future__ import annotations

FACTS_LIMITS = "code facts unavailable"


class FactsMismatch(ValueError):
    """code_facts.revision != target_revision �� the whole request is rejected."""


def _normalize(facts):
    """Tolerate partial per-entry drift: C only reads name/kind/line and never
    crashes on B evolution, but the outer containers must be sound."""
    files_raw = facts.get("files") or []
    skipped_raw = facts.get("skipped") or []
    if not isinstance(files_raw, list) or not isinstance(skipped_raw, list):
        raise ValueError("code_facts files/skipped ��Ϊ�б�")
    files = {}
    for entry in files_raw:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            if not isinstance(entry.get("entries") or [], list):
                raise ValueError("code_fact entries ��Ϊ�б�")
            sanitized = []
            for item in (entry.get("entries") or []):
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    sanitized.append(
                        {
                            "name": item["name"],
                            "kind": item.get("kind") if isinstance(item.get("kind"), str) else "unknown",
                            "line": item.get("line") if isinstance(item.get("line"), int) else None,
                        }
                    )
            files[entry["path"]] = sanitized
    skipped = {s.get("path") for s in skipped_raw if isinstance(s, dict)}
    return files, skipped


def _check_revision(raw_revision, target_revision):
    if not isinstance(raw_revision, str) or raw_revision != target_revision:
        raise FactsMismatch("code_facts.revision ������� target_revision")


def load_code_facts(request_facts, repo, target_revision, wanted_paths):
    """Return ({'files': {path: entries}, 'skipped': set, 'available': bool,
    'source': str}, limits).

    - request_facts present: revision equality enforced; malformed container is
      a controlled input rejection (S27); per-entry drift tolerated.
    - request_facts absent: try in-process B (if installed). The installed B
      return value is re-pinned against target_revision (F07/X06); B failure ��
      unavailable + limits, never fabricated facts (S15).
    """
    limits = []
    if request_facts is not None:
        if not isinstance(request_facts, dict):
            raise FactsMismatch("code_facts ��Ϊ����")
        _check_revision(request_facts.get("revision"), target_revision)
        try:
            files, skipped = _normalize(request_facts)
        except Exception:  # noqa: BLE001 �� supplied shape drift is a controlled reject
            raise FactsMismatch("code_facts ��״�쳣")
        return (
            {"files": files, "skipped": skipped, "available": True, "source": "supplied"},
            limits,
        )

    try:
        from extensions.code_facts.facts import collect_code_facts  # noqa: PLC0415
    except Exception:  # noqa: BLE001 �� B not installed on this base
        limits.append(FACTS_LIMITS)
        return (
            {"files": {}, "skipped": set(), "available": False, "source": "none"},
            limits,
        )

    try:
        # Preferred: only the paths needed at target; a removed path must not
        # poison the whole call, so B rejection on wanted paths falls back to a
        # full-tree collection once.
        raw = collect_code_facts(repo, target_revision, wanted_paths or None)
    except Exception:  # noqa: BLE001
        if wanted_paths:
            try:
                raw = collect_code_facts(repo, target_revision, None)
            except Exception:  # noqa: BLE001 �� B rejects invalid inputs �� degraded
                limits.append(FACTS_LIMITS)
                return (
                    {"files": {}, "skipped": set(), "available": False, "source": "none"},
                    limits,
                )
        else:
            limits.append(FACTS_LIMITS)
tests/test_w3_relations.py:233:    def test_x02_changed_dynamic_keyword_target_is_not_silent(self):
tests/test_w3_relations.py:315:    def test_mixed_provenance_from_and_explicit_import_keeps_medium(self):
extensions/map_proposal/relations.py:115:def _dynamic_tag(call_node, api):
extensions/map_proposal/relations.py:120:    candidates = list(call_node.args)
extensions/map_proposal/relations.py:161:    target_static, target_dynamic, target_plain = _scan_imports(
extensions/map_proposal/relations.py:178:        "added_from_derived": {
extensions/map_proposal/relations.py:179:            p: all(m not in target_plain for m in mods)
extensions/map_proposal/relations.py:224:            if event["added_from_derived"].get(target_path):

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"gitio\\.\" extensions/map_proposal/analysis.py extensions/map_proposal/ca_adapter.py; Get-Content -Encoding utf8 extensions/map_proposal/analysis.py | Select-Object -Skip 150 -First 120" in G:\jiagou\projectmind-c-convergence
 succeeded in 372ms:
extensions/map_proposal/analysis.py:319:        target_paths = gitio.ls_tree_names(repo, target)
extensions/map_proposal/analysis.py:320:        base_paths = gitio.ls_tree_names(repo, base)
extensions/map_proposal/analysis.py:321:    except gitio.DiffSignalError as exc:

def _is_generated(path):
    lowered = path.lower()
    return any(token in lowered for token in ("generated", "/migrations/", "_pb2.py"))


def handle_added(change, target, indexes, facts, proposals, unresolved, no_proposal):
    """R01 NODE_ADD: new file + B declarations + no map coverage. Precision
    rules (S09/S10/S12): test/generated noise and already-covered paths never
    become nodes; responsibility is INFERENCE with explicit uncertainty."""
    path = change["path"]
    if indexes["node_by_path"].get(path):
        no_proposal.append({"paths": [path], "reason": "path already declared in map evidence domain"})
        return
    if not path.endswith(".py"):
        no_proposal.append({"paths": [path], "reason": "non-python addition"})
        return
    if _is_test_noise(path):
        no_proposal.append({"paths": [path], "reason": "test-only addition"})
        return
    if _is_generated(path):
        no_proposal.append({"paths": [path], "reason": "generated or mechanical file"})
        return
    if not facts["available"]:
        unresolved.append(
            {
                "subject": path,
                "reason": "HUMAN_REQUIRED",
                "evidence": [diff_evidence(target, path, "added; code facts unavailable")],
                "note": "B �����ã����鹹 code_fact ֤�ݣ�����·����",
            }
        )
        return
    entries = facts["files"].get(path)
    if entries is None:
        unresolved.append(
            {
                "subject": path,
                "reason": "HUMAN_REQUIRED",
                "evidence": [diff_evidence(target, path, "added; no parseable declarations")],
                "note": "��������ʵ�����鹹 code_fact ֤�ݣ�B ����Ŀ�����ڼܹ��ϲ�����",
            }
        )
        return

    classes = [e for e in entries if e.get("kind") == "class" and "." not in e.get("name", "")]
    uncertainty = ["responsibility inferred from filename and declarations �� human must confirm"]
    entry_point = None
    if len(classes) == 1:
        entry_point = f"{path} �� {classes[0]['name']}"
    elif len(classes) > 1:
        uncertainty.append("multiple top-level classes; primary entry point not asserted")
    else:
        uncertainty.append("function-only module; architecture node decided by human, not by class threshold")
    proposed_change = {
        "node_id": node_id_for_path(path, indexes["node_ids"]),
        "title": path.rsplit("/", 1)[-1].removesuffix(".py"),
        "summary": f"���ļ����� {len(entries)} ��������ְ���ѡ�����˹�ȷ��",
    }
    if entry_point:
        proposed_change["entryPoint"] = entry_point
    proposals.append(
        {
            "kind": "NODE_ADD",
            "subject": path,
            "node_ids": None,
            "proposed_change": proposed_change,
            "rationale": "�����ļ� + B ������ʵ����ͼ֤�����޶�Ӧ�ڵ㣻ְ��Ϊ INFERENCE�����˲þ�",
            "evidence": [
                diff_evidence(target, path, "added"),
                *fact_evidence(target, path, entries),
                map_node_evidence("(map)", f"no node evidence covers {path}"),
            ],
            "confidence": "low",
            "uncertainty": uncertainty,
        }
    )


def handle_modified(change, target, base, indexes, facts, base_facts, proposals,
                    unresolved, no_proposal):
    """R01 declaration channel for modified files. Verdicts:
    - declarations identical �� no_proposal (comments/formatting/internal body);
      this verdict is channel-local and never silences the import channel;
    - entryPoint declaration gone �� RESPONSIBILITY_CHANGE without picking an
      unsupported replacement symbol (S06, DROP L10);
    - declaration change outside map domains �� unresolved."""
    path = change["path"]
    if not path.endswith(".py"):
        no_proposal.append({"paths": [path], "reason": "non-python change"})
        return
    owners = indexes["node_by_path"].get(path, [])
    target_entries = facts["files"].get(path)
    base_entries = base_facts["files"].get(path) if base_facts["available"] else None

    if base_entries is not None and target_entries is not None:
        if sorted(map(repr, base_entries)) == sorted(map(repr, target_entries)):
            no_proposal.append(
                {"paths": [path], "reason": "no declaration-level change (comments/formatting/internal body)"}
            )
            return
        if not owners:
            unresolved.append(
                {
                    "subject": path,
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [
                        diff_evidence(target, path, "modified"),
                        *fact_evidence(target, path, target_entries),
                    ],
                    "note": "�����仯�����ڵ�ͼ֤����֮��",
                }
            )
            return
        gone = sorted({e.get("name") for e in base_entries} - {e.get("name") for e in target_entries})
        touched_responsibility = False
        for owner in owners:
            func = indexes["entry_lookup"].get((owner, path))
            if func and any(g == func or g.rsplit(".", 1)[-1] == func for g in gone):
                touched_responsibility = True

codex
代码已覆盖 `name=` 关键字和混合来源两条路径。由于原测试会创建临时 Git 仓库，我会在内存中执行提交里的回归断言，并补查 `__import__(name=...)`、`from pkg.b import B` 和纯别名场景；这不等同于重跑真实 Git 集成测试。另发现范围内包含 `b9c2994` 的 P07 改动，按本轮限定不审查。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import ast, subprocess, types, unittest
from pathlib import Path
from unittest.mock import patch
from extensions.map_proposal import relations, gitio

def committed(path):
    return subprocess.check_output(['git','show','857e9d0:'+path]).decode('utf-8')
assert Path('extensions/map_proposal/relations.py').read_bytes() == subprocess.check_output(['git','show','857e9d0:extensions/map_proposal/relations.py'])
m=types.ModuleType('target_tests'); m.__file__=str(Path('tests/test_w3_relations.py').resolve())
exec(compile(committed('tests/test_w3_relations.py'),m.__file__,'exec'),m.__dict__)
class Cleanup:
    def cleanup(self): pass
def virtual_repo(base_files,target_files):
    return {'a'*40:base_files,'b'*40:target_files},'a'*40,'b'*40,Cleanup()
def read_blob(repo,revision,path):
    try: return repo[revision][path]
    except KeyError: raise gitio.DiffSignalError('missing')
names=['test_x02_changed_dynamic_keyword_target_is_not_silent','test_mixed_provenance_from_and_explicit_import_keeps_medium','test_adversarial_3_from_package_import_submodule']
with patch.object(m,'build_repo',virtual_repo), patch.object(gitio,'read_blob',read_blob), patch.object(gitio,'ls_tree_names',lambda repo,revision:set(repo[revision])):
    suite=unittest.TestSuite(m.RelationChannelTests(n) for n in names)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    tc=m.RelationChannelTests()
    for api in ['__import__','importlib.import_module']:
        for form in ['positional','keyword']:
            def source(name):
                arg=repr(name) if form=='positional' else 'name='+repr(name)
                return m.A_CLASS+'import importlib\\n'+api+'('+arg+')\\n'
            r=tc.run_engine({'pkg/a.py':source('pkg.c'),'pkg/b.py':m.B_CLASS},{'pkg/a.py':source('pkg.b'),'pkg/b.py':m.B_CLASS},m.two_node_map())
            assert not r['proposals']
            assert any(u['reason']=='HUMAN_REQUIRED' and any('dynamic import: '+api+':pkg.b' in e.get('detail','') for e in u['evidence']) for u in r['unresolved']),r
            print('PASS exact dynamic evidence:',api,form)
    for statement,expected in [('from pkg import b\\n', 'low'),('from pkg import b\\nimport pkg.b\\n','medium'),('import pkg.b\\nfrom pkg import b\\n','medium'),('from pkg import b\\nfrom pkg.b import B\\n','medium'),('from . import b\\nfrom .b import B\\n','medium')]:
        r=tc.run_engine({'pkg/a.py':m.A_CLASS,'pkg/b.py':m.B_CLASS},{'pkg/a.py':m.A_CLASS+statement,'pkg/b.py':m.B_CLASS},m.two_node_map())
        adds=[p for p in r['proposals'] if p['kind']=='RELATION_ADD']
        assert len(adds)==1 and adds[0]['confidence']==expected,(statement,r)
        assert any('__init__' in u for u in adds[0]['uncertainty']) == (expected=='low')
        print('PASS provenance:',repr(statement),expected)
    tc.doCleanups()
'@ | python -B -" in G:\jiagou\projectmind-c-convergence
 exited 1 in 456ms:
Traceback (most recent call last):
  File "<stdin>", line 8, in <module>
AssertionError

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import subprocess, types, unittest
from pathlib import Path
from unittest.mock import patch
from extensions.map_proposal import gitio

def committed(path):
    return subprocess.check_output(['git','show','857e9d0:'+path]).decode('utf-8')
for path in ['extensions/map_proposal/relations.py','tests/test_w3_relations.py']:
    assert Path(path).read_text(encoding='utf-8') == committed(path).replace('\\r\\n','\\n')
m=types.ModuleType('target_tests'); m.__file__=str(Path('tests/test_w3_relations.py').resolve())
exec(compile(committed('tests/test_w3_relations.py'),m.__file__,'exec'),m.__dict__)
class Cleanup:
    def cleanup(self): pass
def virtual_repo(base_files,target_files):
    return {'a'*40:base_files,'b'*40:target_files},'a'*40,'b'*40,Cleanup()
def read_blob(repo,revision,path):
    try: return repo[revision][path]
    except KeyError: raise gitio.DiffSignalError('missing')
names=['test_x02_changed_dynamic_keyword_target_is_not_silent','test_mixed_provenance_from_and_explicit_import_keeps_medium','test_adversarial_3_from_package_import_submodule']
with patch.object(m,'build_repo',virtual_repo), patch.object(gitio,'read_blob',read_blob), patch.object(gitio,'ls_tree_names',lambda repo,revision:set(repo[revision])):
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(m.RelationChannelTests(n) for n in names))
    assert result.wasSuccessful()
    tc=m.RelationChannelTests()
    for api in ['__import__','importlib.import_module']:
        for form in ['positional','keyword']:
            def source(name):
                arg=repr(name) if form=='positional' else 'name='+repr(name)
                return m.A_CLASS+'import importlib\\n'+api+'('+arg+')\\n'
            r=tc.run_engine({'pkg/a.py':source('pkg.c'),'pkg/b.py':m.B_CLASS},{'pkg/a.py':source('pkg.b'),'pkg/b.py':m.B_CLASS},m.two_node_map())
            assert not r['proposals']
            assert any(u['reason']=='HUMAN_REQUIRED' and ('dynamic import: '+api+':pkg.b') in str(u['evidence']) for u in r['unresolved']),r
            print('PASS exact dynamic evidence:',api,form)
    for statement,expected in [('from pkg import b\\n','low'),('from pkg import b\\nimport pkg.b\\n','medium'),('import pkg.b\\nfrom pkg import b\\n','medium'),('from pkg import b\\nfrom pkg.b import B\\n','medium'),('from . import b\\nfrom .b import B\\n','medium')]:
        r=tc.run_engine({'pkg/a.py':m.A_CLASS,'pkg/b.py':m.B_CLASS},{'pkg/a.py':m.A_CLASS+statement,'pkg/b.py':m.B_CLASS},m.two_node_map())
        adds=[p for p in r['proposals'] if p['kind']=='RELATION_ADD']
        assert len(adds)==1 and adds[0]['confidence']==expected,(statement,r)
        assert any('__init__' in u for u in adds[0]['uncertainty']) == (expected=='low')
        print('PASS provenance:',repr(statement),expected)
    tc.doCleanups()
'@ | python -B -" in G:\jiagou\projectmind-c-convergence
 succeeded in 504ms:
test_x02_changed_dynamic_keyword_target_is_not_silent (target_tests.RelationChannelTests.test_x02_changed_dynamic_keyword_target_is_not_silent) ... ok
test_mixed_provenance_from_and_explicit_import_keeps_medium (target_tests.RelationChannelTests.test_mixed_provenance_from_and_explicit_import_keeps_medium) ... ok
test_adversarial_3_from_package_import_submodule (target_tests.RelationChannelTests.test_adversarial_3_from_package_import_submodule) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.001s

OK
PASS exact dynamic evidence: __import__ positional
PASS exact dynamic evidence: __import__ keyword
PASS exact dynamic evidence: importlib.import_module positional
PASS exact dynamic evidence: importlib.import_module keyword
PASS provenance: 'from pkg import b\n' low
PASS provenance: 'from pkg import b\nimport pkg.b\n' medium
PASS provenance: 'import pkg.b\nfrom pkg import b\n' medium
PASS provenance: 'from pkg import b\nfrom pkg.b import B\n' medium
PASS provenance: 'from . import b\nfrom .b import B\n' medium

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import subprocess, types, unittest
from pathlib import Path
from unittest.mock import patch
from extensions.map_proposal import engine, gitio

def source(rev,path): return subprocess.check_output(['git','show',rev+':'+path]).decode('utf-8')
m=types.ModuleType('target_tests'); m.__file__=str(Path('tests/test_w3_relations.py').resolve())
exec(compile(source('857e9d0','tests/test_w3_relations.py'),m.__file__,'exec'),m.__dict__)
old=types.ModuleType('old_relations')
exec(compile(source('dda5246','extensions/map_proposal/relations.py'),'<dda5246 relations>','exec'),old.__dict__)
class Cleanup:
    def cleanup(self): pass
def virtual_repo(base,target): return {'a'*40:base,'b'*40:target},'a'*40,'b'*40,Cleanup()
with patch.object(m,'build_repo',virtual_repo),patch.object(gitio,'read_blob',lambda repo,rev,path:repo[rev][path]),patch.object(gitio,'ls_tree_names',lambda repo,rev:set(repo[rev])),patch.object(engine,'relations',old):
    for name in ['test_x02_changed_dynamic_keyword_target_is_not_silent','test_mixed_provenance_from_and_explicit_import_keeps_medium']:
        result=unittest.TestResult(); m.RelationChannelTests(name).run(result)
        assert len(result.failures)==1 and not result.errors,(name,result.errors)
        print('REGRESSION_CAUGHT against dda5246:',name)
'@ | python -B -
git status --short" in G:\jiagou\projectmind-c-convergence
 succeeded in 513ms:
REGRESSION_CAUGHT against dda5246: test_x02_changed_dynamic_keyword_target_is_not_silent
REGRESSION_CAUGHT against dda5246: test_mixed_provenance_from_and_explicit_import_keeps_medium
?? tests/acceptance_matrix.py

codex
两项新回归断言均通过；切换回 `dda5246` 的关系模块后，两项断言均失败，说明它们能捕获原问题。纯别名仍为 low，混合来源为 medium，两个动态导入 API 的关键字形式也输出了正确目标。审查同时发现一个较低严重度的问题：`_dynamic_tag` 会扫描所有位置参数，可能把第二个 `package` 参数误标为导入目标；它仍只生成 `HUMAN_REQUIRED`。
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import ast
from extensions.map_proposal import relations
for src in [\"importlib.import_module(module_name, 'pkg.c')\", \"importlib.import_module(module_name, 'pkg.b')\"]:
    print(src, '=>', sorted(relations._scan_imports(ast.parse(src))[1]))
'@ | python -B -" in G:\jiagou\projectmind-c-convergence
 succeeded in 322ms:
importlib.import_module(module_name, 'pkg.c') => ['importlib.import_module:pkg.c']
importlib.import_module(module_name, 'pkg.b') => ['importlib.import_module:pkg.b']

codex
**AUDIT_BASE_SHA..AUDIT_TARGET_SHA: `dda5246..857e9d0`**

- **HIGH — keyword dynamic targets: RESOLVED.** Both APIs recognize `name=` string targets; changed targets produce `HUMAN_REQUIRED`.
- **MEDIUM — mixed provenance: RESOLVED.** Explicit imports and ImportFrom prefixes preserve medium confidence; alias-only candidates remain low with named ambiguity.
- **LOW — remaining:** [`_dynamic_tag`](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:120) scans every positional argument. `importlib.import_module(module_name, 'pkg.b')` incorrectly tags the package argument as the target. This creates misleading evidence but remains `HUMAN_REQUIRED`. Restrict positional extraction to the first argument.

**FALSE_GREEN_RISK:** Both new committed guards passed with in-memory Git fixtures and failed against `dda5246`. Nine supplemental checks passed. Real Git integration, full-suite, and mutation runs were not repeated; prior results and optional integration skips remain verification limits.

**CONTRACT_REGRESSIONS:** No admission or confidence regression found within scope; the LOW evidence issue remains.

**SECURITY_FINDINGS:** None found within scope.

Read-only review; no files changed. Project Model impact: **NONE**. P07 commit `b9c2994` was outside this targeted review.

**VERDICT for `78c2751..857e9d0`: PASS_WITH_LIMITS**, carrying forward the supplied resolution of earlier findings without re-auditing them.
tokens used
47,501
**AUDIT_BASE_SHA..AUDIT_TARGET_SHA: `dda5246..857e9d0`**

- **HIGH — keyword dynamic targets: RESOLVED.** Both APIs recognize `name=` string targets; changed targets produce `HUMAN_REQUIRED`.
- **MEDIUM — mixed provenance: RESOLVED.** Explicit imports and ImportFrom prefixes preserve medium confidence; alias-only candidates remain low with named ambiguity.
- **LOW — remaining:** [`_dynamic_tag`](G:/jiagou/projectmind-c-convergence/extensions/map_proposal/relations.py:120) scans every positional argument. `importlib.import_module(module_name, 'pkg.b')` incorrectly tags the package argument as the target. This creates misleading evidence but remains `HUMAN_REQUIRED`. Restrict positional extraction to the first argument.

**FALSE_GREEN_RISK:** Both new committed guards passed with in-memory Git fixtures and failed against `dda5246`. Nine supplemental checks passed. Real Git integration, full-suite, and mutation runs were not repeated; prior results and optional integration skips remain verification limits.

**CONTRACT_REGRESSIONS:** No admission or confidence regression found within scope; the LOW evidence issue remains.

**SECURITY_FINDINGS:** None found within scope.

Read-only review; no files changed. Project Model impact: **NONE**. P07 commit `b9c2994` was outside this targeted review.

**VERDICT for `78c2751..857e9d0`: PASS_WITH_LIMITS**, carrying forward the supplied resolution of earlier findings without re-auditing them.
