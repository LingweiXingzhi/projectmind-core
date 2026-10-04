# C_MVP_FINAL_REPORT — Map Proposal v0.1

- 日期:2026-10-04(3 小时恢复窗口);分支 `feat/map-proposal-mvp`;worktree `G:\jiagou\projectmind-map-proposal`

## 第一屏

```
STATUS:        IMPLEMENTED_SELF_VALIDATED;C_CODEX_REVIEW = FAIL→FIXED,PENDING_RE-REVIEW(两轮审计 findings 全部修复并固化为回归;§12 复审上限已用,未再审计)
C_HEAD:        见 git log feat/map-proposal-mvp
BD_BASE:       integration/bd-ca-c-base @ f43dcaf(BD gate = Codex PASS_WITH_LIMITS @ a71c508 + CA merge)
CA_BASE:       PR #29 @ 9ea2349(实时复核仍为 validated head;merge 零冲突)
TESTS:         C 专项 51/51 PASS(含 8 项审计探针回归);全仓 297 项 = 295 PASS + 2 项 PR31 既有 Windows 环境限制错误(失败集 md5 不变)
ACCEPTANCE:    F1-F20 全部落地 + C-A21..A30 补齐(multi-scope/partial-verified/verifier-unavailable/
               coherent-poison/invalid-pack-degraded/B-revision-mismatch/B-skipped/contract-drift/
               conflict-HUMAN_REQUIRED/map-version-unknown)
BLOCKERS:      无
HIGH:          无
LIMITS:        见下
```

## 实现范围(Stage 0–4,离线可用形态)

`extensions/map_proposal/`:
- `model.py` — SuggestMapRequest/Result 契约校验(完整 SHA、changed_paths ≤2000、路径安全、map 结构、prior_decisions)
- `diff_model.py` — import 行信号抽取(仅读 patch 文本;`--no-lazy-fetch` + GIT_* 环境防护与 B/Core 同款)
- `facts_adapter.py` — B 消费:唯一运行时断言 `CodeFacts.revision == target_revision`(不等→整请求拒绝);
  请求内 facts 形状漂移→容忍为 unavailable(C-A28);进程内全树收集(removed 路径不毒化调用);skipped 永不作为事实
- `ca_adapter.py` — CA 五步协议:PIN(自定 expected_revision)→VALIDATE(失败=整包拒绝→DEGRADED_NO_CONTEXT)→
  SELECT(只读 current_by_scope;conflict/unavailable 键永不入证据)→EVIDENCE(verified_fields 字段级核对)→RECORD
- `engine.py` — 确定性规则引擎:6 种 kind(NODE_ADD/RELATION_ADD/RELATION_REMOVE_CANDIDATE/
  IMPLEMENTATION_LINK_CHANGE/NODE_REMOVE_CANDIDATE/RESPONSIBILITY_CHANGE)+ unresolved/no_proposal/limits;
  false-positive 控制(test-only/generated/helper-only/comment-format-internal/同职责内部变更不建节点);
  证据链 ≥1 条且可定位 (revision,path);proposed_change 永不含 position;status 恒 PROPOSED、human_required 恒 true
- `extension.py` + `index.html` — GET 能力页 / POST suggest / POST schema;调试视图用 textContent 渲染(无 HTML sink)

三处歧义定案(`C_V0_1_RESOLVED_SEMANTICS.md`):F1' 无 B 降级不伪造 code_fact;P05 相干伪造与结构无效拆分
(C-A24/C-A25);invalid pack→整包拒绝+DEGRADED_NO_CONTEXT+高影响缺口落 unresolved。

## 安全摘要

- 输入:revision 强制完整 SHA;路径拒绝 `..`/反斜杠/绝对路径/UNC/控制字符;数量与长度上限
- 无任意文件读:仅 repo-pinned git(diff/rev-parse);无任何命令执行面;恶意文本只作为数据流经(JSON 输出 + textContent)
- CA:digest≠真相(相干伪造由 evidence-fallback 交叉核对拦截,见 C-A24);conflict→HUMAN_REQUIRED 不选边

## 已知边界(LIMITS)

1. RELATION 信号来自 git diff 的 import 行,模块→路径解析仅对"已知路径集"(地图证据域∪变更集∪facts 文件)内目标生效;
   解析不到的 import 静默计数,不产噪。
2. 职责类判断(RESPONSIBILITY_CHANGE/NODE_ADD summary)恒为 INFERENCE 标注,置信度 ≤medium。
3. 进程内 B 全树收集在 >2000 文件/16MiB 仓库会触发 B 上限→自动降级 unavailable(limits 注明)。
4. C 不做 Stage 5(accept/reject 落盘)与 Stage 6(A 集成渲染)——本轮范围外。
5. index.html 为调试视图,不做统一 UI(用户已确认 UI 收拢另行处理)。

## 验证明细

| 套件 | 结果 |
|---|---|
| `tests/test_map_proposal.py`(38 项) | F1–F20(13 用例覆盖)+ C-A21..A30(10 项)+ 降级/安全 4 项 + 确定性 2 项 + ExtensionHost 集成 4 项 → 全 PASS |
| 全仓 `python -m unittest discover -s tests` | 284 项:282 PASS + 2 env-limited(PR31 既有,md5 不变) |
| 确定性 | 同输入双跑 JSON 字节一致;proposal_id 稳定(mp-<target8>-NN) |

## Codex C 审计(两轮,全部真实调用)

- R1(compact,dea111f,~64k tokens):**FAIL,2 HIGH + 5 MEDIUM**——H1 相干伪造可穿透(探针实证书过 validator)、
  H2 conflict 路由不完整、M1 证据版本绑定、M2/M3 关系误报、M4 B 部分漂移崩溃、M5 测试名实不符。
- 修复(5286697):高影响 claim(implementation./contract. 前缀、status/head/merged 类字段、SHA 形文本)一律
  不入 evidence→unresolved HUMAN_REQUIRED;conflict 相关候选按路径+节点 id(词边界)移入 unresolved;
  改名/删除证据绑定正确 revision;声明未变文件排除关系抽取;churn 过滤;git show 复核改 AST 精确计数;
  B 部分漂移容忍;测试强化(真实函数体重构/文档字符串 import/churn/证据绑定/部分漂移)。
- 复审(compact,仅 findings+修复 diff+测试):**FAIL,2 HIGH + 3 MEDIUM 残留**——H1 绕过形态
  (值文本含 MERGED/SHA 但键名 innocuous)、H2 关系候选未路由+node-api 子串误伤、churn 过滤顺序、
  AST 前 docstring 误计、M5 部分测试仍弱。
- 二次修复(当前 HEAD):H1 改为默认怀疑的全文本扫描(token+SHA 正则);H2 词边界匹配 + from/to/证据路径
  路由;churn 交集先算;static_import_count 改 AST 计数;新增 8 项探针回归(Codex 全部探针固化为测试)。
- **状态:C_CODEX_REVIEW = FAIL(2 轮)→ 修复已落地并自验(51/51 + 全仓 297 = 295+2 env-limited),
  复审未再执行(§12 一次 follow-up 上限已用)。C 未获 Codex PASS;是否追加审计轮由用户决定。**
