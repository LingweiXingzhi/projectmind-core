# C Convergence — Source Manifest (W0)

实施依据: `G:/jiagou/C_CONVERGENCE_PLAN.md`（本目录所有 manifest 的唯一上游）。

## 1. Frozen Heads

| 对象 | 冻结标识 | 用途 |
|---|---|---|
| TEAM C | `3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`; branch `feat/role-c-map-proposal`; PR #35; owner `bjtxcy` | C 的交付与治理 baseline；本分支 `integration/c-convergence-v1` 的起点 |
| TEAM C fixed base | `7484d44ddeac3c054ca3ba68f92293d965bb615c` | 识别 TEAM C 自身改动 |
| LOCAL C | `5058c54aa52243c15b286a4922a362c48c941967`; branch `feat/map-proposal-mvp`; PR #34 | 独立参考与选择性移植来源 |
| LOCAL C-only base | `f43dcaf85141a72265e14946c10fee627e3cc7be` | 排除 LOCAL 祖先中的 B/D/CA 交付 |
| 共同契约文档 | `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa` | 唯一产品契约来源 |
| B 对照接口 | PR #31 @ `80e091acefd278fda03e188a125147b0aa5eedc5` | 实际 Code Facts 消费边界 |
| CA 对照接口 | PR #29 @ `9ea23491d1849f21bad9f60c1c1ca8df55bb5936` | 实际 Context Pack validator/resolver 边界 |

## 2. Frozen Source Roots（只读；行号/符号均对应这些冻结版本）

- TEAM_ROOT = `C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/team/LingweiXingzhi-projectmind-core-3bd980ded7a9cc727c1f00c84cf3c2b89c574e40`
- LOCAL_ROOT = `C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local`
- T.extension = TEAM_ROOT/extensions/map_proposal/extension.py
- L.model = LOCAL_ROOT/extensions/map_proposal/model.py
- L.facts = LOCAL_ROOT/extensions/map_proposal/facts_adapter.py
- L.ca = LOCAL_ROOT/extensions/map_proposal/ca_adapter.py
- L.diff = LOCAL_ROOT/extensions/map_proposal/diff_model.py
- L.engine = LOCAL_ROOT/extensions/map_proposal/engine.py

## 3. 冻结证据文件（SHA-256）

| 文件 | SHA-256 |
|---|---|
| PROJECTMIND_C_DUAL_IMPLEMENTATION_REVIEW.md | `1c3ce67f8b4bd404c8319362281a4e828b25945354655ec34f969dc4874b8f6c` |
| dual_results.json (58 条原始记录) | `6a14d1a09affb8ffabf092debc7876a90dd4ee337df160c349e33374c2921483` |

## 4. 决策映射

- KEEP_FROM_TEAM: K01–K04（见 PORT_MANIFEST.md）
- PORT_FROM_LOCAL: P01–P09（见 PORT_MANIFEST.md）
- REIMPLEMENT: R01–R07（见 PORT_MANIFEST.md）
- DROP_FROM_TEAM: T01–T06；DROP_FROM_LOCAL: L01–L12（见 PORT_MANIFEST.md）

冻结结论 NEITHER_READY / CONFIDENCE=HIGH 不因本分支改变。PR OPEN/Draft 状态是历史观察；未来实现需要的外部事实必须重新独立核验。

## 5. Integration Branch

`integration/c-convergence-v1` 起点为 TEAM C frozen HEAD `3bd980de`。C 实施范围限定: `extensions/map_proposal/`、C contract/集成测试、必要 C 消费者文档。共享 A/B/D/CA 依赖由各 owner 独立交付，不在本分支修改 `extension_host.py`。
