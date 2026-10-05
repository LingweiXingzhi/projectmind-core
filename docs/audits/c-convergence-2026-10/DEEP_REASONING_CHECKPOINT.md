# DEEP_REASONING_CHECKPOINT — 深度推理檢查點（2026-10-04，T+90 前）

> 純分析階段的收尾輸出。此後 STOP，等待決策；不自動繼續寫碼。
> 狀態重定義：**C_CONVERGENCE_IMPLEMENTATION_DRAFT_COMPLETE / ACCEPTANCE_NOT_YET_PROVEN**。
> 評級：**BLOCKED（BLOCKED_BY_A30）**，元件級 PARTIAL——詳見 C_SELF_AUDIT_REPORT.md。

## TOP_5_DESIGN_RISKS

1. **A30 共享 Host 隔離缺失（R1）**——實測 SystemExit 逃逸 `run()`。這不是 C 能修的；整體 gate 阻塞於此。任何「C 內部 catch 掉 SystemExit」的修法都是掩蓋證據，禁止。
2. **CA 無價值路徑（R2）**——W4 的「永不附加」是正確的極端安全，但等於把 CA 關掉。設計風險在於：如果不先定義「型別化消費白名單」（T1 上下文 enrich / T2 欄位級支援 / T3 獨立核驗後消費），CA 整合永遠停在「安全但無用」，而壓力會把實現推向另一個極端（恢復黑名單式附加）——那正是 F03。
3. **關係通道的「解析失敗→靜默丟棄」模式（R4）**——設計層的錯不在某個 bug，而在信號選擇層沒有 UNKNOWN 出口。只要這個模式在，每一種未支援的 import 形式都是一個無聲假陰性（今日實測 3 類）。
4. **evidence 路徑==職責域假設（R5）**——R03/R05 的全部證明力建在人類地圖的 evidence 語義上，而這個語義沒有正式定義。這是領域決策（TEAM owner），不是程式問題。
5. **B 從未在管線內（R3）**——base 宣告比對（RESPONSIBILITY_CHANGE 的根基）只在 mock 下存在；「B skipped 的真實語義」「wanted_paths 的真實容錯」全部未 vivo 驗證。

## TOP_5_UNPROVEN_ASSUMPTIONS

1. 地圖節點的 `evidence_paths` 等於該節點的職責域（R05 刪除證明、R03 關係域的地基）。
2. 人類地圖的 entryPoint 一律是 `path · func()` 格式（否則職責通道靜默失效）。
3. B 的容錯分界線：容器壞=拒絕、條目壞=寬容——是雙方共識而非 C 單方面政策。
4. 詞邊界文本匹配能承載真 CA 的 scope→候選關聯（真 CA scope 格式未見）。
5. Core map schema（`{note,nodes,edges}` + `evidence[{path}]`）在整合期保持穩定（intake 是嚴格 400）。

## CURRENT_IMPLEMENTATION_WEAKNESSES

- W4 消費面為零（PARTIAL）。
- relations.py：解析失敗靜默；多行 import 無信號；**兩處修復（相對 import 相對性、from-import 展開）在工作副本未提交未驗證**。
- RESPONSIBILITY：base 比對不可用時 no_proposal 無診斷（誠實降級缺口）。
- status 詞彙（degraded/empty/rule_candidate）自創，未與 DevKit/owner 對齊。
- 綠地請求（無地圖）行為未定義；性能上 ls-tree ×2/請求 + installed-B 全樹 fallback 無上限。
- model.adapt_core_compare 的位置（應為獨立 adapter）；facts_adapter skipped 集可含 None（疣）。

## CURRENT_TEST_WEAKNESSES

- **Mutation 層完全缺失**——99 綠的含金量未證明（破壞 gate 後測試是否變紅沒有證據）。
- S-matrix 未逐條對帳（今日補了靜態對帳表，但那是自審產物，不是獨立 suite 的產物）。
- 缺 metamorphic「全樹 B ≡ changed-only B」；缺 resolve_module 相對形式的 unit；handler 層的 400/500 映射無直接斷言；S08/S12/S17/S18/S27 變體缺口（見矩陣）。
- 全部測試=component-level；REAL/FIXTURE/MOCK 標註制度是今日才建立的，此前 99 綠容易被誤讀為整合驗證。

## WHAT_I_WOULD_NOT_SHIP

- 任何「30/30 / READY / W0-W6 COMPLETE」的表述。
- ca_adapter 以現狀標 COMPLETE（只能標：安全邊界完成、消費面未做）。
- 未重跑測試的 relations.py 修復。
- 「解析失敗靜默」的信號選擇模式。
- 未與 owner 對齊的 status 詞彙。

## WHAT_REQUIRES_REAL_B

S13 真 collector 語法壞源 skipped；base 宣告在管線內（S06 vivo）；wanted_paths 真容錯；S15 有 collector 時的降級正例；W6 型 smoke 換真 facts 重跑。

## WHAT_REQUIRES_REAL_CA

S19–S25 對 schema 0.1 全 schema pack 的真 validator 雙層測試；scope 格式對 tune（R9）；pack metadata 回鏈正確性；S23/S24 真 verdicts。

## WHAT_REQUIRES_CORE_FIX

S30：`run()` 捕 BaseException→ExtensionError（A/Core owner，D1）；七擴展共存與 route E2E 正式測試；（附帶）load 與 run 的隔離語義統一。

## WHICH_W_STAGE_WAS_OVERCLAIMED

- **W4 最被高估**：commit message 與 manifest 都寫「implement W4 CA trust boundary」——實為「信任邊界的防禦半邊」。按用戶標準=W4 PARTIAL。
- **W3 次之**：在對抗測試前自稱完成；對抗發現 3 類靜默漏報（2 類已定位修復未驗證，1 類結構性未修）。
- **W6 名過其實**：real-diff smoke 是「real-data component smoke」，不是 integration validation（facts 是 fixture 側）。
- W0/W1/W2/W5 的表述與實質基本相符（W2 的證明域假設 R5 是殘留設計風險）。

## 交接狀態（供下一步決策，未動手）

- 分支 `integration/c-convergence-v1` @ `78c2751` 已推送；**工作副本 dirty**：relations.py 兩處未驗證修復。
- `G:/jiagou/C_CONVERGENCE_OVERNIGHT_CHECKPOINT.json` 與 `CODEX_C_CONVERGENCE_CONTINUATION.md` 寫於自審**之前**，其「W0-W6 完成」表述需按本檢查點改寫後才能交 Codex；未改，等待決策。
- 審計產物（7 份 .md，均在 G:/jiagou/，未提交）：C_REASONING_MODEL / C_ROOT_CAUSE_TREES / C_MODULE_AND_DESIGN_REVIEW / C_EVIDENCE_LATTICE / C_RISK_REGISTER / C_TEST_STRATEGY / C_SELF_AUDIT_REPORT。

**STOP。等用戶決策後再繼續。**
