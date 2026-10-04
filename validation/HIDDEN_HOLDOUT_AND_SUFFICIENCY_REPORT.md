# HIDDEN_HOLDOUT_AND_SUFFICIENCY_REPORT — 独立 Hidden Holdout + Context Pack 充分性实验

- 实验人:全新独立 Agent,2026-10-03
- 问题集:24 个全新问题(`../evidence/holdout/GROUND_TRUTH_FROZEN.jsonl`,GT 在派发 agent 前**先冻结**;与作者旧 20 问零重复)
- 条件与样本:
  - **RAW**(全仓库常规材料,禁读 CA 产物):3 agents(R1/R2/R3)
  - **CONTEXT PACK + evidence fallback**(CLEAN pack + AGENT_BOOTSTRAP + 允许 git/gh 只读核验):3 agents(C1/C2/C3)
  - **PACK-ONLY**(唯一来源=pack 文件,禁 git/gh):1 agent(B1)+ poisoning 研究中 CLEAN 对照 1 agent(共 2 个数据点)
- 判定:实验者对照冻结 GT 逐题判定;分歧处做独立裁决(见 §4 h19)。

---

## 1. 一句话结论

**CONTEXT PACK 条件在 24 题上 3 个 agent 零事实分歧、零错误;RAW 条件出现 2 处 agent 间事实分歧(其中 1 处是真错误);PACK-ONLY 对 24 题只有 6 题充分可答但 0 幻觉。CA 的价值不是"让答案一样",而是"指针+事实底座让 agent 少踩坑、多找到散落证据"。**

## 2. 总分

| 指标 | RAW (n=3) | CONTEXT+evidence (n=3) | PACK-ONLY (n=2) |
|---|---|---|---|
| GT 正确率 | 71/72 题(98.6%;R3 h23 错误) | **72/72(100%)** | 16/48 可答项全对 |
| agent 间事实分歧 | **2 对**(h19、h23) | **0 对** | n/a |
| 真实错误(与 GT 不符) | 1(R3 h23) | 0 | 0 |
| 无依据假设 | 1(R3 h23 从测试文件推断 GET actions) | 0 | 0 |
| 过期资料当现行 | 0(两组都正确隔离 line-106/旧映射) | 0 | 0 |
| 幻觉(编造 pack 没有的事实) | 0 | 0 | **0(14 个 NOT_IN_PACK 全部诚实标注)** |
| h14(686 构成) | 3×诚实 UNKNOWN | **3×答出**(343×2,经 pack 指针找到 benchmark 报告) | PARTIAL(只有总数) |
| h16(V2 映射出处) | 3×UNKNOWN(禁读限制内找不到) | **3×答出**(claim-v2-role-map 的 scope 指向 model 仓 MVP_PROPOSAL.md) | 1×答出 |

## 3. 逐题明细(关键行)

- **h23(GET actions 数量)**:R1/R2/C1/C2/C3 全部答 3(state/claims/conflicts,✓);**R3 答 4(把 POST 的 context 误归 GET),依据是测试文件里的 action 字符串——真实的无依据假设+过期用法**,且 R1 与 R3 形成同条件事实分歧。CONTEXT 组无一出错(2 人直接读了 extension.py 的 GET_ACTIONS,1 人读 schema 文档)。
- **h19(SHA-256 验收状态)**:R1 称"SHA-256 仓库已有测试覆盖"(引 PR31 测试),R2/R3/C1/C2/C3 给出 PR22 README 的"尚未验收"保留。**独立裁决:R1 更新——PR #31 的 tests/test_code_facts.py 确实新增了 `test_sha256_repository_when_supported_by_installed_git`。** 这是一次**真实且可被证据裁决的分歧**,同时暴露一个跨模块风险:B 的 PR31 已在演进接口与测试面,而 CA registry 的契约 claim 仍钉在 PR22 README(§5)。
- **h14/h16**:RAW 组 3/3 诚实 UNKNOWN;CONTEXT 组 3/3 答出。**这是 pack"指针价值"的直接证据**:pack 不含 686 的构成,但 `implementation.code_facts` 的 evidence 链把 agent 引到 benchmark 报告;pack 自身不知道 V2 全文,但 `claim-v2-role-map` 的 scope 字符串直接给出 model 仓库文件路径。
- **h02(PR22 是 Draft)**:pack 无 draft 字段,RAW 组 3/3 与 CONTEXT 组 3/3 都通过 gh api 独立查出——**CA 漏掉的 volatile 属性被 evidence fallback 补上**(对应 FINDING-07)。

