# CODEX_C_CONVERGENCE_CONTINUATION

> 交接对象：Codex（GPT-6.1 Sol，reasoning=medium，default tier）。ZCode 已完成 90 分钟冲刺的全部 W 阶段，本文件是唯一交接入口。Codex 可按需自行读取 repo，不要要求重述历史。

## 1. 产品目标

收敛 TEAM C baseline + 选择性 LOCAL 移植 + 共享回归 suite 的**单一 C 实现**，最终达到 `C_CONVERGENCE_READY_FOR_HUMAN_REVIEW`（30/30 PASS + 独立审查），之后 B+C+D integration → `BCD_SAFE_FOR_HUMAN_REVIEW`。冻结结论仍是 **NEITHER_READY / HIGH confidence**，本分支不改变它。

## 2. Frozen source heads（只读参照，不许改动）

| 对象 | 标识 |
|---|---|
| TEAM C baseline | `3bd980ded7a9cc727c1f00c84cf3c2b89c574e40` @ `feat/role-c-map-proposal`（PR #35） |
| LOCAL C | `5058c54aa52243c15b286a4922a362c48c941967` @ `feat/map-proposal-mvp`（PR #34，只作移植来源） |
| 契约文档 | `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa` |
| B 接口 | PR #31 @ `80e091acefd278fda03e188a125147b0aa5eedc5` |
| CA 接口 | PR #29 @ `9ea23491d1849f21bad9f60c1c1ca8df55bb5936` |
| 实施依据 | `G:/jiagou/C_CONVERGENCE_PLAN.md` |

## 3. 当前 integration/convergence HEAD

- Worktree：`G:/jiagou/projectmind-c-convergence`
- Branch：`integration/c-convergence-v1`（从 TEAM C frozen HEAD 3bd980de 起点）
- HEAD：**`78c2751`**，已推送 origin。提交链：`5b259df`(W0) → `b2071bf`(W1) → `ced0ee3`(W2) → `7ad77bb`(W3) → `13db5fc`(W4) → `a2f3e55`(W5) → `78c2751`(W6)。
- Working tree clean，无 dirty files。

## 4. W0–W6 状态

| Stage | 状态 | 内容 |
|---|---|---|
| W0 | ✅ | `extensions/map_proposal/convergence/`：SOURCES/CONTRACT/ORACLE(S01-S30)/PORT/COMMON_BASE manifests + A30(D1) 依赖登记 |
| W1 | ✅ | pin/path 校验（拒绝 HEAD/短 SHA/snapshot 补值）、B revision gate（supplied+installed 全路径、同版本/空 diff 不绕过）、skipped 统一 eligibility、canonical 四桶、稳定 ID、no-map-write、mode 诚实 |
| W2 | ✅ | diff×map 通道：rename→IMPLEMENTATION_LINK_CHANGE（不 NODE_ADD）、NODE_ADD 精度（map 覆盖/test/generated 排除、函数型模块低置信度）、RESPONSIBILITY_CHANGE（不选首个替代符号）、R05 stale-map 全 evidence 存在性（早于 base 删除、读取失败≠缺失）、F20 抑制 |
| W3 | ✅ | 独立 import 通道：regex 仅候选信号、AST 对 pinned blob 是证明、X01/X11 声明不变仍有关系、X03/X12 docstring 不误报、X13 churn、X02 动态→unresolved、关系删除需现有 map edge + 全域 import 消失证明、skipped 不进关系通道 |
| W4 | ✅ | CA trust：自身 pin + 真 validator、坏包整包弃用、**无任何 claim 自动附加**（L01/L02 根除）、conflict 按 key/scope/词边界路由（相关候选转 unresolved、无关候选不受影响）、verified_fields 字段级、unavailable 显式 UNKNOWN、非现行分区不读 |
| W5 | ✅ | K03 兼容投影（candidates ⊆ 已准入 NODE_ADD）、X07 诚实、A26 字节级确定性、X09 node id 冲突加宽、S28 路径约束、ID 迁移文档 `convergence/C_ID_MIGRATION.md` |
| W6 | ✅(smoke) | 真实 HEAD~5..HEAD 历史 + demo map 端到端 smoke：发布不变式、确定性、地图 hash 不变、无 B 时诚实降级 |

## 5. 已完成代码（本分支 extensions/map_proposal/）

