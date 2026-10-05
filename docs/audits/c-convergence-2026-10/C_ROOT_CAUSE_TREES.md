# C_ROOT_CAUSE_TREES — 原始缺陷根因樹（審計任務 3）

> 每棵樹：SYMPTOM → IMMEDIATE CAUSE → DESIGN CAUSE → VIOLATED INVARIANT → WHY TESTS MISSED IT → 兩個「看似能修但其實錯誤」的方案 → PRINCIPLED FIX 需要什麼。
> 不變量編號見 C_REASONING_MODEL.md §3。

## F01 — TEAM diff×map 判斷缺失

- **SYMPTOM**：對 B 回傳的每個檔案發 NODE_ADD；已覆蓋、未變、註解/格式/helper 檔案照樣建節點；六類中五類不存在。（實測復現：map 已覆蓋 pkg/a.py 的 modified 檔案，TEAM 仍輸出 `['NODE_ADD']`——audit_probes.py F01）
- **IMMEDIATE CAUSE**：T.extension 遍歷 `code_facts.files` 直接產候選；`changed_paths` 與 `current_map` 被讀取但未參與任何候選決策。
- **DESIGN CAUSE**：C 被實作成「B 輸出的格式化器」，而不是「交叉比對引擎」——實作者心中沒有「地圖覆蓋」與「變化相關性」這兩個概念，自然寫不出分派邏輯。
- **VIOLATED INVARIANT**：C-1（候選由交叉信號定義）、E-3（把 B 事實當架構真值）、O-1（地圖這一層完全沒參與）。
- **WHY TESTS MISSED IT**：TEAM 的 happy-path 測試請求形狀與實作世界觀同構（只有 facts、沒有 diff/map 語義），斷言「有一個候選」而非「候選恰好是對的那個」；沒有任何測試餵入「map 已覆蓋的路徑」並斷言**不**出節點。弱測試與缺陷同源。
- **BAD FIX A**：`if (path in changed_paths) 才 NODE_ADD`——只檢查了 diff 軸，仍然無視地圖覆蓋；對「已覆蓋路徑的小修改」照樣誤報，且 rename 語義完全缺失。
- **BAD FIX B**：保留全檔案 NODE_ADD，但 confidence 一律 low + uncertainty 加長——表面上更誠實，實際把裁決成本全推給人類；噪聲即傷害，且違反 C-1（候選仍非交叉信號定義）。
- **PRINCIPLED FIX**：候選類型由「變化狀態 × 地圖覆蓋 × 宣告事實」的交叉唯一決定（R01 分派表）；每通道獨立運行；非信號輸出帶原因的 no_proposal。落地於 analysis.py；殘餘風險見 C_MODULE_AND_DESIGN_REVIEW.md §analysis。

## F02 — TEAM CA validation 不完整

- **SYMPTOM**：同 SHA 的缺欄位 pack 被接受；conflict 進了 limits 但相關候選不受影響。（實測：pack 僅憑 `project_revision==target` 就被消費，候選照常輸出——audit_probes.py F02）
- **IMMEDIATE CAUSE**：T.extension 只做 `pack_rev != target → drop` 與枚舉 conflict 進 limits/unresolved；沒有 validator 呼叫、沒有候選閘門。
- **DESIGN CAUSE**：CA 被當成「展示性註釋」而非「帶信任邊界的證據來源」；「驗證」被縮減為 revision 相等。
- **VIOLATED INVARIANT**：S-2、E-4、G-1（pack 失效無定義姿態）。
- **WHY TESTS MISSED IT**：沒有測試餵入 validator 必拒的 pack（同 SHA 缺欄位）並斷言拒絕；conflict 測試只斷言「conflict 被列出」，沒斷言「相關候選被阻斷」。
- **BAD FIX A**：C 自己寫一套深欄位檢查——與 CA owner 的 schema 漂移，且契約明文禁止「兩套 CA validator 策略」。
- **BAD FIX B**：關鍵字黑名單過濾可疑 value——正是 LOCAL F03 的教訓（見下），連貫偽造輕鬆繞過。
- **PRINCIPLED FIX**：呼叫真 validator（C 自己的 pin），失敗整包棄用；消費走型別化準入（用途+欄位級驗證+獨立核驗）；conflict 結構化路由到相關候選。P01+R04。

## F03 — LOCAL coherent poison 進入 evidence

- **SYMPTOM**：validator-pass、中性 key（`team.focus.v1`）、value="PR 35 is CLOSED" 的主張被附加到第一個 proposal 的 evidence，標 UNVERIFIED。（實測復現：用凍結 CA builder `build_context_pack` 造真 pack，LOCAL engine 確實附加——audit_probes.py F03 old=True）
- **IMMEDIATE CAUSE**：`_apply_context_claims` 的 supplement 邏輯：第一個通過 `_is_high_impact_claim` 黑名單掃描的 claim 附到 `proposals[0]`。
- **DESIGN CAUSE**：信任決策建立在「偽造在詞彙上可偵測」的假設上（黑名單），並假設「claims 一般有用」而無逐條用途審查。兩個假設都錯：偽造可以是任意新措辭；無用途的附加只是注入面。
- **VIOLATED INVARIANT**：S-2、E-4、（G-2 仍確定，但確定地錯）。
- **WHY TESTS MISSED IT**：LOCAL 自己的測試斷言「高影響關鍵字被拒」——威脅模型與防禦同構（都是關鍵字）；中性 key + 連貫偽造在測試集之外；弱斷言只查「無 crash / 高影響未附」。
- **BAD FIX A**：加長黑名單（"closed"/"open"/PR 編號/SHA 形……）——軍備競賽；合法主張被誤殺、新穎措辭照樣通過；且這正是「把安全修復做成更長關鍵字黑名單會再次繞過」的計劃原文警告。
- **BAD FIX B**：照樣附加但加更醒目的 UNVERIFIED 警示——標籤不降低虛假度；下游把「存在於 evidence」當支援，警示文字沒有語義效力。
- **PRINCIPLED FIX**：預設拒絕附加；claim 進 evidence 需型別化用途 + 欄位級驗證 + 高影響事實獨立核驗（E-4 三條件）。W4 落地了「預設拒絕」這一半；**消費那一半未做 → W4=PARTIAL**（見 C_MODULE_AND_DESIGN_REVIEW.md §W4）。

