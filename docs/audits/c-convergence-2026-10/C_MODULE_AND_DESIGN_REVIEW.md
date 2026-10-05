# C_MODULE_AND_DESIGN_REVIEW — 逐模組審查與設計級重思（審計任務 4/5/7/8/9/10）

> 對 convergence HEAD `78c2751` + 工作副本中兩處**未驗證**的未提交修改（見文末§dirty）的設計級審查。結論先說：實作的「安全邊界」部分基本成立，「有用性」部分明顯不足；W4 依用戶標準必須記 PARTIAL。

## §1 逐模組審查

### model.py — 請求/身份/提案原語
- **為何存在**：讓不合法請求無法被表達、讓提案構造期就攜帶不變式（K02）。
- **擁有的職責**：SHA/path 語法校驗、Core compare 顯式適配、地圖 intake、穩定 ID 推導、proposal 構造不變式（無 position、evidence 非空、kind 白名單）。
- **不該擁有卻擁有的**：`adapt_core_compare` 放在 model 是權宜——它是 A↔C 邊界的契約知識，長大後應獨立成 adapter 模組。
- **輸入事實來源**：全部來自呼叫端請求（不可信輸入），不讀環境。
- **隱含假設**：(a) SHA 只有 40/64 小寫 hex；(b) 路徑永遠是 POSIX repo-relative（反斜線整體拒絕）；(c) entryPoint 格式是 `path · func()`；(d) map 節點的 evidence 是 list[{path}]。
- **最可能錯的假設**：(c)。**entryPoint 解析是靜默的**——人類地圖若用別的書寫格式，`entry_lookup` 全空 → RESPONSIBILITY_CHANGE 永遠不觸發，且無任何診斷。這是「無聲降級」，違反 G-3 的精神。
- **介面變化時怎麼壞**：Core map schema 新增欄位 → 寬容（忽略多餘鍵）；改名 evidence→sources → intake 400 大聲失敗（可接受）；B/CORE 改用非 SHA 版本標識 → pin 閘門整體拒絕（大聲，但需先修）。

### facts_adapter.py — B 閘門
- **為何存在**：把「B 的事實可用性」從各通道的局部關注變成統一語義（R02）。
- **擁有的職責**：全路徑 revision 相等（supplied+installed 再釘）、形狀容錯政策（容器嚴格/條目寬容）、skipped 集合、path/domain eligibility 語義。
- **不該擁有的**：無明顯越權；eligibility 放這裡是對的（它是「B 事實」的語義）。
- **隱含假設**：(a) B 成功回傳必帶 revision（若 B schema 演化省略 revision → 我們硬拒——大聲，可接受）；(b) skipped 行必有 path——實作上無 path 的行會把 `undefined/None` 放進集合（無害但醜的疣）；(c) installed B 失敗時重試全樹收集——大 repo 有性能成本。
- **最可能錯的假設**：「容器壞=輸入錯誤→400，條目壞=B 演化→寬容」這條分界線。它是可辯護的政策而非契約明文；若 B owner 認為條目形狀也是契約，我們的寬容就是默許漂移。
- **介面變化時怎麼壞**：B 改為 dict-of-lists → `_normalize` raise → supplied 端 400、installed 端降級——大聲失敗，符合 G-1。

### analysis.py — 宣告/地圖/存在性通道
- **為何存在**：R01/R05 的語義落在這裡：kind 分派表、證據組裝、全域存在性證明。
- **擁有的職責**：rename→link、added→NODE_ADD（精度規則）、modified→職責/內部變化判決、stale-map 全路徑存在性、F20 抑制。
- **不該擁有的**：test/generated 命名啟發式放在這裡是政策選擇，若未來變複雜應外提為 policy 模組。
- **輸入事實來源**：diff（A）、B 宣告（target 供給/base 靠 installed B）、map（人類）、pinned tree（gitio）。
- **隱含假設**：(a) **節點的 evidence_paths == 職責域**——這是最重要的領域假設：人類在 evidence 裡掛「順便參考」的路徑時，R05 的刪除證明域和 R03 的關係域都會被污染（過寬→誤刪保護、過窄→漏證明）；(b) base 宣告只能來自 installed B——C-only 分支上 comparison 永遠不可用 → modified 通道靜默走「無比對」分支；(c) modified 在 map 域內且無比對可用 → no_proposal（見 §3 過度保守清單第 3 條）。
- **最可能錯的假設**：(a)。它沒有契約背書，是人類地圖使用習慣的假設。緩解：uncertainty 措辭已寫「map may be stale」；但更好是需要人類地圖語義的正式定義（TEAM owner 的領域）。
- **介面變化時怎麼壞**：B 若提供 diff-aware 的 base facts 供給方式，這裡的 installed-B-only 路徑要改；Core 若把 evidence 改成帶版本的引用，R05 反而變簡單。

