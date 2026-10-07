ProjectMind 架构认知闭环 · BATCH-3 修复复审（BATCH-4，只读，逐条复验）

- package_id: BATCH-4
- target_sha: `803c6736d1ab01bee004a77c2d2b3b140b28cb12`（你的工作目录即该提交的只读副本，应为 CLEAN）
- 累计范围：`b75ad820e0d31e3dadf842b414f6950b5aa46102..803c6736`——上一轮工作台起点 → 本轮最终集成提交（已含 BATCH-2、BATCH-3 两批审查的全部修复）。
- 上一批审查结论：`receipts/BATCH-3/attempt-001/verdict.json`（CHANGES_REQUESTED，6 条）；原回复与证据随包提供：`evidence/BATCH-3-verdict.json`、`evidence/BATCH-3-reply.md`。

## 本批唯一目标

对上一批 6 条 finding **逐条**核验：修复是否真实存在、是否能通过你自己的复现推翻。不要采信描述；除这 6 条之外的既有能力（人审边界、版本身份、B/C 接通、前两批修复）应当保持：只报告**回归**。

### 逐条清单（finding → 修复位置 → 期望复验结果）

1. **A-01**（旧格式载体仍遮蔽 B 的真实分支编辑）
   - 位置：`archloop/backend_b.py` 反向投影：条件在 `branchFallbacks` 中但**填充值未知**（旧载体的纯条件字符串）时，一律以 **B 当前值**为准；填充值已知且与当前值相等（仍是我们写的占位）时才回用记录的 A 意图。
   - 期望：用 `a973d77` 的旧投影生成的真实旧格式载体（`branchFallbacks` 为纯条件列表）下，B 把目标改成 s3 后：反投影必须给出 `branchTargets[条件]=s3`，再投影不得恢复 s2，且对 B 当前图的差分不含改写该分支的 step 级操作。
2. **A-05**（显式 `coverage: null` 仍被当作缺省）
   - 位置：`archloop/backend_b.py` 的 `preview_review` 以 **`"coverage" not in request`** 判断“未提供”，显式 null/非对象/非列表一律 `VALIDATION_FAILED`；`archloop/service.py` 的 review_preview 只在调用方真的给了 coverage 时才转发该键。
   - 期望：`coverage: null` 被拒（不是默认覆盖、不产生发布授权）；**完全省略** coverage 仍走默认覆盖；`bad-list`、`["nodes"]` 等仍被拒。
3. **GEN-01**（新正则误排普通配置文件）
   - 位置：`archloop/context_pack.py`：改为“键名按组件判定”（`_key_name_is_secret`）：snake/kebab/camelCase 拆分后**最后一个组件**为凭据词（key/token/secret/password/passwd/credential），或任意组件属于 secret/password/credential 类；不再做子串匹配。
   - 期望：`{"monkey": "LongNonSensitiveAnimalName"}`、`service_name`、`token_cache` 之类**不被**排除；`api_key`/`apiKey`/`OPENAI_API_KEY`/`clientSecret`/`secret_key_base`/`GITHUB_TOKEN`/`KEY = "sk-…"` 仍被排除并记录原因；占位符（`your API key`）不误判。
4. **C-INCREMENTAL-01**（连续更新互相覆盖；仍返回不可应用操作）
   - 位置：`archloop/backend_c.py` 的 `_incremental_ops_to_a`：同一节点的多条变更**合并为一条** update（两个文件都保持降级）；仍被关系引用的节点**不产生**删除操作（改为 warnings）；派生 ID 冲突时**唯一化**并记 warning；所有产出的操作在**实际累积图上逐一验证**，不可应用的一律降级为 warnings。顺序为 新增 → 更新 → 删除。
   - 期望：a.py+b.py 两次更新后两条证据都停在 `unknown`；被边引用的节点删除 → 0 操作 + 1 警告；两个派生同 ID 的新增 → 两个唯一 ID 且都能应用；“修改且删除”同一节点这类自相矛盾输入 → 仍全部可应用（不可用者进 warnings）。
5. **G-02**（移走活锁仍允许两个持有者同时执行）
   - 位置：包内 `unattended/controller.py`：新增 `lease_held()` 围栏校验；`LeaseWatchdog` 在线程中轮询真实锁文件，租约一旦易主即**杀死正在执行的审计子进程**（判定 `LEASE_LOST`，包保持可重试）；`tick_audit` 在调用前先做围栏校验；`release_lock(lease=…)` 只释放**仍属于自己**的锁；`_run_child` 以可中断方式运行子进程。
   - 期望：模拟“回收者移走活租约、第三人取得新锁”后：被顶替的持有者必须**停止执行**（子进程被杀、`LEASE_LOST`、不与第三人并行完成工作）；释放不会删除他人的锁；正常死主过期锁回收、`selfcheck.json` 的 `lock_reclaim_cases` / `lease_fencing_cases` / `queue_concurrency_cases` 全部通过。
6. **ACCEPTANCE-01**（T21/T24 判据仍接受不足或不一致证据）
   - 位置：`archloop/acceptance.py`：`handover_tamper_verdict` 要求 `contentMatches is False` **且** `revisionMatches is True` **且** `mapIdMatches is True`（或 `EVIDENCE_MISMATCH` 拒绝）；`self_coverage_verdict` 要求：绑定工作区的 identity 版本是**完整 40/64 位 SHA**、`git cat-file -e <sha>^{commit}` 在**本仓库**成立、identity 版本 = coverage 版本 = 本仓库 HEAD、且 coverage 的 `trackedFiles`/`pythonFiles` **等于本仓库该提交的真实文件树计数**（运行器本地用 git 计算）。
   - 期望：`revisionMatches` 缺失/null/False 或 `mapIdMatches` False 时 T21 不得 PASS；`"HEAD"`、不存在的 SHA、identity 与 coverage 不一致、或文件数与真实树不符时 T24 不得 PASS；真实情形仍 PASS（提供方记录：`evidence/acceptance-a-side-batch3repair.json`，35 PASS / 2 NOT_RUN，T24：trackedFiles=248/pythonFiles=139 与本仓库一致）。

## 请真实执行

1. `git rev-parse HEAD`、`git status --porcelain`，确认与 target_sha 一致且 CLEAN。
2. 若沙箱允许临时目录，运行 `python -m unittest tests.test_archloop_a_batch3_fixes tests.test_archloop_a_batch2_fixes -v`；不允许则说明，并用内存复现/静态核对替代。
3. 抽查（至少覆盖）：`archloop/backend_b.py` 的两个载体分支与 coverage 判定、`archloop/context_pack.py` 的键名组件规则、`archloop/backend_c.py` 的合并/删除/唯一化/逐条验证、`archloop/acceptance.py` 的两个谓词、包内 `unattended/controller.py` 的围栏与看门狗（可与 `unattended/selfcheck.json` 对照）。
4. 明确指出：你未独立核验的内容（真实 AI、真实浏览器、跨设备、D 模块、发布事务极端中断等），以及**本轮修复之外**的回归（如发现）。

## 回复要求（结构化最终输出，与你被要求的输出 schema 一致）

- package_id: "BATCH-4"
- target_sha: 上述 40 位提交
- scope: 实际审查范围（列出你实际读/跑的内容）
- verdict: "PASS" 或 "CHANGES_REQUESTED"
- findings: 数组（PASS 时必须为空）；每项 {id, severity, summary, evidence}
- unverified: 数组
- notes: 实际执行的命令与结果摘要

不要修改任何文件。