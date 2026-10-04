# C Convergence — Oracle Manifest (W0)

S01–S30 一一对应冻结 Common Acceptance Matrix A01–A30，目标全部 PASS。两列历史状态不作 oracle。撤回样例（初始 A16 缺 position、X10 empty-map、初始 A27-map-shape）不进入缺陷或验收 oracle。

| ID | Common / 场景 | 必须断言的目标行为 | 变体 |
|---|---|---|---|
| S01 | A01 real NODE_ADD | 新模块无 map 覆盖且有 B 声明: 恰好预期节点，git_diff + 可回放 code_fact + map 判断；全树/changed-only 不多生无关节点；PROPOSED/human_required。函数型模块不凭 class 门槛定案。 | A01、X19 |
| S02 | A02 real RELATION_ADD | 新增实际跨域 import: 预期 from/to 的 RELATION_ADD，精确源 diff + 两端 map 证据；声明没变仍触发。 | A02、X01; class 前/后 import |
| S03 | A03 relation removal | 最后跨域 import 消失: 对应既有 edge 的 REMOVE_CANDIDATE；其他源仍 import 不移除；churn 不移除。 | A03、X11/X13; 跨文件剩余 import |
| S04 | A04 implementation link | rename/move: 对应 node 路径更新，old@base/new@target，不 NODE_ADD。 | A04; 移动子目录 |
| S05 | A05 node removal | node 全 evidence 明确从 target 消失: 低置信度删除候选；任一路径保留则无删除候选。 | A05; 多 evidence 部分保留 |
| S06 | A06 responsibility change | entryPoint 声明改名/消失: 对应 node 责任/实现链接候选，声明证据由 B 给出；不选无依据的首个替代符号。 | A06; 多声明歧义 |
| S07 | A07 comment only | 零强 proposal，明确 comments_only 原因；无无关人工任务。 | A07、X20 |
| S08 | A08 formatting only | 零 proposal，格式原因；不因行号/引号漂移制造新职责。 | A08 |
| S09 | A09 helper only | 已有职责加 helper 不 NODE_ADD；无其他交叉信号无强 proposal。 | A09、F10 |
| S10 | A10 internal class only | 已有职责加内部 class 不 NODE_ADD；提示不宣称新职责事实。 | A10、F9 |
| S11 | A11 docstring only | 仅 docstring（含 import 文本）零关系/节点强 proposal；有其他声明变化也不能把字符串当 import。 | A11、X03/X12 |
| S12 | A12 test noise | 仅 test/generated 噪声无业务架构候选；不例行制造人工 unknown；确与 map 交叉按实际证据。 | A12; R02/R05 噪声输入 |
| S13 | A13 B skipped | 真实 skipped changed 源 HUMAN_REQUIRED；任何通道/兼容 candidates 无依赖该源的强候选；正常源仍工作。 | A13、X04/X21; 真实 collector 语法坏源 |
| S14 | A14 B mismatch | supplied/installed B mismatch 一律受控拒绝；同 revision、空 changes 不绕过。 | A14、X06; 安装 B 注入 mismatch |
| S15 | A15 B unavailable | 明确 limits/DEGRADED；安全 diff↔map 分支仍运行；需 B 的新模块 unresolved、零虚构 code_fact。 | A15; 独立 rename 正例 |
| S16 | A16 stale map | 早于 base 删除、target 全 evidence 缺失仍有 stale removal candidate；读取未知 ≠ 缺失。base==target 零 proposal + map drift limit。 | A16-valid-map `4f95f010...`、F11/F15 |
| S17 | A17 ambiguous mapping | 多 map owner: 低/中置信度并列 multiple candidate nodes 或 unresolved；不武断单选。 | A17; 多 owner rename |
| S18 | A18 missing evidence | 新文件但 facts/diff 证据不足: unresolved UNKNOWN、零强候选；B 没条目 ≠ 架构不存在。 | A18; 无声明/缺关键证据 |
| S19 | A19 CA conflict | relevant key/scope conflict 不入任何 proposal evidence；相关候选 HUMAN_REQUIRED；精确无关节点仍有有效候选。 | A19、X14/X15/X18 |
| S20 | A20 stale claim | validated stale 与其他非现行分区不进 context_claim；相关消费需求有 limits/UNKNOWN。 | A20; stale/proposal/research/history 分区 |
| S21 | A21 multi-scope | 真实合法 pack 同 key 多 scope 均进选择层；按相关用途分别消费，不读 current 投影、不随便加首项。 | A21; 正面计数 + 两 scope 关联 |
| S22 | A22 verified_fields | 支持字段与无支持字段分开；后者 UNVERIFIED/诊断、不能作事实支撑；行 freshness 不升级整值。 | A22; 多 evidence ref、字段部分覆盖 |
| S23 | A23 unavailable | 合法 unavailable/stale fixture 先 validator PASS；C 不伪作坏包 DEGRADED；相关值排除且明确 UNKNOWN/limits。 | A23 `b3addc5a...`; 替换旧 C_A23 自测 |
| S24 | A24 invalid pack | 真实 validator 拒绝: 整包不消费、零 context_claim、显式 DEGRADED；独立有效 diff/B/map 候选仍可存在。 | A24; 同 SHA 缺字段/坏回链/错 revision |
| S25 | A25 coherent poison | 结构与 digest 合法的 poison 不进 evidence/rationale；高影响事实有独立真值或 UNKNOWN；矛盾记录 claim_id/双方值，pack 不再可信。 | A25、X05/X16/X17 `ea8cbd8f...`(X17); 中性 key/自由文本、核验不可用 |
| S26 | A26 determinism | 固定输入 + 固定外部观察重复字节一致；ID 不依赖偶然遍历顺序，无时间戳/随机数。 | A26-repeat、X09; 排序变体 |
| S27 | A27 malformed input | HEAD/短 SHA/错 facts shape/错 map shape/缺字段受控拒绝；安装 B 异常 shape 不崩溃、不误当 available。 | A27; valid-context malformed_payload_map |
| S28 | A28 path abuse | changed/old_path/map evidence/facts/entryPoint 全来源路径约束；拒绝越界/绝对路径/不安全输入；不读工作树或 repo 外补证。 | A28; map evidence + rename 双侧 |
| S29 | A29 no map write | 请求前后正式地图及 source fixture 文件 hash 不变；无 save/apply/accept 或 position proposed_change。 | 冻结 no_map_write 字段 + 独立 hash 断言 |
| S30 | A30 Host isolation | 七扩展可加载；普通异常与 runtime SystemExit 均不阻断其他路由。C 边界与共享 Host 分别测试。**依赖 A/Core 修复才能 PASS。** | 冻结 Host 场景 |