### relations.py — import 關係通道（⚠ 工作副本有未驗證修改）
- **為何存在**：F05 的教訓：關係是獨立的分析層，證明必須是 AST 而非文本。
- **擁有的職責**：patch 候選信號、AST 證明、churn 語義、域級刪除證明、動態/相對形式的 UNKNOWN 路由。
- **不該擁有的**：無明顯越權（import 分析本就是 C 的推斷域，見 §B）。
- **隱含假設**：(a) 僅分析 .py；(b) module→路徑解析用「點分路徑 ∩ known_paths」啟發式——namespace package、src-layout、sys.path 技巧都會解析失敗；(c) **解析失敗 → 靜默 continue**。
- **最可能錯的假設**：(c)。這是全模組最嚴重的設計弱點：`resolve_module` 返回 None 時直接跳過，無 UNKNOWN、無 limits——違反 C-3/G-3 的精神（審計任務 9 實測：相對 import 1a/1b、`from pkg import b`（case 3）、多行 import（case 4）全部**無聲漏報**）。其中相對 import 的根因（驗證時 `lstrip('.')` 丟失相對性）與 from-import 信號展開已在工作副本修復**但未重跑測試**；多行 import 是信號提取器的結構性缺口，按審計紀律記錄不修。
- **介面變化時怎麼壞**：Git 輸出格式（-U0、rename 檢測）變化影響信號提取；Python 語法演化影響 AST（3.x 相容性由 ast 模組承擔）。

### ca_adapter.py — CA 信任邊界（W4）
- **為何存在**：S-2/E-4 的執行者：先驗證後消費、整包棄用、衝突路由。
- **擁有的職責**：validator 呼叫（自身 pin）、選擇層（current_by_scope only）、admission（衝突結構化路由、無附加預設）、欄位級驗證語義。
- **不該擁有的**：無；但「消費」職責整體缺席——見 §W4。
- **隱含假設**：(a) validator 從 `extensions.context_authority.context_pack` 可導入——本分支不存在 → 永遠 DEGRADED；(b) 衝突關聯性用詞邊界文本匹配 scope+key+value——scope 形如 `path:pkg/a.py` 有效；若真 CA 的 scope 是結構化物件 → 靜默不匹配 → 欠路由；(c) 「永不附加」是終態。
- **最可能錯的假設**：(c)。安全上它是對的極端，但產品上它是未完成——見 §W4 判決。
- **介面變化時怎麼壞**：真 validator 的例外類型/簽名變化 → 全部歸入「整包棄用」（大聲但可能過寬）；scope 格式需要 REAL_CA 對 tune（R16）。

### engine.py — 調度與 canonical 結果
- **為何存在**：單一決策路徑與單一發布出口（契約明文：不做兩套引擎 union）。
- **擁有的職責**：管線順序、通道接線、F20/CA admission 的時序、K03 投影、誠實 status。
- **不該擁有的**：`_legacy_candidates` 的投影邏輯放這裡勉強可以；status 詞彙表（degraded/empty/rule_candidate）是自創的——這是對外契約面，應與 DevKit/owner 對齊。
- **隱含假設**：(a) current_map 必填——「全新專案還沒有地圖」的產品流程契約未定義（X10 empty-map 被撤回是對的，但綠地請求的正確答案悬空）；(b) changed_paths 與 B wanted_paths 的交集策略（排除 removed/renamed-old）與真 B 的容錯行為匹配。
- **最可能錯的假設**：(a)——不是技術風險，是產品流程缺口，應列為 open question 交 TEAM owner。

### extension.py — seam
- **為何存在**：K01：保留 owner 語義的註冊面，內部全權委託單一調度器。
- **隱含假設**：ValueError=內部不變式破壞→500、RequestError/FactsMismatch=輸入錯誤→400。若未來把依賴失效也表達成 RequestError 子類，會把依賴問題偽裝成用戶錯誤——目前沒有，記為守則。

## §2 W4 判決：SAFE ≠ USEFUL+SAFE（審計任務 5）

**逐條對照用戶的五項要求**：

