# C_CONVERGENCE_PLAN

日期：2026-10-04（Asia/Hong_Kong）。本文件是实施方案，不是新的实现比较、代码变更或 readiness 复验。

**冻结结论：NEITHER_READY；CONFIDENCE = HIGH。** 本方案不改变该结论，不对 TEAM C 与 LOCAL C 排名。

目标：**TEAM C baseline + selected LOCAL implementation + shared regression suite**。TEAM C 开发者继续担任 C owner，负责设计决策、移植审查和最终交付。LOCAL 是按组件选用的实现来源；TEAM 缺失而 LOCAL 已符合共同契约的组件可以直接移植，无须为了保留原代码重写。现有实现均不能整体作为正确答案。

## 1. Frozen Heads

| 对象 | 冻结标识 | 用途 |
|---|---|---|
| TEAM C | `3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`；`feat/role-c-map-proposal`；[PR #35](https://github.com/LingweiXingzhi/projectmind-core/pull/35)，owner `bjtxcy` | C 的交付与治理 baseline |
| TEAM C fixed base | `7484d44ddeac3c054ca3ba68f92293d965bb615c` | 识别 TEAM C 自身改动 |
| LOCAL C | `5058c54aa52243c15b286a4922a362c48c941967`；`feat/map-proposal-mvp`；[PR #34](https://github.com/LingweiXingzhi/projectmind-core/pull/34) | 独立参考与选择性移植来源 |
| LOCAL C-only base | `f43dcaf85141a72265e14946c10fee627e3cc7be` | 排除 LOCAL 祖先中的 B、D、CA 交付，不视作团队已批准的集成基座 |
| 共同契约文档 | `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa` | 唯一产品契约来源 |
| B 对照接口 | PR #31 @ `80e091acefd278fda03e188a125147b0aa5eedc5` | 实际 Code Facts 消费边界 |
| CA 对照接口 | PR #29 @ `9ea23491d1849f21bad9f60c1c1ca8df55bb5936` | 实际 Context Pack validator / resolver 边界 |

PR 的 OPEN/Draft 状态仅是冻结报告中的历史观察，不据此推断今天的状态、交付或批准。未来实现需要的外部事实必须重新独立核验；本次没有刷新远端、重跑实现或更换 heads。

本方案读取的冻结证据：

| 文件 | SHA-256 |
|---|---|
| [PROJECTMIND_C_DUAL_IMPLEMENTATION_REVIEW.md](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/PROJECTMIND_C_DUAL_IMPLEMENTATION_REVIEW.md) | `1c3ce67f8b4bd404c8319362281a4e828b25945354655ec34f969dc4874b8f6c` |
| [dual_results.json](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/dual_results.json)（58 条原始记录） | `6a14d1a09affb8ffabf092debc7876a90dd4ee337df160c349e33374c2921483` |

下文源代码定位统一指向冻结归档，避免原 worktree 后续变更：

- TEAM_ROOT = `C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/team/LingweiXingzhi-projectmind-core-3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`。
- LOCAL_ROOT = `C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local`。
- T.extension = [TEAM extension.py](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/team/LingweiXingzhi-projectmind-core-3bd980ded7a9cc727c1f00c84cf3c2b89c574e40/extensions/map_proposal/extension.py)。
- L.model = [LOCAL model.py](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local/extensions/map_proposal/model.py)；L.facts = [facts_adapter.py](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local/extensions/map_proposal/facts_adapter.py)；L.ca = [ca_adapter.py](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local/extensions/map_proposal/ca_adapter.py)。
- L.diff = [diff_model.py](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local/extensions/map_proposal/diff_model.py)；L.engine = [engine.py](C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local/extensions/map_proposal/engine.py)。

行号与符号均对应上述冻结版本。所有 KEEP / PORT / REIMPLEMENT 建议均是未来工作，本次只交付这个 Markdown 文件。

## 2. Contract Baseline

规范依据是共同 C 产品契约及冻结报告 §11 的 **30 项 Common Acceptance Matrix（A01–A30）**。报告给出的两列历史状态不作为目标 oracle，也不用于评分。相关规范入口为 [C_PRODUCT_BOUNDARY.md](G:/jiagou/projectmind-validation-review/c-readiness/C_PRODUCT_BOUNDARY.md)、[C_INPUT_OUTPUT_CONTRACT_PROPOSAL.md](G:/jiagou/projectmind-validation-review/c-readiness/C_INPUT_OUTPUT_CONTRACT_PROPOSAL.md)、[C_ACCEPTANCE_PLAN.md](G:/jiagou/projectmind-validation-review/c-readiness/C_ACCEPTANCE_PLAN.md)、[C_B_CODEFACTS_USAGE.md](G:/jiagou/projectmind-validation-review/c-readiness/C_B_CODEFACTS_USAGE.md)、[C_CONTEXT_SAFETY_RULES.md](G:/jiagou/projectmind-validation-review/c-readiness/C_CONTEXT_SAFETY_RULES.md)及 [C_CONSUMABLE_INTERFACE.md](G:/jiagou/projectmind-validation-review/c-readiness/C_CONSUMABLE_INTERFACE.md)。

### 产品不变式

1. 输入是 pinned Git diff、B 声明事实、当前人工 Project Map、可选 CA；输出是 `proposals / unresolved / no_proposal / limits`，附请求与事实底座追踪信息。`UNKNOWN` 进入 unresolved，不进入强 proposal。
2. 六类候选为 `NODE_ADD / RELATION_ADD / RELATION_REMOVE_CANDIDATE / IMPLEMENTATION_LINK_CHANGE / NODE_REMOVE_CANDIDATE / RESPONSIBILITY_CHANGE`。每项均具有完整 proposal 字段、非空且可定位到 revision/path 的 evidence、confidence、uncertainty、`status=PROPOSED`、`human_required=true`。
3. C 不写正式地图，不建议 position，不自行 accept/reject，不仲裁 CA conflict，不复制 B 声明解析，不编辑 CA registry，不接管 D 的 worklog。职责、架构归属、关系含义属于 INFERENCE，声明、路径、diff 属于 FACT。
4. base/target 必须是完整 40/64 位小写 SHA。请求缺少 pin、使用 HEAD/短 SHA 均拒绝；不得从 snapshot 偷补。地图无版本身份，target SHA 本身不能证明地图适用于该版本。
5. A/caller 的 compare 是 changed_paths 的来源。Core 的 `baseRevision / targetRevision / changes[{code,path,oldPath?}]` 通过显式适配映射为 C 请求；C 不另建一套文件差异口径。按该范围只读 pinned patch/blob，不能从工作树补证据。
6. 当前地图按实际 Core `{note,nodes,edges}` 结构接收，非空 nodes 及 title/summary/entryPoint/position/evidence 等既有约束不能被测试替身放宽。输入保留 position，候选的 proposed_change 不包含 position。
7. B 的事实仅含 revision/files/skipped，以及声明 name/kind/line，不包含 import、签名、调用图或职责。所有目标事实来源均验证 revision 等于 target，包括安装 B 的返回值、同版本比较和空差异请求。必要的 base 声明证据仍由 B 在独立 pinned base 上收集并标明 base 角色，不由 C 解析声明。
8. changed 文件若 B skipped，输出 HUMAN_REQUIRED unresolved；该文件不得继续成为节点或关系强候选的事实基础。B 不可用时记录 limits，可运行安全的 diff↔map 阶段；需要 B 的新增节点进入 unresolved，不虚构 code_fact。
9. 依赖信号来自实际 pinned Git diff。允许用 base/target 的 import AST 验证信号及排除字符串/docstring，但不能借此重做 B 声明解析。声明未变不等于 import 未变。
10. Context Pack 先由真实 `validate_context_pack(pack, expected_revision=C 独立 pin)` 校验。失败整包弃用，显式 DEGRADED/limits 后允许无 pack 运行；“硬停止”指停止消费该 pack，不是必须终止整个 C 服务。这沿用冻结报告对规范冲突的处理。
11. CA 只读 current_by_scope；verified_fields 按字段判定。非现行分区、conflict/unavailable key 不进入 proposal context evidence。已验证结构和未密钥 digest 不证明外部真伪；revision 对应、PR 状态、contract shape、implementation 状态须独立 git/gh 核验。state、merged、draft 分别核对，核验不可用则 UNKNOWN，矛盾则以独立证据为准、记录 claim_id 与双方值、标记 pack 不再可信。
12. 相关 conflict 进入 unresolved HUMAN_REQUIRED；C 不选边。未覆盖不等于不存在，不解析 do_not_assume 中的数字。相同固定输入与固定独立观察产生相同输出，不嵌时间戳或随机值。
13. `base==target` 时先完成必需的输入/事实一致性校验，再返回零 proposal，并说明 map drift 不属于本次差异判断。人工已 REJECTED、同 subject/kind 且理由未变的候选遵循 F20 抑制规则；无交叉信号不制造人工任务。

### 收敛后的单一决策路径

请求/路径/pin 校验 → Core compare 适配 → B 与 CA 入口校验 → 独立收集声明变化、import 变化、地图路径映射与目标存在性 → 按候选来源统一检查 skipped、证据、冲突、CA 准入 → 四桶输出 → 兼容字段投影。

各信号通道独立运行；任何单一通道不能因为“声明没变”结束整个文件分析。结果发布只有一个出口，不能把两套引擎的结果做 union，也不能在未完成准入检查时向旧 candidates 字段写入候选。

## 3. Failure Matrix

以下 ROOT CAUSE 与历史行为取自冻结报告、dual_results.json 及报告已定位的代码；TARGET BEHAVIOR 是共同契约要求。组件编号对应后续 KEEP / PORT / REIMPLEMENT 条目。

### F01 — TEAM 缺核心 diff × map 判断

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | T.extension 134–186 遍历 B files 转 NODE_ADD；changed_paths/current_map 被读取但没有参与核心候选判断，也没有六类推断分支。 |
| TEAM BEHAVIOR | 对已覆盖、未变、注释/格式/helper/internal class 等文件继续建议节点；未实现关系、路径更新、职责和删除判断。 |
| LOCAL BEHAVIOR | 已有 diff/map 映射和多类 handler，但信号调度、模块选择及证据准入仍有缺口，不能整体移植 suggest。 |
| TARGET BEHAVIOR | 先按本次 diff 与 map 交叉确定候选类型；已覆盖职责不因新增内部声明变成新节点；无交叉信号返回无提案；六类各有正例。 |
| IMPLEMENTATION SOURCE | KEEP K01–K03；PORT P02/P03/P04/P07；REIMPLEMENT R01/R06。直接移植成熟 rename 核心，重建总调度，不保留 TEAM 全文件生成循环。 |
| TEST/ORACLE | A01、A04–A12、A17、A18；X19/X20；F18 无交叉信号。断言精确 kind/subject/受影响节点，而不是候选数大于零。 |
| MIGRATION RISK | HIGH：TEAM 内部候选生产方式改变；旧 status/candidates 只能从合规结果投影，旧弱测试可能需要更正。 |

### F02 — TEAM CA validation 不完整

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | T.extension 66–81 只比较 pack SHA、枚举冲突；没有真实 validator、current_by_scope 或字段级证据协议。 |
| TEAM BEHAVIOR | 同 SHA 的缺字段 pack 仍被接受；冲突虽进入 unresolved，相关候选未被完整阻断。 |
| LOCAL BEHAVIOR | L.ca 21–43 已有独立 pin + 真实 validate + 整包弃用降级；读取 current_by_scope。但后续 engine 的信任与关联策略不合规。 |
| TARGET BEHAVIOR | 先真实校验、后选取；坏包零 context_claim，可无包继续；合法 pack 保留 schema_version/project_revision/registry_hash；选取与证据准入分离。 |
| IMPLEMENTATION SOURCE | PORT P01 的载入/选择模块；REIMPLEMENT R04 的消费与准入；DROP T03，不重写已经成熟的 validator 调用。 |
| TEST/ORACLE | A20–A24；实际 CA validator 对坏包先证实 reject、对合法 fixture 先证实 pass，再断言 C 的降级/选择/诊断。 |
| MIGRATION RISK | MEDIUM（结构适配）/HIGH（消费边界）：严禁将 LOCAL engine 的自动 supplement 随适配器一起带入。 |

### F03 — LOCAL poisoned context 可进入 evidence

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | L.engine `_is_high_impact_claim` 使用 key/字段/文本黑名单；`_apply_context_claims` 将首条幸存 claim 附到首个 proposal。结构校验成功被错误当成足够准入条件。 |
| TEAM BEHAVIOR | 没有完备的 CA 准入；冻结 X17 没有该 supplement 行为，但也没有符合 R6 的独立核验与矛盾诊断。 |
| LOCAL BEHAVIOR | validator-pass 的中性 key、值为“PR 35 is CLOSED”的 X17 被作为 UNVERIFIED context_claim 附到候选；X05 的中性语义断言也能附入。 |
| TARGET BEHAVIOR | 未识别语义/无相关用途的自由文本不进入 proposal evidence；高影响事实独立核验后才能消费。UNKNOWN/UNVERIFIED 标记不能洗白毒化事实；冲突时不再使用该 pack 的 current claims 作证。 |
| IMPLEMENTATION SOURCE | REIMPLEMENT R04；只复用 P01 的真实校验和 P07 的追踪结构，DROP L01/L02。 |
| TEST/ORACLE | A25 + X05/X16/X17；合法 poison 先要求真实 validator PASS。使用固定 fixture PR 的独立真值，分别测 OPEN、CLOSED、merged、draft、核验不可用及矛盾，不依赖未来 live PR #35 状态。 |
| MIGRATION RISK | HIGH：误将安全修复做成更长关键词黑名单会再次绕过；默认不附加不具备明确用途的 claim，但必须保留 UNKNOWN/limits 诊断。 |

### F04 — LOCAL skipped 文件关系误报

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | L.engine 132–138 只在文件 handler 跳过 skipped；152–156 的 relation_paths 没有统一排除，之后仍读 patch 生成关系。 |
| TEAM BEHAVIOR | 对 skipped 源本身保守 unresolved；全树模式仍有无关节点噪声。X21 changed-only 未生成该源关系。 |
| LOCAL BEHAVIOR | X04/X21 真实 B skipped 源同时产生 unresolved 和 RELATION_ADD。 |
| TARGET BEHAVIOR | 一次建立候选事实可用性规则，所有 kind 和关系端点证据域共用；被 skipped 的变化源进入 HUMAN_REQUIRED，不发依赖该源的强候选。 |
| IMPLEMENTATION SOURCE | KEEP K04 的保守原则；REIMPLEMENT R02/R03 的统一准入；DROP L04，不能只给 relation_paths 打一次局部补丁。 |
| TEST/ORACLE | A13 + X04/X21；用真实 B 对语法坏文件产生 skipped。必须同时断言有 unresolved、四桶与兼容 candidates 中无相关强候选，正常文件仍能产生独立有效候选。 |
| MIGRATION RISK | HIGH：多个候选通道、rename 旧/新路径、关系两端都会引用路径；局部过滤容易漏掉间接证据。 |

### F05 — LOCAL 真实 import 漏报

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | `_handle_modified` 272–277 用声明列表相同标记 declaration_unchanged；relation_paths 排除这些文件，把“声明没有变化”错误当作“没有关系信号”。 |
| TEAM BEHAVIOR | 无核心 RELATION_ADD / REMOVE 推断。 |
| LOCAL BEHAVIOR | X01 class 后新增真实 import、X11 class 后删除最后 import 均空结果；X02 同类动态信号也缺应有 unresolved。 |
| TARGET BEHAVIOR | import 通道独立于声明通道，新增/移除真实跨节点 import 均能识别；动态/不可解析依赖进入 UNKNOWN，不凭猜测建关系。 |
| IMPLEMENTATION SOURCE | REIMPLEMENT R01/R03；PORT P05 的 Git 只读与 import AST 小组件；DROP L03。 |
| TEST/ORACLE | A02/A03；X01/X11 必须各有预期关系 kind 与精确端点；X02 必须有依赖信号不足的 unresolved。加入 import 位于 class 前后两组，保持声明不变。 |
| MIGRATION RISK | HIGH：取消早退会暴露文本误报，必须与 F06 一起完成，不能单独放开 regex 路径。 |

### F06 — docstring 假 import 与关系删除证明不完整

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | L.diff `import_signals` 48 起直接扫描 patch 文本；移除验证只覆盖单个源文件，没有证明整个节点 evidence 域到目标域的 import 消失。 |
| TEAM BEHAVIOR | 不判断关系，docstring 变化仍可能因全树生成产生节点噪声。 |
| LOCAL BEHAVIOR | X03/X12 的 docstring import 文本误生成关系；X13 的简单 import 写法 churn 已有正确无关系变化行为，可复用该语义原则。 |
| TARGET BEHAVIOR | diff 为信号来源、AST 确认是实际 import；同一规范化目标的写法变换不产生关系变化。删除既有关系前，验证两个 map evidence 域之间相关静态 import 全部消失；读取/解析失败不能等同零 import。 |
| IMPLEMENTATION SOURCE | PORT P05 的 AST 遍历与模块解析基础；REIMPLEMENT R03 的信号归一化、跨文件聚合和缺证降级；DROP L05 的 regex 直接作证。 |
| TEST/ORACLE | A03/A11；X03/X12/X13；扩展“一个源删 import、另一个源仍保留”不得建议移除；SyntaxError/读取失败应 UNKNOWN。 |
| MIGRATION RISK | HIGH：import alias、包入口、相对 import 和多 evidence 文件不能以单行计数等同架构关系。未支持形式须明确 unresolved。 |

### F07 — revision / 输入 / 路径 gate 缺口

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | TEAM 隐式 HEAD fallback 与弱形状检查；LOCAL 同 revision 早退在 B 校验之前，安装 B 返回值未再次钉 revision，normalize 在错误边界之外；map evidence 路径校验没有统一覆盖。 |
| TEAM BEHAVIOR | HEAD/不合法请求可进入生成；facts 列表形状错误可能成为 Host 500；缺完整路径防护。普通 B mismatch 已拒绝。 |
| LOCAL BEHAVIOR | 普通 pin/path/mismatch 已处理；X06 绕过 B mismatch，安装 B mismatch/形状异常仍有缺口。 |
| TARGET BEHAVIOR | 每条执行路径先验证请求与目标事实一致性；map、changed、old_path、facts、entryPoint 的路径统一约束；输入错误受控拒绝，依赖异常明确限额/降级，不能变成可用事实。 |
| IMPLEMENTATION SOURCE | PORT P02 的 SHA/path 原语；REIMPLEMENT R02/R06/R07；DROP T02/L06/L07。B shape 防御只检查安全消费所需结构，不绑定 CA 陈旧 contract claim 的完整字段表。 |
| TEST/ORACLE | A14/A27/A28；X06；额外 supplied/installed B × 正常/同版本/空 changes × mismatch/异常 shape；合法 40/64 SHA 正例。 |
| MIGRATION RISK | MEDIUM–HIGH：旧 demo 缺 pin 会变成正确的受控拒绝；不可用隐式补值换取旧测试绿。 |

### F08 — scope conflict / stale / unavailable 诊断不完整

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | TEAM 无完整分区协议；LOCAL conflict 路由主要查 value 文本，忽略结构 scope；有效 unavailable/stale 排除之后缺显式消费者诊断。 |
| TEAM BEHAVIOR | 可列 conflict，却未可靠阻断关联候选；没有 multi-scope / verified_fields 消费协议。 |
| LOCAL BEHAVIOR | A21 by_scope 选择可用；X14 文本冲突有效、X15 避免子串误伤；X18 仅 scope 指向变化文件仍发节点；A23 排除正确但缺 limits/UNKNOWN。 |
| TARGET BEHAVIOR | 按 key、scope、明确路径/节点关联判定相关冲突；相关候选 unresolved HUMAN_REQUIRED，冲突 key 永不入证据。无关 node-api 不阻断 node-a。合法 unavailable 不伪装坏包，相关事实 UNKNOWN/limits；非现行 claim 全部排除。 |
| IMPLEMENTATION SOURCE | PORT P01/P08；REIMPLEMENT R04；DROP L08 的 text-only 路由与静默诊断。 |
| TEST/ORACLE | A19–A23 + X14/X15/X18；合法多 scope、scope-only conflict 和合法 unavailable fixture 均先 validator PASS。 |
| MIGRATION RISK | HIGH：过宽关联会阻断所有候选，过窄关联会继续泄漏；必须用相关与无关成对正反例。 |

### F09 — map stale 检测局限于本次 removed

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | TEAM 不读 map 判断；LOCAL `_handle_removals` 只检查本轮 removed 集合，且与 B available 耦合。 |
| TEAM BEHAVIOR | A16-valid-map 中已过期 node 未产生所需候选/诊断。 |
| LOCAL BEHAVIOR | A05 本轮删除可产生候选；A16-valid-map 的 gone.py 在 base/target 均不存在时漏报。 |
| TARGET BEHAVIOR | 对 node 的全部有效 evidence 路径做 pinned target 存在性判断；全部明确不存在才低置信度 NODE_REMOVE_CANDIDATE，并说明 map stale。任一路径仍存在则不删；base==target 仍遵守零 proposal 的 F15。 |
| IMPLEMENTATION SOURCE | PORT P04 当前删除候选结构；REIMPLEMENT R05，独立于 B 声明可用性。 |
| TEST/ORACLE | A05/A16-valid-map；早于 base 删除、部分 evidence 保留、Git 读取失败、same-revision map drift 四组。不可虚构“base 曾存在”。 |
| MIGRATION RISK | MEDIUM：扩大检查范围可能误把读取失败当不存在；需正面证实缺失，避免不可逆语气。 |

### F10 — ID / 主声明选择 / evidence 回放

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | LOCAL 新 node 用 basename，proposal 用顺序编号，首个 class 被当主入口，fact evidence 截前三条；TEAM ID 简化路径、fact evidence 缺结构化 path/name/line。LOCAL context evidence 缺 pack_revision 等回放字段。 |
| TEAM BEHAVIOR | 候选缺可靠 diff/map 依据和结构化声明定位，不能把“地图缺节点”当未验证事实。 |
| LOCAL BEHAVIOR | X09 两个 service.py 同 node_id；R02 以 CodeFactsError 作入口；R04 主 class 可能不在前三条证据；context 引用回放不完整。 |
| TARGET BEHAVIOR | 确定性且不冲突的 ID；B 声明不是入口/职责真值，无法支持选择时 unresolved 或明确低置信度候选，不因首个 class 猜主入口。引用实际所选声明，不截掉关键证据；context_claim 带 claim_id/key/scope/pack_revision/source 定位。 |
| IMPLEMENTATION SOURCE | PORT P02/P07；REIMPLEMENT R01/R06；DROP T05/L09/L10。ID 采用契约允许的短 hash 形式，是实现选择，不新增产品目标。 |
| TEST/ORACLE | A01/A06/A18/A26 + X08/X09；重复 basename、与现存 map id 冲突、候选输入顺序变化、实际主声明回放及 F20 否决重放。function-only 不强行判为 NODE_ADD，但不得假定没有 class 就不是模块。 |
| MIGRATION RISK | MEDIUM–HIGH：D/人工引用可能依赖旧 proposal_id；必须声明旧 ID 迁移关系，不能自动接受旧候选。 |

### F11 — 输出兼容与 mode 诚实性

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | TEAM 旧 envelope 与 canonical 四桶混存；125–129 仅凭 mode/API key 宣称 ai_candidate；LOCAL 的模块化内部模型不能直接当 TEAM 对外替换。 |
| TEAM BEHAVIOR | X07 占位 key 即输出 ai_candidate，实际无模型执行；旧 candidates 流程能够绕开新候选语义。 |
| LOCAL BEHAVIOR | 已有较完整 canonical 输出，但不能据此整体覆盖 TEAM handler、前端/DevKit 或 owner 契约。 |
| TARGET BEHAVIOR | canonical 结果唯一；旧字段是兼容投影，不独立生成；生成方式与 proposal lifecycle 分开，规则生成不得宣称 AI。缺合法输入明确拒绝，不伪造 pin 或降级产假节点。 |
| IMPLEMENTATION SOURCE | KEEP K01/K03；REIMPLEMENT R07；DROP T04。 |
| TEST/ORACLE | X07 + A26/A27；Host route/legacy smoke 对照 canonical 子集；旧缺 pin fixture 应受控拒绝而非继续生成。 |
| MIGRATION RISK | MEDIUM：保留字段不等于保证所有旧弱断言成立，需要在同一集成 PR 明确消费者迁移。 |

### F12 — 共享 Host runtime SystemExit 隔离未完成

| 字段 | 内容 |
|---|---|
| ROOT CAUSE | 共享 ExtensionHost load 捕获 Exception + SystemExit，runtime run 只捕获 Exception；此问题位于共同 Core 基座。 |
| TEAM BEHAVIOR | 普通异常隔离有效，runtime SystemExit 仍逃出 Host。 |
| LOCAL BEHAVIOR | 同一共享基座、同一缺口；不是可从 LOCAL C 移植解决的组件。 |
| TARGET BEHAVIOR | A30 中单扩展普通异常与 runtime SystemExit 均不阻止其余路由继续；由 A/Core owner 修复共享 Host 或提供满足该 oracle 的隔离执行机制。C 可控制自身 B/CA 依赖边界，但不能代表 Host 全局隔离已完成。 |
| IMPLEMENTATION SOURCE | SHARED_REGRESSION_TESTS S30；A/Core 独立依赖任务。C integration diff 不修改 extension_host.py；不整合两份相同缺陷代码。 |
| TEST/ORACLE | A30：七扩展集成，故障扩展普通 Exception 与 SystemExit 分别注入，其余 route 仍可调用；不能只测 load 或 C 内部 catch。 |
| MIGRATION RISK | HIGH（外部阻塞）：此项未完成时整体仍不能报 30/30 PASS；不以“历史问题”豁免。 |

## 4. Keep From TEAM

**分类：KEEP_FROM_TEAM。** 保留的是 owner、合规边界与对外接入，不是保留全部原函数体。

| ID | 保留对象 / 来源 | 收敛动作 | 证明 |
|---|---|---|---|
| K01 | 正式 C owner、扩展标识、ExtensionHost 接入与 handler seam；T.extension `handle` 21 起 | TEAM 负责交付；沿用已注册路由和标准库基础，不引入第二个 map_proposal 注册或共享请求可变状态。内部委托单一新调度器。 | A30 route smoke；请求间状态不串扰 |
| K02 | 候选为 PROPOSED/human_required；不写 map、不输出 position 的边界，T.extension 184–185 等 | 提升为所有 kind、所有输出路径的统一发布不变式。 | A01–A06、A29；非法候选不能进入兼容字段 |
| K03 | `_make_response` 202–226 的旧 status/revision/candidates/note 兼容外壳 | 从已经校验的四桶结果生成投影；旧 candidates 仅投影其 schema 能表达的合规 NODE_ADD，其他 kind 在 canonical proposals 中保留。revision 为完整 target。旧 summary status 与每项 PROPOSED 生命周期分别定义。 | A26/A27、X07；旧 candidates 不比 canonical 多出任何未准入候选 |
| K04 | skipped 变化源保守进入 unresolved 的行为，T.extension 87–95 | 作为统一候选准入原则保留，不保留独立 TEAM B 循环；只报告相关 changed skipped，不制造全树无关诊断。 | A13、X04/X21 与正常文件正例 |

不得为了让原 DevKit 继续出现固定数量 candidates，保留隐式 HEAD、全树 NODE_ADD 或缺 pin 请求的旧成功行为。

## 5. Port From LOCAL

**分类：PORT_FROM_LOCAL。** “直接移植”指冻结组件的合规职责可直接复用，仅调整 import/调用边界；不意味着未修复其周边缺陷也可发布。移植 manifest 应记录 source SHA、符号、修改范围和 oracle。

| ID | 来源与最小单元 | 移植方式 | 允许保留的能力 / 必要边界 |
|---|---|---|---|
| P01 | L.ca `load_context` 21–67 的 pin/真实 validate/整包弃用/current_by_scope 选择 | **直接移植核心适配模块**，补 RECORD/诊断 | TEAM 没有该协议，无须重造。保留合法 pack 元数据；补 scope/conflict/unavailable 诊断与完整回链。`verified_fields` 不得只取第一证据引用就推广整行。不得带入 L.engine supplement/trust policy。 |
| P02 | L.model `SHA_PATTERN`、`validate_path`、`parse_entry_point`；L.engine 的 node_by_path / entry_lookup | **直接移植原语与索引核心**，扩大调用覆盖 | 复用完整 SHA、路径约束、精确 map owner 索引。统一校验 map evidence 等所有来源路径；请求/实际 Core map schema 的适配由 R06 完成，不接受空-map 假 fixture。 |
| P03 | L.engine `_handle_renamed` 183 起 | **直接移植 rename/move 核心** | old@base 与 new@target 证据、受影响 node、multiple owners 降置信度/uncertainty。发布前接统一 skipped/conflict gate，不因 rename 建新节点。 |
| P04 | L.engine `_handle_removals` 321 起的本轮全部 evidence 被删除证明与候选 payload | **选取合规子逻辑移植** | 保留 A05 已符合契约的当前删除行为；移除不必要的 B availability 门槛，补 R05 的早于 base 删除检测，不把完整函数原样复制当完成。 |
| P05 | L.diff `_git` 22 起、`resolve_module` 103 起、`static_import_count` 的 import AST 遍历核心 | **直接复用只读 Git / 有界模块解析原语；调整 AST 结果模型** | 保留环境清理、pinned blob、no-lazy-fetch/禁止 ext diff、超时边界。AST 仅验证 import；SyntaxError 不再返回可当“零”的证明。绝对模块路径解析可复用；未支持相对/动态形式明确 UNKNOWN。 |
| P06 | L.engine prior_decisions 431 起的 REJECT 抑制流程 | **移植隔离的抑制/limits 结构，核对适用条件** | 遵守 F20 同 subject/kind 且理由未变；证据/理由实质变化时允许重新待审，不永久封禁，也不由 C 改人工状态。 |
| P07 | L.model `make_evidence` / `make_proposal` 的字段骨架；L.engine 既有 git/map/fact evidence 组装 | **移植结构，改回放与身份细节** | 复用六 kind payload、confidence/uncertainty/status/human_required 模板及 FACT/INFERENCE 分离；补结构化 path/name/line、完整 CA 回链与 R06 ID。只复制与候选直接相关证据，不复制 first-three 截断与 first-class 入口推断。 |
| P08 | L.engine `_mentions` 57 起的词边界匹配、确定性排序等小组件 | **直接移植小组件，限定用途** | 防止 node-a / node-api 子串误伤，可用于诊断辅助；不是 scope/关系归属的唯一判断。 |
| P09 | LOCAL / frozen dual fixture 的有效构造与标准正例 | **迁移为共享测试输入** | 不迁移旧错误输出作 golden，不迁移弱负断言或无效 CA fixture。标准 rename、当前删除、基本 entryPoint 变化正例可直接复用输入与共同契约预期。 |

不整体移植 L.engine.suggest、L.diff.import_signals 或 L.facts.load_code_facts。NODE_ADD 中合规的 diff/B/map 证据组装可以复用，但“首个 class = 主模块入口”的策略必须重新制定。

## 6. Reimplement

**分类：REIMPLEMENT。** 下列重建由 TEAM C owner 实施；均可使用 §5 的小组件，不要求从零写每一行。

| ID | 重建职责 | 必须完成的行为 | 依赖 / oracle |
|---|---|---|---|
| R01 | diff × map 调度与候选判断 | 按 A compare 的真实变化和 map 覆盖决定 kind；独立运行声明/import/map 通道，最后才判断 no_proposal。全树 B 和包含必要事实的 changed-only B 不得造成不同的无关 NODE_ADD。新增 class/helper 不证明职责新增；声明入口不明确时低置信度明确 uncertainty 或 unresolved。 | K01、P02/P03/P07；A01–A12/A17/A18，F18 |
| R02 | B 适配与统一事实可用性 gate | supplied/installed 两条来源返回后都查 target equality，早退之前执行；normalize 处于受控错误边界。调用实际 B，按必要 target 存在路径收集，不能把 removed 路径传给会整包失败的 collector；必要 base 事实单独 pinned。区分 unavailable、skipped、无条目、错误 shape；将 skipped 约束覆盖每个候选证据域与关系端点。 | P02；A13–A15/A27，X04/X06/X21 |
| R03 | 独立 import 关系分析 | 从 pinned patch 找变化事件，base/target import AST 验证实际语句；规范化同目标 import/churn，映射两端已有 node evidence 域，避免 alias 写法噪声。仅对已存在 map edge 且跨域 import 全部消失给移除候选。动态/相对/解析或读取失败若无足够证明则 UNKNOWN；不解析 B 声明。 | P02/P05；A02/A03/A11，X01/X02/X03/X11/X12/X13；跨文件残留正反例 |
| R04 | CA evidence 准入、独立核验与 conflict 路由 | 真 validator 后使用有明确消费用途的 claim/字段；未知语义自由文本进入诊断，不随意附入 evidence。按每条 evidence 的 source 与 verified_fields 验证字段支持范围；高影响事实必须有独立 git/gh 观察，不能仅靠 freshness/字段名/关键词。按结构 key/scope 和精确 path/node 关联判冲突，相关候选转 unresolved，不选边。核验矛盾记录 claim_id/双方值并令 pack 不再作证；不可核验 UNKNOWN；合法 unavailable/stale 明确 limits，不假称 validation 失败。 | P01/P08；A19–A25，X05/X14–X18 |
| R05 | stale map 目标存在性判定 | 使用 pinned target Git tree/blob 的确定存在性检查，检查全部有效 evidence 路径；本轮 removed 只是其中一种来源。路径读取异常不得当不存在。全部确认缺失给低置信度 removal candidate；部分保留不删；same-revision 先 gate 后零 proposal。 | P04/P05；A05/A16，F15 |
| R06 | canonical 请求/输出、ID 与证据回放 | Core compare 显式适配；实际 Core map shape 与所有来源路径校验。proposal ID 用 target、kind、规范化 subject/payload 的稳定短 hash；node ID 纳入完整 repo-relative path/稳定 hash 并检查现存 map ID，避免 basename/路径压缩碰撞。code_fact 引 actual selected name/kind/line/path/revision，CA 引用含 pack_revision 等回链；schema/project_revision/registry_hash 按消费协议记录。所有桶可追踪，不将时间戳/digest再生成作为验证。 | P02/P07；A01/A06/A18/A26–A29，X09，F20 |
| R07 | 兼容 response / mode / 错误边界 | TEAM handler 仅发布 canonical 结果及其兼容投影。规则方法如实标识；无真实模型运行不得标 ai_candidate。用户输入错误受控拒绝，依赖失败按契约显式 limits/降级或拒绝，未预期错误不暴露 secret。旧缺 pin 请求不偷补 SHA。 | K01/K03；X07、A26/A27/A30 的 C 内部边界 |

关系“移除”的证明范围是 map 节点 evidence 域，不能以某一个文件的 import 数归零替代。CA conflict 约束作用于所有六种候选，不仅 NODE_ADD。运行时未知语义可进入诊断，但不能靠“UNVERIFIED”字样进入 proposal evidence 并支撑事实断言。

## 7. Must Not Combine

### DROP_FROM_TEAM

| ID | 删除/替换行为 | 原因 / 替代 |
|---|---|---|
| T01 | B 全文件转 NODE_ADD 与未经 map 检查的“地图缺少节点”断言 | 缺 diff × map 核心，改为 R01 |
| T02 | 缺 pin 时自动 snapshot HEAD / 接受短 SHA 的生成路径 | 破坏可回放契约，改 R02/R06 |
| T03 | 仅 pack revision 相等即接受，以及列 conflict 后仍保留关联候选 | 换 P01 + R04；不保留第二套弱 CA 分支 |
| T04 | 凭 API key/env/mode 声称 ai_candidate | 改 R07 的真实生成方式记录 |
| T05 | 无结构化 path/name/line 的 code_fact、顺序/压缩路径 ID 与独立旧 candidates 生成 | 改 R06/K03；不能借旧 envelope 绕过 gate |
| T06 | 对全树非 changed facts/skipped 制造节点或人工处理噪声 | 仅相关变化进入候选/诊断；独立有效事实仍保留 |

### DROP_FROM_LOCAL

| ID | 删除/替换行为 | 原因 / 替代 |
|---|---|---|
| L01 | key/字段/文本黑名单充当高影响事实验证 | 无法抵抗相干伪造，改 R04 typed consumption + independent fallback |
| L02 | 第一个幸存 claim 自动附到第一个 proposal | 无因果相关性、可注入；每项 evidence 明确用途与来源 |
| L03 | declaration_unchanged 排除关系分析/对文件全局早退 | 漏真实新增/删除 import，改 R01/R03 |
| L04 | skipped 仅在文件 handler 过滤，而 relation 通道继续 | 改 R02 的统一可用性 gate |
| L05 | patch regex 单独证明 import；解析失败当零；单源 import 归零当关系消失 | 改 R03；regex 可保留为候选信号提取，不能作最终事实证明 |
| L06 | same-revision 在 B 校验前成功返回、安装 B 返回值不查 revision | 改 R02；所有路径必经 gate |
| L07 | normalize 异常泄漏、无视 wanted_paths 的全树 B 收集、map evidence 路径不统一验证 | 改 R02/R06；保留实际 B 合约容错，不硬编码旧 CA 字段表 |
| L08 | conflict 只匹配 value 文本、忽略 scope，以及合法 unavailable/stale 静默排除 | 改 R04 结构关联与显式诊断 |
| L09 | basename node ID、顺序 ID 依赖与关键 fact evidence 截前三条 | 改 R06；身份稳定与关键证据不可截断 |
| L10 | 首个 class/首个替代声明自动当职责或 entryPoint；无 class 就默认不是模块 | 改 R01；保留有证据的候选组装，不继承职责猜测规则 |
| L11 | 只按本轮 removed 发现 stale map，且依赖 B available | 改 R05；保留 P04 中符合 A05 的子逻辑 |
| L12 | 旧自测 C_A23 的无效 unavailable fixture、只检查“无 context_claim”即通过的弱断言 | 用真实 validator-pass 合法 fixture 与正面状态/诊断断言替换 |

同一文件可有 PORT 与 DROP 条目，边界以符号和职责为准。禁止整体合并 PR #34、整包复制 LOCAL C 或将其 B/CA/D 祖先当 C 交付；禁止两个 map_proposal 注册、两个候选引擎 union、两套 CA validator 策略或两套 diff 文件口径。不得把 pack digest 当真伪认证，不把 demo map 视为获批架构，不把候选自动应用到正式地图。

## 8. Unified Regression Suite

**分类：SHARED_REGRESSION_TESTS。** 建议未来由 TEAM owner 维护同一套 contract fixtures，A/B/CA owner 审查各自边界；本次不创建测试代码、不运行实现。

### 30 项共同验收目标

以下 S01–S30 一一对应冻结 Common Acceptance Matrix A01–A30，目标全部为 PASS。这里仅列未来 oracle，不复述两份实现的胜负或历史分数。

| 测试 ID | Common ID / 场景 | 必须断言的目标行为 | 输入来源 / 变体 |
|---|---|---|---|
| S01 | A01 real NODE_ADD | 新模块无 map 覆盖且有 B 声明：恰好预期节点，git_diff + 可回放 code_fact + map 判断；全树/changed-only 不多生无关节点；PROPOSED/human_required。 | A01、X19；新增函数型模块不凭 class 门槛定案 |
| S02 | A02 real RELATION_ADD | 新增实际跨域 import：预期 from/to 的 RELATION_ADD，至少精确源 diff 与两端 map 证据；声明没变仍触发。 | A02、X01；class 前/后 import |
| S03 | A03 relation removal | 最后跨域 import 消失：对应既有 edge 的 REMOVE_CANDIDATE；其他 evidence 源仍 import 不移除；churn 不移除。 | A03、X11/X13；跨文件剩余 import |
| S04 | A04 implementation link | rename/move：对应 node 路径更新，old@base/new@target，不 NODE_ADD。 | A04；移动子目录变体 |
| S05 | A05 node removal | node 全 evidence 明确从 target 消失：低置信度删除候选；任一路径保留则无删除候选。 | A05；多 evidence 部分保留 |
| S06 | A06 responsibility change | entryPoint 声明改名/消失：对应 node 的责任或实现链接候选，声明证据由 B 给出；不选无依据的首个替代符号。 | A06；多声明歧义 |
| S07 | A07 comment only | 零强 proposal，明确 comments_only 或等价原因；不出现无关人工任务。 | A07、X20 |
| S08 | A08 formatting only | 零 proposal，格式变化原因；不能因行号/引号漂移制造新职责。 | A08 |
| S09 | A09 helper only | 已有职责加 helper 不 NODE_ADD；无其他交叉信号时无强 proposal。 | A09、F10 |
| S10 | A10 internal class only | 已有职责加内部 class 不 NODE_ADD；必要提示不得宣称新职责事实。 | A10、F9 |
| S11 | A11 docstring only | 仅 docstring（含 import 文本）零关系/节点强 proposal；有其他声明变化也不能把字符串当 import。 | A11、X03/X12 |
| S12 | A12 test noise | 仅 test/generated 噪声无业务架构候选；不得因已知测试动态加载例行制造人工 unknown。若确与现有 map 交叉，按实际证据处理，不能把所有 test 永久全禁。 | A12；R02/R05 的噪声输入 |
| S13 | A13 B skipped | 真实 skipped changed 源有 HUMAN_REQUIRED；任何通道、兼容 candidates 均无依赖该源的强节点/关系候选；正常源仍工作。 | A13、X04/X21 |
| S14 | A14 B mismatch | supplied/installed B mismatch 一律受控拒绝；同 revision、空 changes 不绕过。 | A14、X06；安装 B 注入 mismatch |
| S15 | A15 B unavailable | 明确 limits/DEGRADED；安全 diff↔map 分支仍运行；需 B 的新模块 unresolved、零虚构 code_fact。 | A15；可独立证明 rename 的正例 |
| S16 | A16 stale map | 早于 base 删除、target 全 evidence 缺失仍有 stale removal candidate；读取未知不当缺失。base==target 则零 proposal + map drift limit。 | **A16-valid-map**；F11/F15 |
| S17 | A17 ambiguous mapping | 多 map owner：低/中置信度并列 multiple candidate nodes 或 unresolved；不武断单选。 | A17、多 owner rename |
| S18 | A18 missing evidence | 新文件但所需 facts/diff 证据不足：unresolved UNKNOWN、零强候选；B 没条目不等同架构不存在。 | A18；无声明/缺关键证据 |
| S19 | A19 CA conflict | relevant key/scope conflict 不入任何 proposal evidence；相关候选 HUMAN_REQUIRED；精确无关节点仍有其有效候选。 | A19、X14/X15/X18 |
| S20 | A20 stale claim | validated stale 与其他非现行分区不进入 context_claim；相关消费需求有 limits/UNKNOWN。 | A20；stale/proposal/research/history 分区 |
| S21 | A21 multi-scope | 真实合法 pack 的同 key 多 scope 均进入选择层；按相关用途分别消费，不读 current 投影、不随便加到首项。 | A21；选择层正面计数与两 scope 关联测试 |
| S22 | A22 verified_fields | 支持字段与无支持字段分开；后者标 UNVERIFIED/诊断且不能作事实支撑；行 freshness 不升级整值。 | A22；多 evidence ref、字段部分覆盖 |
| S23 | A23 unavailable | 合法 unavailable/stale fixture 先 validator PASS；C 不将其伪作坏包 DEGRADED；相关值排除且明确 UNKNOWN/limits。 | dual A23；替换旧 C_A23 自测 |
| S24 | A24 invalid pack | 真实 validator 拒绝：整个 pack 不消费、零 context_claim、显式 DEGRADED；独立有效 diff/B/map 候选仍可存在。 | A24；同 SHA 缺字段/坏回链/错 revision |
| S25 | A25 coherent poison | 结构与 digest 合法的 poison 不进入 evidence/rationale；高影响事实有独立真值或 UNKNOWN；矛盾记录 claim_id/双方值，pack 不再可信。 | A25、X05/X16/X17；中性 key/自由文本、核验不可用 |
| S26 | A26 determinism | 固定输入与固定外部观察重复字节一致；ID 不依赖偶然遍历顺序，不携带时间戳/随机数。 | A26/A26-repeat；X09；候选排序变体 |
| S27 | A27 malformed input | HEAD/短 SHA/错 facts shape/错 map shape/缺字段受控拒绝；安装 B 异常 shape 不崩溃、不误当 available。 | A27 有效子例；valid-context malformed_payload_map |
| S28 | A28 path abuse | changed/old_path/map evidence/facts/entryPoint 全来源路径约束，拒绝越界/绝对路径/不安全输入；不读工作树或 repo 外补证。 | A28；追加 map evidence 与 rename 双侧路径 |
| S29 | A29 no map write | 请求前后正式地图及 source fixture 文件 hash 不变；没有 save/apply/accept 或 position proposed_change。 | 冻结各条 no_map_write 字段 + 未来独立 hash 断言 |
| S30 | A30 Host isolation | 七扩展可加载；普通异常与 runtime SystemExit 均不阻断其他路由。C 边界与共享 Host 分别测试，不以 load catch 替代 runtime。 | 冻结 Host 场景；**依赖 A/Core 修复后才能 PASS** |

### Oracle 与 fixture 纪律

- 原始记录中的 `request / repo / input_sha256` 可用于恢复输入，`results / assertions / summary` 是冻结观察，不能复制为 expected output。每个 migrated fixture 保留 source record ID/hash，并记录从哪个契约条款推导 oracle。
- A01–A06 正例同时检查 kind、subject、map node/edge、实际证据、status/human_required；“proposals 非空”不够。反例同时检查所有相关候选入口与诊断，不能只证明出现 unresolved 或没有 context_claim。
- B skipped 用真实 collector 构造语法坏源，不只手工放一条 skipped；补正常源正例，防止通过把所有结果清空取巧。B unavailable/mismatch 与合法 B 返回分开测试，证明正确分支可达。
- CA 两层测试：先真 validator 给出预期 PASS/REJECT，再测 C 行为。合法 poison/unavailable/multi-scope/partial-verification 不能因错误 fixture 被全部降级而“假绿”。坏包可无包继续，必须同时有独立候选正例。
- X17 的历史文本可以保留为攻击输入，但 PR 真值用可重复的独立 fixture 观察；不要假定 live PR #35 以后仍 OPEN。生产 fallback 使用真实只读 git/gh，测试替身不得直接返回 pack 自称的值。
- known_conflicts 按 key 排除证据，按 scope/path/node 精确关联候选；对相关和无关候选分别断言。动态/相对等不支持信号必须有 UNKNOWN 正面断言，不能只测“没有 RELATION_ADD”。
- F18 无交叉信号、F19 动态依赖、F20 人工否决、X07 mode、X09 ID collision，以及多文件关系删除证明均为 30 项内部必要变体，不替代或减少矩阵项数。
- A29/A30 不是 dual_results 中同名独立 JSON 行：A29 依据各记录 no_map_write，A30 依据冻结报告/Host 产物。未来分别建立独立 hash 与集成故障测试，不能因原数组没有同名行就跳过。

撤回样例不进入缺陷或验收 oracle：初始 A16 缺 position（改用 A16-valid-map）、X10 empty-map（不符合 Core）、初始 A27-map-shape 同时破坏 context map（改用有效 context 下的 malformed_payload_map）。报告已记录的 `additional_faults.json` 仅作输入补充，期望仍由共同契约制定。

关键输入锚点（用于防止迁移错例）：

| Record ID | input_sha256 |
|---|---|
| X01-unchanged-decls-real-import | `351d9d86a0cc43fa205957e4a349578449aec5458bdd52ba7ef5947955de78cc` |
| X04-skipped-relation | `2d5d6fc0df62b8fe39112597850a74c344b39b90f48e1c14b4ec7dc933c190dd` |
| X17-hidden-open | `ea8cbdf902699cf3301a8dcee42f2bb719a771bedf726c0f5cd232755f36d8e3` |
| X18-conflict-by-scope | `deb92c02ee7a494bb64157d1ce9c174296bdf1928ace2b7b233901bbaebe2498` |
| A16-valid-map | `4f95f010ada0bb012d82611eb94b2b30c443139fd968288bd3855034794b7726` |
| A23 | `b3addc5ad3f0e2926296d979a85234bfdce4b5f543cc8f687d52962775ba944f` |

R01–R05 真实 ProjectMind diff 仅作集成 smoke/input 来源，人工 demo map 不代表团队批准的职责划分；不能把历史候选数量作为 golden 或得分。旧 DevKit / author suite 是兼容与基础验证补充，不能取代 30 项语义 oracle；错误旧请求改为契约正确的受控拒绝，不靠恢复误报维持原通过数。

建议未来测试交付组成：contract manifest（30 项及变体/source hash）、确定性 Git fixtures、真实 B/CA 集成 fixture、只读外部核验 fixture、Host 集成 suite、实际 diff smoke。由同一 suite 执行收敛实现；不再维护 TEAM/LOCAL 两份互不一致的验收标准。

## 9. Implementation Order

下面是未来实施顺序。本次不创建 branch、测试或代码。

| 步骤 | 工作与责任 | 退出条件 |
|---|---|---|
| W0 | TEAM owner 固定实现来源与契约 manifest；将 S01–S30 和有效 X/F 变体转成独立 oracle；A owner 确定获批 common base，并立即登记 F12/A30 外部依赖。 | 不以 raw 输出定 expected；withdrawn fixture 已排除；每项 owner/输入/oracle 可追踪。无需修改冻结结论。 |
| W1 | C owner 保留 TEAM seam，移植 P01/P02/P05/P07 基础，先完成 R02/R06 的 pin、shape、path、事实可用性和 canonical 发布 gate。 | mismatch 在所有路径拒绝；坏 pack 整包弃用；skipped 不可能跨通道进入强候选；no-write/lifecycle 不变式已覆盖。此时不开放未完成的 CA enrichment。 |
| W2 | C owner 完成 R01；直接移植 P03，复用 P04 的当前删除能力；补 R05 stale map、可靠新增节点和 entryPoint 变化。 | A01/A04–A10/A16–A18 的正反例与无交叉信号 oracle 通过；不再全树转 NODE_ADD。 |
| W3 | C owner 完成 R03 import 独立通道、语义归一化、两端 map 域及删除全域证明，与 R02 共用 eligibility。 | X01/X11 真关系正例、X03/X12 假 import 反例、X04/X21 skipped、X13 churn 与多源残留全部通过；不能仅修 recall 放大误报。 |
| W4 | C owner 与 CA owner 复核 R04 的消费者边界；完成 scope conflict、typed evidence、字段级支持、独立 fallback 和合法 unavailable 诊断。 | A19–A25 与 X05/X14–X18 全部有效、全部通过；中性 key poison 无法附入 evidence。 |
| W5 | C owner 完成 P06/R07 与 ID 回放迁移；核对 TEAM 兼容 envelope、mode、确定性、路径/错误边界。D/调用方仅审查 ID/字段消费影响，不在 C PR 改 D。 | A26–A29、F20、X07/X09 通过；旧投影只来自已准入 canonical 结果。 |
| W6 | C owner 运行一套完整 suite 与真实 diff smoke；A/Core owner 提供满足 S30 的共享基座；独立 reviewer 按同一 matrix 审查结果。 | §10 全部 gate 满足，再申请人类集成批准；没有“剩余已知问题”豁免。 |

W1 的 CA loader 可先复用，但 context_claim 发布保持关闭直到 W4 的证据准入完成。关系 recall 与 docstring precision 必须在同一阶段验证。任何 port 都先记录来源与边界，再修改；不把整份 LOCAL 复制完成当作里程碑。

## 10. Acceptance Gate

仅满足下列条件才能为**未来收敛版本**提出 READY 评审；当前冻结 heads 继续是 NEITHER_READY/HIGH，本方案本身不产生 PASS 结果。

1. **30/30 Common Acceptance Matrix 为 PASS**，必要有效变体全部通过；FAIL/PARTIAL/NOT_IMPLEMENTED/未执行均不能计为 PASS。基础 author/DevKit 测试绿不替代语义验收。
2. 五个指定问题有独立复现与正确行为证明：TEAM diff×map、TEAM 真 CA validator、LOCAL coherent poison、LOCAL skipped relation、LOCAL unchanged-declarations import add/remove。每项同时包含正例和安全反例，不能通过全部返回空消除失败。
3. 所有 kind 均满足 evidence、PROPOSED、human_required、无 position/无地图写入。所有输入/事实路径均满足 pin 与路径约束；B mismatch 在 supplied/installed、same revision、空 diff 均受控拒绝。
4. poison、conflict、stale、unavailable、未支持外部事实不进入 proposal 的强证据。必要 UNKNOWN/HUMAN_REQUIRED/limits 不能静默丢失；矛盾 pack 的 context 支撑全部停止，独立 diff/B/map 结果按实际证据继续。
5. 证据回放到 pinned Git、真实 B 声明、map 原文及具体 CA pack/source；ID 无碰撞且稳定，F20 抑制可追踪。独立核验不能取 pack 自称值或未冻结 live 状态充当 oracle。
6. C 的实施 diff 不复制/改写 B、CA registry、D、Core Host；共享依赖变更由各 owner 的独立交付提供。**A30 的共享 runtime SystemExit 隔离未满足时，整体 gate 阻塞**，不能由 C 内部 catch、load 测试或历史备注替代。
7. 端到端 Core compare→C route 的 pinned 请求、兼容投影、七扩展隔离及实际 diff smoke 完成；正式地图 hash 不变。通过测试后的代码审查仍需确认候选的事实/推断边界和 owner 接收，不自动写 map 或合并。

未来验收报告应记录：integration HEAD、approved common base、依赖 heads、contract head、suite revision、每个 A 项及变体的 input hash/oracle/result、有效性与撤回清单、回放产物、所有外部依赖状态。人类批准由团队流程决定；机器测试通过不能冒称已获批准。

## 11. Recommended Integration Branch

推荐未来分支：**`integration/c-convergence-v1`**，由 TEAM C owner `bjtxcy` 负责。本次未创建该分支。

建议操作方案：

1. 以 TEAM C frozen HEAD `3bd980ded7a9cc727c1f00c84cf3c2b89c574e40` 的 C 交付为起点，保留 TEAM 的 owner/扩展接入。先由 A/Core owner 确认共同依赖基座，再将 TEAM C 交付对齐到获批基座；如果使用 rebase 导致提交 SHA 变化，manifest 仍记录 TEAM source SHA 与 C-only diff 来源。
2. 将 C 实施范围限定到 `extensions/map_proposal/`、对应 C contract/集成测试与必要的 C 消费者文档。共享 A/B/D/CA 的提交由其 owner 对齐，不用 LOCAL PR #34 的整条祖先链自动解决依赖；`f43dcaf...` 仅是已验证候选基座，不能假称已批准。
3. 按 P01–P09 明确选择文件/符号移植，按 R01–R07 重建缺陷职责。移植提交写 source SHA + symbol + changed boundary + tests，标准 rename 等成熟模块直接复用；不得 whole-merge PR #34 或盲 cherry-pick 其后续修复提交。
4. 在同一分支形成一个 route、一个 canonical 模型、一个 evidence gate 和一套 suite。建议提交序列按 W1 gates / W2 diff-map / W3 relations / W4 CA trust / W5 compatibility / W6 integration 分开，便于 owner 审查与回退；这只是未来提交建议。
5. 未来 PR 的 base、是否 draft、审批与合并由 owner 流程确认；描述围绕最终行为、来源边界与统一验收，不写实现排名。共享 Host 修复独立关联为依赖；未满足 §10 时不请求最终合并。

如获批 common base 尚未确定，仍可先固定 oracle、port manifest 和 C-only 设计；不能将 LOCAL HEAD 当作默认替代产品。禁止从 LOCAL 5058... 起建后称为 TEAM baseline，除非团队另作明确治理决定并重新记录来源；本方案没有提出该变更。

## 12. Estimated Risk

**总体预计风险：HIGH，主要来自证据安全、关系分析和共享集成依赖。** 这是未来迁移风险估计，不是重新比较结果，也不改变冻结结论的 HIGH confidence。未实施、未测试，不能给出已经降低风险或 READY 的承诺。

| 范围 | 风险 | 主要原因 | 降低风险的必要证据 |
|---|---|---|---|
| TEAM seam、SHA/path 原语、成熟 rename 小组件 | LOW–MEDIUM | 接口接线与旧消费者兼容；已有合规核心可直接移植 | route/路径/rename 正反例，canonical 与旧投影一致 |
| diff×map 调度、模块/入口候选 | HIGH | TEAM 核心缺失；新增声明不等于新职责，LOCAL 首个 class 策略不可继承 | 六 kind 正例、噪声反例、全树/changed-only 一致、关键声明回放 |
| B gate 与 skipped 跨通道约束 | HIGH | 多来源、多早退、多路径证据域可能绕过 | mismatch 全路径矩阵、真实 skipped 与正常源配对、无 shape 崩溃 |
| import add/remove 与跨域证明 | HIGH | 声明 gate 漏报、docstring 误报、跨文件关系删除与未支持形式 | X01/X11/X12、churn、跨源残留、UNKNOWN 正面 oracle |
| CA trust / poison / scope conflict | HIGH | 结构合法不保证真伪；关键词/首条 supplement 不安全 | 真 validator-pass poison、中性 key、字段级支持、独立真值、scope-only conflict、合法 unavailable |
| stale map、稳定 ID、回放与人工否决 | MEDIUM–HIGH | 无 map 版本身份；旧 ID 引用与多 evidence 路径迁移 | 早删/部分保留/未知读取、碰撞检查、ID 迁移说明、F20 |
| 兼容输出与 mode | MEDIUM | 正确拒绝旧不完整输入可能改变 demo；候选 schema 投影有限 | 真实 pinned 请求、旧字段子集、X07 honesty、消费者审查 |
| A30 共享 Host | HIGH / 外部 blocker | C owner 无权以本模块代替全局隔离修复 | A/Core 独立交付 + 七扩展 runtime 故障回归 |

责任分工：TEAM C owner 对收敛实现与 suite 交付负责；A/Core owner 对 approved common base、compare/Host 共享边界负责；B owner 审查真实事实接口；CA owner 审查 validator 与消费边界；D/调用方审查 proposal ID/输出引用影响。LOCAL 开发者可解释来源组件，但不因此替代 TEAM C ownership。

未给出工时承诺：重建和外部依赖尚未排期。优先完成 W0/W1 建立可审查的 oracle 与 gate，再由 owner 根据移植量和依赖安排估时；不能用“多数代码可复制”推断低风险。

本次交付仅为 **C_CONVERGENCE_PLAN.md**：没有修改实现或测试代码，没有重跑两份 C、没有 commit/push/merge，也没有创建推荐分支。**STOP。**
