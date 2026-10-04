# C_IMPLEMENTATION_SEQUENCE — 给 C 开发者的施工顺序

> 原则:每个 Stage 结束都有可运行、可验收的东西;Stage 0–4 不需要任何人批准即可在独立分支开工(不动 main/其他扩展);Stage 5–6 涉及流程与 A,需要人确认。

## Stage 0 — 读 Context Pack(纯读)
- 实现 `load_pack(path_or_dict, expected_revision)` 五步协议(PIN→VALIDATE→SELECT→EVIDENCE→RECORD,见 C_CONTEXT_AUTHORITY_USAGE.md)。
- 测试:注入 CLEAN pack 通过;注入 P05 同款相干伪造 → 必须硬停止(防中毒回归测试)。
- 交付:pack loader + 单测;无 UI。

## Stage 1 — 接 Git diff
- 输入 changed_paths(与 A 的 /api/compare 同口径);实现 diff↔地图交叉模型(哪些 path 属于哪个 node 的 evidence 域)。
- 测试:F15(same revision)、F18(无交叉信号)、F11(过期地图)。
- 交付:`analyze(diff, map) -> {candidates, unrelated}` 内部结构 + 单测。

## Stage 2 — 接 B Code Facts
- 实现 B 调用封装(revision 一致性断言、skipped 隔离、限额遵守)。
- 测试:F13(skipped)、F10(helper 不建 node)。
- 交付:`facts facade` + 单测;**此时 B 未合 main 时用 fixture 桩**。

## Stage 3 — candidate evidence model
- 把 diff 信号与 code facts 合成 candidates,每个 candidate 带证据链(git_diff/code_fact/map_node/context_claim 四种 kind)。
- 测试:F14(证据缺失→UNKNOWN)、F17(多候选)、F19(弱信号→NEEDS_HUMAN_REVIEW)。
- 交付:evidence schema 校验函数 + 单测。

## Stage 4 — 产生 MapProposal
- 实现 7 种 kind(NODE_ADD/…/UNKNOWN)与确定性输出(双跑字节一致)。
- 测试:F1–F9、F16;反目标扫描(position/status/evidence 为空即 FAIL)。
- 交付:`extensions/map_proposal/extension.py`(handle:GET 状态页 + POST suggest)+ 独立 API;**到此为止 C 已可用(离线形态)**。

## Stage 5 — human accept/reject flow
- proposal 落盘为 JSON 文件(proposal_id 命名含 target_revision);实现 accept/reject 命令或页面按钮,产出 decision log(谁、何时、对哪个 proposal_id)。
- 测试:F20(人工否决抑制重复)。
- 注意:**地图写入仍不在 C 内**;ACCEPTED 的变更由人/A 执行(或生成"建议补丁"给人看)。

## Stage 6 — A integration
- 与 A 一起决定:proposal 列表是否渲染进主图待复核区、mapSource 身份补丁的先后关系(C 不抢它的活)。
- 验收:真实 core 仓库 diff 跑一轮冒烟;172 既有测试 + C 测试全绿。
- 交付:PR(独立分支,正常 commit,不 force push)。

## 每阶段的"不做"清单
- 不改 main、不改其他扩展、不合并任何 PR。
- 不引入 LLM 调用(V0.1 是确定性规则引擎;LLM 建议是后话,需人另批)。
- 不抢 mapSource/版本身份的实现(那是独立的 PROPOSED 提案)。
- 不把 CA 变成硬依赖(CA 不可用时降级运行,见 C_CONTEXT_AUTHORITY_USAGE.md 降级路径)。

## 第一个里程碑建议(半天可完成)

Stage 0+1+4 的最小闭环:输入 = pinned revision 的 diff(手工构造)+ 当前地图;输出 = 1 条 NODE_ADD 候选(F1)+ F6/F7/F8 的 no_proposal;evidence 只用 git_diff kind(不需要 B)。它能端到端验证边界(只建议、不写入)与确定性,再往 Stage 2/3 加厚。
