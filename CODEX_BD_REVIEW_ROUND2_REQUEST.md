# CODEX_BD_REVIEW_REQUEST — 第二轮(修复复核)

致独立 reviewer(Codex):你是 REVIEW ONLY 角色。硬性规则与第一轮相同(READ ONLY;允许读取 repo root/tests/extensions/docs/verification/git;结尾必须给出 `CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`)。

## 本轮目标

第一轮审核(405d663)给出 FAIL,findings 与 ZCode 的修复记录见 `CODEX_BD_REVIEW.md`(内含逐条核验与修复映射)。修复 commit:`ccc30f0`。

请**独立复核**(不要只读修复说明):

1. **HIGH-1 复核**:handoff 带 workNotes 导出 → continuity import_packet 是否已恢复闭环?导出格式是否仍向后兼容?`extensions/continuity/model.py` 的过滤是否只影响导入路径、不改变导出行为?
2. **MED 惰性取件**:`extensions/continuity/inspection.py` git() 是否已钉住 `--no-lazy-fetch` + `GIT_NO_LAZY_FETCH`?旧版 git(退出码 129)是否有显式提示?行为是否与 B 的 facts.py 防护一致?
3. **MED 来源协议**:`remotes()` 是否同时携带 canonical `address` 与原始 `url`?config/capture 两处 sourceLocator 是否优先用原始 URL?canonical address 的相等性用途(inspection.py source_state 比较)是否未被破坏?
4. **LOW category 400**:worklog 非字符串 category 是否返回 400 而非宿主 500?
5. **harness 修复**:S3.4/S3.16/S15.1 是否已达到声称的覆盖?新增 S21.1–S21.4 是否真实构成回归防线?
6. **回归真实性**:`tests/test_bd_integration.py` 6 项新测试是否真实覆盖各修复?83 项 unittest(2 项 Windows 环境限制除外)与 63/63 harness ×3 轮结果是否可信?
7. **回归面**:修复是否引入新问题(D 原有 267+211+164 行测试是否仍全绿;有没有行为被意外改变)?

## 基准信息

- 分支 `integration/bd-v1` @ `ccc30f0`;第一轮审核基线 `405d663`。
- 你本轮仍可用:git log/diff/show、文件读取、只读 python(不写盘)。上一轮你已核验的 merge 拓扑/文件归属结论可复用,无需重复。
- GitHub PR 状态查询在你沙箱返回 401——与上轮相同,不作为缺陷。

## 输出

- 逐条复核结论(引用实际证据)。
- findings 按 BLOCKER/HIGH/MEDIUM/LOW 分级(含新发现)。
- 最后一行:`CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`
