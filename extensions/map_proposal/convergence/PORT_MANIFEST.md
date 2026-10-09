# C Convergence — Port / Keep / Reimplement / Drop Manifest (W0)

任何 port 先记录来源与边界再修改。移植提交写 source SHA + symbol + changed boundary + tests。不把整份 LOCAL 复制完成当作里程碑。

## KEEP_FROM_TEAM

| ID | 保留对象 | 收敛动作 | Oracle |
|---|---|---|---|
| K01 | 正式 C owner、扩展标识、ExtensionHost 接入与 handler seam (T.extension `handle`) | 沿用已注册路由和标准库基础；不引入第二个 map_proposal 注册或共享请求可变状态；内部委托单一新调度器 | A30 route smoke；请求间状态不串扰 |
| K02 | PROPOSED/human_required、不写 map、不输出 position 边界 | 提升为所有 kind、所有输出路径的统一发布不变式 | A01–A06、A29 |
| K03 | `_make_response` 旧 status/revision/candidates/note 兼容外壳 | 从已校验四桶结果生成投影；旧 candidates 仅投影其 schema 能表达的合规 NODE_ADD；revision 为完整 target | A26/A27、X07 |
| K04 | skipped 变化源保守进 unresolved | 统一候选准入原则；只报告相关 changed skipped，不制造全树无关诊断 | A13、X04/X21 与正常文件正例 |

## PORT_FROM_LOCAL（LOCAL_ROOT 冻结 @ 5058c54）

| ID | 来源与最小单元 | 移植方式 | 边界 |
|---|---|---|---|
| P01 | L.ca `load_context` 21–67: pin/真实 validate/整包弃用/current_by_scope 选择 | 直接移植核心适配模块，补 RECORD/诊断 | 保留合法 pack 元数据；`verified_fields` 不只取第一引用推广整行；不带入 L.engine supplement/trust policy |
| P02 | L.model `SHA_PATTERN`/`validate_path`/`parse_entry_point`; L.engine node_by_path/entry_lookup | 直接移植原语与索引核心，扩大调用覆盖 | 统一校验所有来源路径；Core map schema 适配由 R06 完成 |
| P03 | L.engine `_handle_renamed` 183 起 | 直接移植 rename/move 核心 | old@base/new@target 证据；multiple owners 降置信度/uncertainty；发布前接统一 skipped/conflict gate；不因 rename 建新节点 |
| P04 | L.engine `_handle_removals` 321 起合规子逻辑 | 选取合规子逻辑移植 | 保留 A05 行为；移除 B availability 门槛；补 R05 早于 base 删除检测 |
| P05 | L.diff `_git` 22 起、`resolve_module` 103 起、`static_import_count` import AST 遍历核心 | 直接复用只读 Git/有界模块解析原语；调整 AST 结果模型 | 保留环境清理、pinned blob、no-lazy-fetch/禁 ext diff、超时；SyntaxError 不再当"零"；未支持相对/动态形式 UNKNOWN |
| P06 | L.engine prior_decisions 431 起 REJECT 抑制流程 | 移植隔离的抑制/limits 结构，核对适用条件 | F20 同 subject/kind 且理由未变；实质变化允许重新待审 |
| P07 | L.model `make_evidence`/`make_proposal` 字段骨架; L.engine evidence 组装 | 移植结构，改回放与身份细节 | 补结构化 path/name/line、完整 CA 回链、R06 ID；不复制 first-three 截断与 first-class 入口推断 |
| P08 | L.engine `_mentions` 57 起词边界匹配、确定性排序 | 直接移植小组件，限定用途 | 防 node-a/node-api 子串误伤；不是 scope/关系归属唯一判断 |
| P09 | LOCAL/frozen dual fixture 有效构造与标准正例 | 迁移为共享测试输入 | 不迁移旧错误输出作 golden、弱负断言、无效 CA fixture |

不整体移植 L.engine.suggest、L.diff.import_signals、L.facts.load_code_facts。

## REIMPLEMENT