| 要求 | 現狀 | 判定 |
|---|---|---|
| 合法 verified claim 可安全消費 | 結構上不可能消費（任何 claim 都不進 evidence） | ✗ 未實現 |
| coherent poison 不能消費 | 結構上不可能（無附加路徑） | ✓ |
| conflict → HUMAN_REQUIRED | 已實現（結構化路由+詞邊界） | ✓ |
| unavailable → UNKNOWN/limits | 已實現 | ✓ |
| stale/非現行分區不作 current evidence | 已實現（只讀 current_by_scope） | ✓ |

**結論：W4 = PARTIAL**（防禦面完整，消費面為零）。不是推倒重來：正確路徑是在現有 admission 層上加「型別化消費白名單」——只允許 (a) 低影響、有明確用途的上下文 enrich（rationale 附近，帶 claim_id/scope/pack 回鏈，不支撐事實斷言），(b) verified_fields 明確覆蓋的欄位級事實支援，(c) 高影響主張的獨立核驗結果（有核驗才消費，無核驗維持現狀）。每開一類消費，對應 poison 測試必須同步證明該類仍不可偽造。

**全實作的過度保守清單**（SAFE vs USEFUL+SAFE 視角）：
1. CA claim 永不附加——SAFE✓ USEFUL✗（上表）。
2. **關係信號解析失敗靜默丟棄**（relations.py `resolve_module` None → continue）——既不 SAFE-useful 也不誠實，應產 UNKNOWN/limits。三個實測案例：相對 import、from-import 子模組、多行 import。（前兩個已在工作副本修，未驗證；第三個記錄未修。）
3. modified 在 map 域內、base 比對不可用 → no_proposal 無診斷——比「無聲降級」好一點（有 no_proposal 記錄），但 limits 裡沒有「為什麼」。應加 limits 診斷；是否升級為 unresolved 交 TEAM owner 決策（噪聲 vs 誠實的取捨）。
4. rename 源的關係變化被抑制（新路徑尚未在任何節點域）——保守有理（link change 未被接受前建關係是空中樓閣），但無診斷。可接受，記錄。
5. **正面的 USEFUL+SAFE 例子**（防止一邊倒）：函數型模組仍給低置信度 NODE_ADD（不被 class 門檻綁架）；B 不可用時 stale-map/非 python 分支照常運行；determinism 靠排序而非刪減資訊。

## §3 重新思考 CA（審計任務 7）

**應該被允許消費的 CA 主張分類**：
- **T1 上下文 enrich（低影響、帶回鏈）**：團隊焦點、遷移計劃、命名慣例等主張——可附加在 proposal 的 rationale 鄰近區，必須帶 claim_id/scope/pack_revision 回鏈，明確標註「context，不支撐事實」。
- **T2 欄位級事實支援**：dict 值 + live_verification.verified_fields 明確列出的欄位——該欄位可支撐該斷言；未列欄位不得（S22 語義）。
- **T3 高影響主張**：implementation./contract./PR 狀態——必須先有 C 的獨立 git/gh 核驗；核驗可用才消費核驗**結果**（不是 pack 自稱值）；不可用 → UNKNOWN。
- **T4 衝突行**：不是證據，是路由信號——相關候選轉 HUMAN_REQUIRED（已實現）。
- **T5 unavailable 行**：不是壞包，是「這個 key 的真相未知」——相關候選需要它時 → UNKNOWN/limits（已實現）。

**五個 CA 應該幫到 C 的真實場景**：
1. **地圖版本見證**：CA「最後一次地圖人工確認於 rev R」→ 彌補地圖無版本身身份的根本缺陷——C 的所有 map 相對判斷可以引用它作為適用性 UNKNOWN 的依據（這是 CA 對 C 最大的潛在價值）。
2. **爭議職責**：`owner.module.auth` 顯示 auth 模組歸屬有爭議 → C 的 NODE_ADD/RESPONSIBILITY 對該模組應降級或轉 HUMAN_REQUIRED（現在只有 conflict 行能觸發同效果）。
3. **入口真相**：verified claim「auth 的入口 = authenticate()」→ 為 RESPONSIBILITY_CHANGE 的候選替換提供獨立於 B 行號的錨點。
4. **慣例主張**：「tests/ 下靜態生成物非架構性」為 verified 慣例 → 餵給噪聲過濾器，避免硬編碼命名規則。
5. **變更意圖**：「module A 排期併入 B」→ C 的 NODE_REMOVE/NODE_ADD 引用它作為 context，人類裁決時有為什麼。

**如果答不出這些場景，W4 就只是「把 CA 關掉」**。現在能答出來，但實作尚未消費任何一類——再次確認 W4=PARTIAL。

## §4 重新思考 B（審計任務 8）

