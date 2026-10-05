# C_TEST_STRATEGY — 測試策略設計（審計任務 12）

> 只設計不實作。核心原則先講清楚：**測試失敗時為什麼不能直接改 expected**——
> 契約推導的 expected 是整個系統唯一的固定點。失敗時改 expected，suite 就退化成「行為快照」：它驗證的不再是「實作符合契約」，而是「程式碼沒被改動」——任何回歸、任何安全漏洞都會被下一次 expected 更新合法化。合法的 expected 變更只有兩種，且都需要證據而非方便：(a) fixture 本身錯了（例：審計中 F05 探針的行號錯誤——修正的是 fixture，oracle 不變）；(b) 發現 expected 對契約條款推導錯誤（必須引用契約條款原文並在 review 中說明）。除此之外的每一次「改 expected 讓它過」都是一次 oracle 降級。

## 分層與每層要證明什麼

| 層 | 形式 | 證明目標 | 現狀 |
|---|---|---|---|
| **Unit** | 純函數對手工推導的 oracle（validate_path 邊界、ID 穩定性、eligibility、resolve_module） | 原語本身正確 | 部分有（W1）；resolve_module 的相對形式無 unit |
| **Contract（S-matrix）** | S01–S30 逐條，每條標 REAL/FIXTURE/MOCK/NOT_RUN | 實作符合共同契約（不是符合自己） | 覆蓋廣但未逐條對帳；這是下一階段的第一件事 |
| **Metamorphic** | 不看絕對輸出、看關係不變式：全樹 B ≡ changed-only B（無關節點集合相同）；請求內條目順序無關；重複請求位元組一致；base==target ⊆ 任何輸入的候選集為空 | 一類整體性質，防「對單一 fixture 過擬合」 | 3/4 有（全樹≡changed-only 缺） |
| **Mutation** | 臨時破壞每個 gate（禁 B revision 檢查、放行 skipped 關係、放行 claim 附加、禁 AST 證明、放行 position）→ 對應測試必須 FAIL | **測試本身有效**——證明測試真的綁在它聲稱保護的不變量上 | **未執行**（審計被暫停切斷）；這是評估「99 綠」含金量的關鍵缺失 |
| **Adversarial** | 對抗性輸入清單（相對/別名/多行 import、字串內 import 文本、註解、rename+關係、skipped+正常並存……），**先記錄後修復** | 實作在設計者沒設計的形狀下不產生錯誤輸出、不靜默吞掉 | 14 案已執行並記錄；發現 2 小 bug + 1 結構缺口 |
| **Integration** | 真 B collector / 真 CA validator 在管線內（真擴展、真 worktree） | 與依賴 owner 交付的接縫正確 | **未做**（C-only 分支）；全部標 MOCK |
| **Real-repo** | 對本 repo 真實歷史端到端（W6 型） | 真實資料形狀下不炸、發布不變式成立、確定 | 有 1 條 |
| **Cross-version** | 對 TEAM/LOCAL 凍結實作重放同一 fixture：old FAIL / new PASS | 修的正是當初的缺陷，不是新造的問題 | 5 缺陷全部雙側實測（audit_probes.py） |
| **Failure-injection** | B 拋例外/回錯 revision、validator 拋/缺、git 超時、擴展 SystemExit | 每種依賴失效走 G-1 定義的姿態 | 部分（B/validator 有；git 超時、SystemExit 有探針無正式測試——SystemExit 屬 Core） |

## 各層防的假綠不同（為什麼缺一不可）

- 只有 Contract → 防不了「expected 跟著實作寫」（測試與缺陷同構，F01 的教訓）。
- 加 Mutation → 防得了：破壞 gate 後測試仍綠 = 該測試是裝飾。
- 加 Metamorphic → 防得了「對單一 fixture 調參到綠」的過擬合。
- 加 Cross-version → 防得了「修了新造的問題、沒修原缺陷」。
- 加 Adversarial → 防得了「設計者想像力邊界外的靜默失敗」（今日 1a/1b/3/4 的教訓：**靜默漏報不會讓任何既有測試變紅**）。
- 標 REAL/FIXTURE/MOCK → 防得了「元件級驗證冒充整合驗證」（用戶審計任務 6/7 的要求）。

## 對下一階段的具體指令（不寫測試，只立規矩）

1. 先補 **Mutation 層**（4–5 個 gate 各一次），給現有 99 綠一個含金量證明。
2. 逐條對帳 **S-matrix**，產生帶 REAL/FIXTURE/MOCK/NOT_RUN 標籤的表格，放入 readiness 證據。
3. 補 Metamorphic 的「全樹≡changed-only」。
4. Adversarial 新案例照舊：先記錄，修復後**同一腳本**重跑留 before/after。
5. 任何 expected 變更：引用契約條款，寫進 commit message。