- `model.py` — P02 原语（SHA_PATTERN/validate_path/validate_request/validate_map/parse_entry_point）、Core compare 适配、R06 稳定 ID、K02 构造期不变式（无 position、evidence 非空）
- `facts_adapter.py` — R02 统一 gate（所有路径 revision 相等、skipped/eligibility、形状漂移降级）
- `analysis.py` — R01 通道（renamed/added/modified）+ R05 stale-map + F20（L09/L10/L11 已修）
- `relations.py` — R03 import 通道（L05 已修：AST 证明、域级删除证明）
- `ca_adapter.py` — P01 + R04（L01/L02/L08 已修）
- `engine.py` — 单一调度与发布出口、canonical 结果、K03 投影
- `extension.py` — K01 seam（受控 400/500，无第二引擎）
- `gitio.py` — P05 只读 git（环境清理、no-lazy-fetch、15s 超时）
- 测试：`tests/test_map_proposal.py`(31) + `test_w2_channels.py`(20) + `test_w3_relations.py`(10) + `test_w4_ca_trust.py`(11) + `test_w5_compatibility.py`(14) + `test_w6_smoke.py`(1) = **99/99 OK**

## 6. 未完成工作（Codex 的任务）

1. **DevKit 兼容回归**：对重写后的 handler 跑 DevKit C-S01~C-S11（DevKit 在 `G:/jiagou/projectmind-v1-devkit`）；旧缺 pin/空 map fixture 现在的正确行为是受控拒绝，不是恢复旧成功。
2. **S01–S30 oracle 覆盖扩展**：按 `ORACLE_MANIFEST.md` 补缺口——S15 完整正例、S17 多 owner、S18、S20–S25 变体矩阵、S29 独立 hash 断言、S26 排序变体。已有 99 测试覆盖大量条目但未逐项对账。
3. **真实 B/CA 集成 fixture**：B/CA 扩展不在本分支（TEAM 基座只有 map_proposal+project_summary）；等 owner 交付或建独立集成 worktree 后，把 mock validator 换成真实 `validate_context_pack` / `collect_code_facts` 双层测试。
4. **variants**：F18 无交叉信号、F19 动态依赖已有部分覆盖，补齐必要变体不减少矩阵项数。
5. **C self-validation** → fresh independent review → 达到 `C_CONVERGENCE_READY_FOR_HUMAN_REVIEW`。

## 7. 当前 tests

`cd G:/jiagou/projectmind-c-convergence && python -m unittest discover tests` → **99/99 OK（约 15s）**。Python 3.12。测试用 unittest；W3/W4 部分测试用真实临时 git 仓库（tempfile）。

## 8. known failures

无失败测试。但注意三类**预期行为变化**（不是回归）：
- 旧 TEAM 行为（隐式 HEAD、空 map 接受、mode+API key→ai_candidate、全文件 NODE_ADD）现在是受控拒绝/诚实状态。
- `S30` 无法 PASS：A30 共享 Host runtime SystemExit 隔离是 A/Core owner 的外部交付（见 §11 blocker），整体 gate 在此阻塞。
- B/CA 真实扩展未安装 → 运行时走 DEGRADED 路径，契约行为由 mock 双层测试保证。

## 9. C_CONVERGENCE_PLAN 路径

`G:/jiagou/C_CONVERGENCE_PLAN.md`（§8 oracle 表、§9 实施顺序、§10 验收 gate 是工作依据）。manifest 在 `G:/jiagou/projectmind-c-convergence/extensions/map_proposal/convergence/`。

## 10. next exact action

```
cd G:/jiagou/projectmind-c-convergence
python -m unittest discover tests          # 确认 99/99 基线
# 然后：跑 DevKit C-S01~C-S11 对账 → 修预期内的旧 fixture → 逐条补 S01-S30
```
每完成一个原子步骤：targeted tests → commit（`convergence: ...` 风格）→ normal push（**不要 force push**）。推送需走本地代理：`HTTPS_PROXY=http://127.0.0.1:7897 git push`。

## 11. 禁止事项

- 不修改 `extension_host.py`、B、CA registry、D、Core compare 的共享代码（S30 是 A/Core 的活）。
- 不做 UI，不开始 BCD 最终整合（C 未达 READY 前）。
- 不整体合并 PR #34、不整包复制 LOCAL C、不建第二个 map_proposal 注册/候选引擎/CA validator 策略/diff 口径。
- 不把 pack digest 当真伪认证、不把 demo map 当获批架构、不自动写正式地图、不输出 position、不宣称 ai_candidate。
- 不以 raw 输出定 expected、不迁移无效 CA fixture、不删 skipped/unresolved 断言凑绿。
- checkpoint 中 `main_modified=false`、`main_merged=false` 必须保持。

## 12. quota wait protocol

Codex 若返回 usage limit / quota exhausted / try again at HH:MM：
1. 立即保存 checkpoint（更新 `G:/jiagou/C_CONVERGENCE_OVERNIGHT_CHECKPOINT.json`）；
2. commit + push 已完成的原子工作（不留 dirty 半成品，除非明确记录到函数/行）；
3. 解析 reset 时间，等待 reset + 5 分钟；
4. fresh lightweight handshake（只回 `C_CONVERGENCE_CONTINUATION_READY`）；
5. 从 checkpoint `next_action` 继续，不重做已完成 W stage。
不要连续重试。
