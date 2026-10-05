# C_RISK_REGISTER — 風險登記簿（審計任務 11）

> 排序：BLOCKER → HIGH → MEDIUM → LOW。CURRENT_EVIDENCE 指今日（2026-10-04）審計中的實測/靜態證據。
> OWNER：A/Core=A 擴展 owner；B=B owner；CA=CA owner；TEAM=TEAM C owner（最終交付者）；NEXT=下一實作階段。

| # | 等級 | RISK | CAUSE | IMPACT | LIKEliHOOD | DETECTION | MITIGATION | OWNER | CURRENT_EVIDENCE |
|---|---|---|---|---|---|---|---|---|---|
| R1 | **BLOCKER** | runtime SystemExit 逃逸共享 Host；任一擴展 exit() 殺死 API server | `run()` 只 catch Exception（load 卻 catch SystemExit——邊界放錯層） | S30=FAIL；30/30 整體 gate 阻塞；生產可用性 | 高（依賴庫行為不可控） | 已實測復現（A30 探針） | Core `run()` 捕 BaseException → ExtensionError；C 不得內部 catch 代勞 | **A/Core**（已登記 D1） | 實測：SystemExit(7) 逃逸 host.run() |
| R2 | **HIGH** | CA 從不產生價值：「永不附加」= 把 CA 關掉 | W4 只建了防禦面，消費面（T1/T2/T3 型別化消費）未實作 | CA 整合的產品價值未證明；W4=PARTIAL | 確定（現狀即如此） | lattice 衝突/加強欄全由 conflict 行驅動 | 在 admission 層加型別化消費白名單，每開一類同步補 poison 反例 | TEAM（設計）+ NEXT | C_MODULE_AND_DESIGN_REVIEW §2 判決表 |
| R3 | **HIGH** | B 從未真正進入管線：base 宣告比對、wanted_paths、真 skipped 語義全部未在 vivo 驗證 | C-only 分支無 code_facts 擴展；supplied facts + mock 覆蓋契約面 | RESPONSIBILITY_CHANGE 正確性未證明；S13-S15 只算元件級 | 確定 | 分支清單（無 extensions/code_facts） | 建 integration worktree 接真 B；W6 型 smoke 重跑 | **B**（交付）+ TEAM | 分支實況；W6 smoke 用 fixture-side facts |
| R4 | **HIGH** | 關係信號解析失敗靜默丟棄 → 無診斷的假陰性 | `resolve_module` None → continue；信號提取器不支援多行 import | 相對 import/src-layout/多行 import 的關係全部漏報且無 UNKNOWN | 高（審計已實測 3 類） | 對抗腳本 1a/1b/3/4 | 相對性修復已做（未驗證）；多行需信號提取器結構性升級；所有解析失敗應產 UNKNOWN/limits | NEXT | audit_w3_adversarial 輸出 |
| R5 | **HIGH** | 「evidence 路徑==職責域」假設：人類在 evidence 掛參考性路徑 → R03/R05 的證明域失真 | 地圖語義無正式定義；C 把 evidence 域當職責域用 | NODE_REMOVE/RELATION_REMOVE 證明過寬或過窄 | 中 | 無（需人類地圖語義學） | 與 TEAM owner 確認地圖 evidence 語義；必要時按 evidence reason 欄位分權重 | **TEAM**（領域決策） | 模組審查 §analysis 假設 (a) |
| R6 | **HIGH** | DevKit C-S01~C-S11 未對新 handler 重跑 | 舊測試預期隱式 HEAD/全檔案 NODE_ADD；重寫為契約測試後未對帳 DevKit | 舊消費者/演示流程斷裂未被發現 | 高 | 未執行 | 跑 DevKit 對帳；舊 fixture 的正確新行為是受控拒絕 | NEXT | 檢查點缺口清單 |
| R7 | MEDIUM | relations.py 兩處修復未提交未驗證（相對 import、from-import 展開） | 暫停指令切斷在修復與驗證之間 | 工作副本 dirty；修復本身可能引入誤報 | 中 | git status | 先重跑全套+對抗腳本，再決定 commit/revert | NEXT | 工作副本 diff |
| R8 | MEDIUM | entryPoint 解析靜默失敗：格式不合 → RESPONSIBILITY 永不觸發、無診斷 | `parse_entry_point` 返回 (None,None) 被當正常 | 職責通道在格式漂移的地圖上整體失效而不被察覺 | 中 | 靜態分析 | entry_lookup 為空時產生 limits 診斷；或 intake 時警告 | NEXT | 模組審查 §model 假設 (c) |
| R9 | MEDIUM | CA 衝突關聯靠文本詞邊界：真 CA 的 scope 格式未對 tune | 結構化 scope 物件/其他前綴不匹配 | 相關衝突漏路由（欠抑制） | 中（取決於真 CA 格式） | 無 | REAL_CA 整合時用真 fixture 對 tune；unit 測試保留但標 MOCK | TEAM+CA | 模組審查 §ca 假設 (b) |
| R10 | MEDIUM | status 詞彙自創（degraded/empty/rule_candidate）與舊消費者期望錯位 | K03 投影保留了 candidates 但 status 語義變了 | DevKit/前端對 status 的分支邏輯失效 | 中 | DevKit 對帳（同 R6） | 與 owner 對齊詞彙表；投影層映射 | TEAM | W5 測試只斷言「不是 ai_candidate」 |
| R11 | MEDIUM | 地圖 intake 嚴格：人類 evidence 路徑含軟連結風格/越界書寫 → 400 | validate_path 對所有來源統一嚴格（S28 要求） | 現場真地圖可能被拒絕服務 | 低-中 | 無（需真地圖樣本） | 收集真實地圖樣本測 intake；錯誤訊息已具體可行動 | NEXT | validate_map 實作 |
| R12 | MEDIUM | 性能：ls-tree ×2/請求 + installed B 失敗時全樹收集 fallback | R05 全域存在性檢查；wanted-paths 失敗兜底 | 大 repo 上請求延遲/超時 | 中（小 repo 無感） | 無 | ls-tree 結果按 (repo,rev) 請求內快取已做；fallback 加上限/指標 | NEXT | gitio 實作 |
| R13 | LOW | skipped 集可能含 None（無 path 的行） | set-comprehension 不過濾非字串 | 無功能影響（changed∩skipped 不中）；集合含 None 是疣 | 低 | 靜態 | `_normalize` 過濾非字串 path | NEXT | facts_adapter 實作 |
| R14 | LOW | 多行 import 的單側 churn（加側在多行中被丟、刪側被捕）理論上可造成單向信號 | 信號提取器不支援多行（R4 的衍生面） | 極端書寫下的假 RELATION_ADD | 低 | 對抗腳本 case 4 衍生 | 隨 R4 的信號提取器升級一併處理 | NEXT | 邏輯推演 |
| R15 | LOW | proposal ID 含 proposed_change payload：同 subject 的候選因 payload 微調而換 ID | R06 的 payload 敏感設計（特徵非缺陷） | F20 抑制按 (subject,kind) 不受影響；但外部若按 ID 追蹤會看到換號 | 低 | 設計審查 | 對外文檔聲明 ID 語義；必要時 ID 與 payload 解耦 | TEAM | C_ID_MIGRATION.md |
| R16 | LOW | 綠地請求（尚無地圖）行為未定義 | current_map 必填（X10 撤回的連帶） | 新專案 onboarding 無法用 C | 低 | 產品流程未定義 | 交 TEAM owner 定義；或契約新增「無地圖」姿態 | **TEAM**（決策） | 模組審查 §engine 假設 (a) |

統計：BLOCKER 1、HIGH 5、MEDIUM 6、LOW 4。R1 未解決期間整體驗收 = BLOCKED_BY_A30。