## Fixture 纪律

- 原始记录 `request/repo/input_sha256` 可恢复输入；`results/assertions/summary` 是冻结观察，不能复制为 expected output。每个 migrated fixture 保留 source record ID/hash + 契约条款出处。
- A01–A06 正例检查 kind、subject、map node/edge、实际证据、status/human_required；反例检查所有相关候选入口与诊断。
- B skipped 用真实 collector 构造语法坏源；补正常源正例。B unavailable/mismatch 与合法 B 返回分开测试。
- CA 两层测试: 先真 validator PASS/REJECT，再测 C 行为。坏包可无包继续，必须同时有独立候选正例。
- 动态/相对等不支持信号必须有 UNKNOWN 正面断言。F18 无交叉信号、F19 动态依赖、F20 人工否决、X07 mode、X09 ID collision、多文件关系删除证明为 30 项内部必要变体。

## 关键输入锚点

| Record ID | input_sha256 |
|---|---|
| X01-unchanged-decls-real-import | `351d9d86a0cc43fa205957e4a349578449aec5458bdd52ba7ef5947955de78cc` |
| X04-skipped-relation | `2d5d6fc0df62b8fe39112597850a74c344b39b90f48e1c14b4ec7dc933c190dd` |
| X17-hidden-open | `ea8cbdf902699cf3301a8dcee42f2bb719a771bedf726c0f5cd232755f36d8e3` |
| X18-conflict-by-scope | `deb92c02ee7a494bb64157d1ce9c174296bdf1928ace2b7b233901bbaebe2498` |
| A16-valid-map | `4f95f010ada0bb012d82611eb94b2b30c443139fd968288bd3855034794b7726` |
| A23 | `b3addc5ad3f0e2926296d979a85234bfdce4b5f543cc8f687d52962775ba944f` |