## 4. Context Pack Sufficiency(条件 B 逐题判定,依据 B1 实答)

| 判定 | 题数 | 题 |
|---|---|---|
| SUFFICIENT(pack-only 完整可答) | 6 | h01 main head、h05 文件数上限、h06 大小上限、h09 line 109、h16 V2 出处、h22 mapSource 提案 |
| PARTIAL | 5 | h07 skipped 语义(缺不存在路径行为)、h14 评测总数(缺构成)、h15 旧 A 角色(缺职责全文)、h19 SHA 规则(缺验收保留)、h20 revision(缺分支关系) |
| INSUFFICIENT(pack 无该信息) | 13 | h02 draft、h03 PR 标题、h04 PR 文件清单、h08 超时/POST 限制、h10 suggest_map 签名、h11/h12/h13(PR26/27/31)、h17 POST 上限、h18 revision 相等约束、h21 PR24、h23 GET actions、h24 tests 清单 |

**三条件画像**:
- A=Full repo:覆盖最广,但 2 处 agent 间分歧 + 1 错误 + 散落证据找不到(h14/h16)。
- B=Pack only:**零幻觉、零分歧**(两人数据点),但 54% 的问题答不了——**单独用 pack 不够,它只覆盖"当前事实底座",不覆盖 PR 全景/接口细节/代码树**。
- C=Pack+evidence:100% 正确 + 0 分歧 + 覆盖与 RAW 持平甚至更广(h14/h16 反超)+ 显式排除 pack 未覆盖区(h02 等)。

## 5. 对 C_CONSUMABLE 判定的直接输入

1. C 必须实现为 **C=Pack+evidence 条件**(§6 C_CONSUMABLE_INTERFACE 据此把 evidence fallback 定为 MANDATORY);pack-only 模式仅可用于"快速定向",不得作为唯一事实来源。
2. **registry 需要跟进 PR31**:B 契约 claim 现钉 PR22 README@0c46747,但 PR31(feat/30-code-facts-integration)已改 facts.py 并新增 SHA-256 测试。若 PR31 合并,B 契约的 evidence 应更新(这正是 append-only registry + supersedes 的设计用途)。
3. 与作者旧实验的关系:作者的 frozen 20 问实验(Raw 60/60 = CA 60/60,0% 分歧)经**原始数据抽查成立**(B1/A1 的 q01–q05 与 GT 逐条一致,final_metrics.json 与原始 jsonl 相符);我的 24 问 holdout 在更高难度(h14/h16/h23 需要跨仓库/跨产物/代码级证据)下复现并强化了结论,同时补上了作者实验没有的:pack-only 充分性画像与真实分歧样本。

## 6. 实验限制

- RAW 条件的禁读清单靠 prompt 约束,无法硬保证;三人都未违反(其 h14 UNKNOWN 恰是证据)。
- CONTEXT 条件允许 evidence fallback,因此"100% 正确"不能全记在 pack 头上;pack 的独立贡献由 PACK-ONLY 条件单独度量(6 SUFFICIENT/5 PARTIAL)。
- 单轮、小样本;分歧率 0 是必要非充分证据,不能外推为"永远 0"。
- h19 的 GT 本身被 PR31 推翻,说明**冻结 GT 也会过期**——CA 的 verifier/registry 机制正是为此设计,这条应记录为 GT 维护的教训。