## F04 — LOCAL skipped 檔案關係誤報

- **SYMPTOM**：B skipped 的變化源同時產生 unresolved 與 RELATION_ADD。（實測：old kinds=['RELATION_ADD'] + unresolved 含該路徑；new 兩者只剩 unresolved——audit_probes.py F04）
- **IMMEDIATE CAUSE**：skip 過濾只在檔案 handler 裡做；`relation_paths` 的收集沒有排除 skipped。
- **DESIGN CAUSE**：eligibility 被當成「各通道自己的局部關注點」，而非「證據域的屬性」。缺一個統一的事實可用性閘門，每加一個通道就多一個能漏的地方。
- **VIOLATED INVARIANT**：E-3（skipped 毒化整個依賴子樹）、C-1。
- **WHY TESTS MISSED IT**：LOCAL 的 skip 測試只覆蓋檔案通道；關係測試用的都是非 skipped 源。測試形狀沿著實作的分層走，而不是沿著不變量走。
- **BAD FIX A**：只在 `relation_paths` 收集處補一個過濾——下一個新通道（如未來的簽名通道）照樣漏；補丁摞補丁。
- **BAD FIX B**：把 skipped 的 unresolved 拿掉讓輸出「一致」——把人類任務藏起來，比誤報更糟。
- **PRINCIPLED FIX**：統一 eligibility 原語（`path_eligibility` / `domain_eligibility`），每個通道在把任何路徑變成強候選證據**之前**必須詢問；skipped → 一次 HUMAN_REQUIRED + 全通道禁入。

## F05 — LOCAL 真實 import 漏報

- **SYMPTOM**：宣告位元組不變 + 真實跨節點 import 新增/刪除 → 空結果。（實測：import 加在 class **後**、宣告完全不變時，old kinds=[]；new kinds=['RELATION_ADD']——audit_probes.py F05。注意 fixture 紀律：import 加在 class 前會造成行號漂移，LOCAL 反而會報——這正是 X01 原始 fixture 用「class 後」的原因）
- **IMMEDIATE CAUSE**：`_handle_modified` 用「宣告列表相同」標記 declaration_unchanged；`relation_paths` 排除這些檔案。
- **DESIGN CAUSE**：一個通道的裁決（宣告沒變）被當成整個檔案分析的裁決——通道獨立性在架構上就不存在；宣告比對被誤用為「有沒有值得分析」的代理。
- **VIOLATED INVARIANT**：C-2（通道獨立）、E-3。
- **WHY TESTS MISSED IT**：LOCAL 的 F2/F3 測試裡 import 變化總是伴隨宣告變化或行號漂移——沒有 fixture 把「宣告位元組不變」單獨隔離出來。測試沒有對準不變量 C-2。
- **BAD FIX A**：拿掉 declaration_unchanged、永遠跑關係通道，但證明仍靠 regex——docstring/字串/註解的 import 文字全部湧入（F06），recall 的修復變成 precision 災難。
- **BAD FIX B**：用 import 計數比對取代宣告比對作為閘門——用文字計數重做依賴分析，仍然是文本層證據，解析失敗當零的坑還在。
- **PRINCIPLED FIX**：通道獨立 + 任何關係主張必須對 pinned blob 做 AST 證明（regex 只能當候選信號提取器）。落地於 relations.py；殘餘缺口（相對 import、多行 import 的靜默漏報）見 checkpoint。

## F12 / A30 — 共享 Host runtime SystemExit 隔離

- **SYMPTOM**：擴展執行期拋 SystemExit 直接逃出 `host.run()`。（實測：注入 `raise SystemExit(7)` 的擴展，SystemExit 帶 code=7 逃逸；正常 Exception 被隔離為 500；之後的健康路由在新呼叫中可達——A30 探針，2026-10-04）
- **IMMEDIATE CAUSE**：`ExtensionHost.run()` 只 `except Exception`。
- **DESIGN CAUSE**：隔離邊界只放在 load 時（load 處確實 `except (Exception, SystemExit)`），呼叫時沒有；把「載入不受信任程式碼」與「執行會犯錯的程式碼」混為一談。
- **VIOLATED INVARIANT**：G-1（Host 層的失效姿態缺失）；七擴展共存保證。
- **WHY TESTS MISSED IT**：既有測試只注入普通 Exception 或只測 load 階段；沒有人從 runtime 路由注入 BaseException。
- **BAD FIX A**：C 在自己的 handle 裡 catch SystemExit——只保護 C 的路由；其他擴展照樣裸奔，且用 C 的內部 catch 掩蓋共享缺陷，計劃 §10.6 明文禁止。
- **BAD FIX B**：寫入規範「擴展不得拋 SystemExit」——約定不是隔離；一個依賴庫的 exit() 就能殺死整個 API server。
- **PRINCIPLED FIX**：`run()` 捕獲 BaseException（至少 SystemExit）轉 ExtensionError。這是 Core 的改動，owner 是 A——已登記為 D1 外部阻塞，整體 gate 在此阻塞（S30=FAIL，實測證實）。