C 對 B 的依賴拆開看是三件事：
1. **target 宣告**（候選路徑上有什麼符號）——NODE_ADD/職責分析的事實錨。
2. **base 宣告**（之前有什麼）——職責變化偵測的 delta 基準。
3. **skipped 語義**（哪些路徑 B 明確說「我沒有事實」）——事實可用性邊界的真相標記。

**沒有 B 時仍能繼續**：stale-map 存在性（純 git tree）、rename link（diff+map）、非 python 噪聲過濾、pin/path 閘門。
**沒有 B 時必須 unresolved**：新增模組（無法驗證宣告存在）、職責變化（無 delta 基準）——實作正確（unresolved + 不虛構 code_fact）。
**C 絕不能自己補的**：宣告解析。因為 (a) B skipped 的含義是「這裡的事實基礎作廢」，C 自己解析等於繞過 B 的真相宣告，信任鏈斷裂；(b) 兩套宣告詞彙必然漂移（O-1）；(c) C 的輸出將引用「自己造的 code_fact」，證據回放斷裂。

**為什麼 import AST 不算複製 B**：B 的契約產品是「宣告（name/kind/line）」，明確**不含** import/呼叫圖/簽名。import 關係是 C 在自己的推斷域內、對 pinned blob 做的架構層分析——它的證據種類標 `git_diff`/pinned blob，不標 `code_fact`；它不重建 B 的產品（不產出宣告清單），也不與 B 的輸出矛盾。邊界一句話：**「存在哪些符號」是 B 的；「符號之間/檔案之間如何引用」是 C 的**。

## §5 重新思考 Map（審計任務 9）

地圖沒有版本身份 ⇒ **C 在原則上不可能知道「這份地圖適用於 target」**。所有 map 相對判斷的準確措辭是「相對於請求時提供的那份地圖」。
- **仍然允許的 proposal**：一切 diff×map 交叉信號——它們定義正確（相對於所給地圖），不依賴地圖的版本真值：NODE_ADD（地圖沒覆蓋新路徑）、rename link、RELATION_ADD（地圖聲稱的兩個域之間的新依賴）。
- **必須降 confidence/措辭**：NODE_REMOVE（「地圖可能過期」而非「節點已死」——已做）；RESPONSIBILITY_CHANGE（入口消失可能是地圖過期的症狀——uncertainty 已含）。
- **應該 unresolved 而尚未做的**：地圖適用性本身的 UNKNOWN。若 CA 能提供「地圖最後確認版本」見證（§3 場景 1），其缺失/不匹配應成為顯式 limits。目前只有 `map_has_version_identity: false` 的追蹤欄位——誠實但消費者難以行動。
- **絕不假設 target SHA == 地圖版本**（不變量 4）——這正是 S29/地圖 hash 斷言之外，最容易被產品壓力侵蝕的一條。

## §6 真實整合邊界（審計任務 10）

**CURRENT_BRANCH_IS_C_ONLY_CONVERGENCE。**

convergence 分支的基座 = TEAM C 分支（3bd980de）的祖先：Core（app.py/extension_host/compare）、project_summary、map_proposal。**B（code_facts）、CA（context_authority）、D（worklog/handoff/continuity）都不在分支上。**

因此以下結論只能叫 **component-level validation**，不得叫 integration validation：
- 全部 99 項測試 + 五缺陷探針（B 用 supplied facts / installed-B 用 mock；CA validator 用 mock/shim；HTTP 層未走）。
- W6 smoke（真 git 歷史 + 真地圖 + **fixture 側** facts）= real-data component smoke，**不是** B integration。
- S30（已實測 FAIL）。

真正的 integration validation 需要：真 B collector 在管線內（base facts 比對、wanted_paths 行為、真 skipped 語義）+ 真 CA validator 在管線內（schema 0.1 全 schema pack、scope 格式對 tune）+ Core route E2E（HTTP、七擴展共存）——分別對應 WHAT_REQUIRES_REAL_B / REAL_CA / CORE_FIX（見 DEEP_REASONING_CHECKPOINT）。

## §dirty 工作副本狀態（如實記錄）

`extensions/map_proposal/relations.py` 有兩處**未提交、未重跑測試**的修改（暫停指令到達前的最後動作）：
1. `imports_target` / `_imports_target_loose`：相對 import 候選不再 `lstrip('.')` 後解析（丟失相對性導致靜默漏報——對抗案例 1a/1b 的根因）。
2. `import_signals`：`from x import y` 形式展開 `x.y` 子模組候選（對抗案例 3 的根因）。
未驗證；下一步必須先重跑全套 + 對抗腳本再決定 commit 或 revert。多行 import（case 4）為結構性缺口，已記錄未修。