| ID | 重建职责 | 必须行为 | Oracle |
|---|---|---|---|
| R01 | diff × map 调度与候选判断 | 按 A compare 真实变化和 map 覆盖决定 kind；声明/import/map 通道独立运行，最后判断 no_proposal；全树与 changed-only 一致；新增 class/helper 不证明职责新增 | A01–A12/A17/A18、F18 |
| R02 | B 适配与统一事实可用性 gate | supplied/installed 两来源返回后都查 target equality（早退之前）；normalize 受控错误边界；区分 unavailable/skipped/无条目/错误 shape；skipped 约束覆盖每个候选证据域与关系端点 | A13–A15/A27、X04/X06/X21 |
| R03 | 独立 import 关系分析 | pinned patch 变化事件 + base/target import AST 验证；规范化同目标 import/churn；映射两端 node evidence 域；仅对已存在 map edge 且跨域 import 全消失给移除候选；动态/相对/解析失败 UNKNOWN | A02/A03/A11、X01/X02/X03/X11/X12/X13 |
| R04 | CA evidence 准入、独立核验与 conflict 路由 | 真 validator 后只用有明确消费用途的 claim；未知语义自由文本进诊断；按每条 evidence 的 source 与 verified_fields 验证字段支持范围；高影响事实独立 git/gh 观察；按结构 key/scope + 精确 path/node 关联判冲突；核验矛盾记录 claim_id/双方值并 pack 停用；不可核验 UNKNOWN；合法 unavailable/stale 显式 limits | A19–A25、X05/X14–X18 |
| R05 | stale map 目标存在性判定 | pinned target Git tree/blob 确定存在性检查全部有效 evidence 路径；本轮 removed 只是一种来源；读取异常 ≠ 不存在；全部确认缺失给低置信度 removal candidate；same-revision 先 gate 后零 proposal | A05/A16、F15 |
| R06 | canonical 请求/输出、ID 与证据回放 | Core compare 显式适配；proposal ID = target+kind+规范化 subject/payload 稳定短 hash；node ID 含完整 repo-relative path/稳定 hash 并查现存 map ID；code_fact 引 actual selected name/kind/line/path/revision；CA 引用含 pack_revision 回链 | A01/A06/A18/A26–A29、X09、F20 |
| R07 | 兼容 response / mode / 错误边界 | TEAM handler 只发布 canonical 结果及兼容投影；规则方法如实标识；无真实模型不标 ai_candidate；输入错误受控拒绝；依赖失败显式 limits/降级；旧缺 pin 请求不偷补 SHA | X07、A26/A27/A30 |

关系"移除"证明范围 = map 节点 evidence 域。CA conflict 约束作用于所有六种候选。

## DROP_FROM_TEAM

| ID | 删除行为 | 替代 |
|---|---|---|
| T01 | B 全文件转 NODE_ADD 与未经 map 检查的"地图缺节点"断言 | R01 |
| T02 | 缺 pin 自动 snapshot HEAD / 接受短 SHA | R02/R06 |
| T03 | 仅 pack revision 相等即接受；列 conflict 后仍保留关联候选 | P01 + R04 |
| T04 | 凭 API key/env/mode 声称 ai_candidate | R07 |
| T05 | 无结构化 path/name/line 的 code_fact、顺序/压缩路径 ID、独立旧 candidates 生成 | R06/K03 |
| T06 | 对全树非 changed facts/skipped 制造节点或人工噪声 | 仅相关变化进候选/诊断 |

## DROP_FROM_LOCAL

| ID | 删除行为 | 替代 |
|---|---|---|
| L01 | key/字段/文本黑名单充当高影响事实验证 | R04 |
| L02 | 第一个幸存 claim 自动附到第一个 proposal | R04 |
| L03 | declaration_unchanged 排除关系分析/文件全局早退 | R01/R03 |
| L04 | skipped 仅文件 handler 过滤，relation 通道继续 | R02 |
| L05 | patch regex 单独证明 import；解析失败当零；单源 import 归零当关系消失 | R03 |
| L06 | same-revision 在 B 校验前成功返回；安装 B 返回值不查 revision | R02 |
| L07 | normalize 异常泄漏、无视 wanted_paths 全树 B 收集、map evidence 路径不统一验证 | R02/R06 |
| L08 | conflict 只匹配 value 文本、忽略 scope；合法 unavailable/stale 静默排除 | R04 |
| L09 | basename node ID、顺序 ID 依赖、关键 fact evidence 截前三条 | R06 |
| L10 | 首个 class/首个替代声明自动当职责或 entryPoint | R01 |
| L11 | 只按本轮 removed 发现 stale map 且依赖 B available | R05 |
| L12 | 旧自测 C_A23 无效 unavailable fixture、只查"无 context_claim"的弱断言 | 真实 validator-pass fixture + 正面状态/诊断断言 |

禁止: 整体合并 PR #34、整包复制 LOCAL C、两个 map_proposal 注册、两个候选引擎 union、两套 CA validator 策略、两套 diff 文件口径。不把 pack digest 当真伪认证，不把 demo map 视为获批架构，不把候选自动应用到正式地图。
