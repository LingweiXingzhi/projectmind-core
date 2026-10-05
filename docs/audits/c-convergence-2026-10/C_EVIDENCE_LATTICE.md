# C_EVIDENCE_LATTICE — 每種結論的證據格（審計任務 6）

> 每種 kind 一張 decision table：最低證據條件 / 加強證據 / 衝突證據 / 禁止證據 / UNKNOWN 條件。
> 「✓已落地」指 convergence HEAD 的現狀；「△」=部分；「✗」=未落地或違反。

## NODE_ADD

| 欄位 | 內容 | 落地 |
|---|---|---|
| 最低條件 | changed(added) ∧ 路徑不在任何節點 evidence 域 ∧ B 對該路徑有合格宣告（eligible）∧ 非 test/generated 噪聲 ∧ 非 skipped | ✓ |
| 加強證據 | 唯一頂層 class（可給 entryPoint）；多宣告（結構化列舉）；diff+fact+map 三源齊備 | ✓ |
| 衝突證據 | CA conflict 觸及該路徑/節點 → 轉 HUMAN_REQUIRED；B skipped → 整體失格 | △（skipped✓，CA conflict ✓ 但僅 conflict 行） |
| 禁止證據 | position；未驗證 claim 作為職責依據；「B 有檔案」單獨作為理由；首個 class 自動當入口 | ✓ |
| UNKNOWN 條件 | B 不可用 → unresolved（不虛構 code_fact）；B 無條目 → unresolved（不等於架構上不存在） | ✓ |

## RELATION_ADD

| 欄位 | 內容 | 落地 |
|---|---|---|
| 最低條件 | 真實新增 import（**AST 證明於 target blob**）∧ 兩端各有 map 節點域 ∧ 兩域不同 | ✓（AST 證明） |
| 加強證據 | 兩端均單一 owner（→medium）；證據含兩端節點的域宣告 | ✓ |
| 衝突證據 | 任一端 skipped → 失格；CA conflict 觸及任一端節點 → 轉人類 | △（skipped✓；conflict✓） |
| 禁止證據 | regex 文本單獨作證；同域自邊；動態 import 直接建邊 | ✓ |
| UNKNOWN 條件 | 動態 import → HUMAN_REQUIRED；**blob 讀取/解析失敗 → limit+unresolved**；**解析器無法解析的形式（多行 import、未支援相對形式）→ 目前靜默丟棄 = 違反本格**（已在工作副本部分修復，未驗證） | ✗→△ |

## RELATION_REMOVE_CANDIDATE

| 欄位 | 內容 | 落地 |
|---|---|---|
| 最低條件 | 刪除 import 信號 ∧ **已存在的 map edge** 連接兩域 ∧ 域級證明：source 節點域內全部 .py 對 target 域的 import 於 target 全消失、於 base 至少一處存在 | ✓ |
| 加強證據 | 單檔案域（證明域=全域天然成立）；單一 owner | ✓ |
| 衝突證據 | 任一域檔案 skipped → 失格；同 (file,module) 於同一 diff 既加又刪（churn）→ 兩邊一起作廢 | ✓ |
| 禁止證據 | 單一檔案的 import 計數歸零當全域證明；B available 與否作為門檻 | ✓ |
| UNKNOWN 條件 | 域內任一檔案讀取/解析失敗 → 整個候選不出（UNKNOWN≠零） | ✓ |

## IMPLEMENTATION_LINK_CHANGE

| 欄位 | 內容 | 落地 |
|---|---|---|
| 最低條件 | rename（R 碼）∧ old 在某節點域內 ∧ new 不在任何域 | ✓ |
| 加強證據 | B 對新路徑的宣告；old@base + new@target 雙側 diff 證據 | ✓ |
| 衝突證據 | 多 owner → low confidence + ambiguity uncertainty | ✓ |
| 禁止證據 | 對新路徑發 NODE_ADD（rename 不是新增）；單側路徑證據 | ✓ |
| UNKNOWN 條件 | 無（rename 語義完全由 diff 定義，不依賴 B）——**沒有 B 也可用** | ✓ |

## NODE_REMOVE_CANDIDATE

| 欄位 | 內容 | 落地 |
|---|---|---|
| 最低條件 | 節點**全部** evidence 路徑在 pinned target tree 中確定不存在（ls-tree 全域檢查，含早於 base 的刪除） | ✓ |
| 加強證據 | 路徑在 base 存在（乾淨的刪除敘事）；本輪 diff 的 removed 事件 | ✓ |
| 衝突證據 | 任一路徑仍存在 → 無候選；base==target → 零提案（不變量 13） | ✓ |
| 禁止證據 | 以「B available」為門檻；以本輪 removed 集合為唯一來源；不可逆措辭 | ✓ |
| UNKNOWN 條件 | tree 讀取失敗 → limit+不產候選（讀取未知≠缺失） | ✓ |

## RESPONSIBILITY_CHANGE

| 欄位 | 內容 | 落地 |
|---|---|---|
| 最低條件 | 節點 entryPoint 所指宣告於 target 的 B 宣告中消失（base vs target delta）∧ 節點擁有該檔案 | △（**base 宣告僅 installed B 一條路**——C-only 分支上此通道實際不可用，需 REAL_B 才能證明） |
| 加強證據 | 剩餘頂層宣告少而明確（列在 uncertainty 供人選擇） | ✓ |
| 衝突證據 | 多 owner 各自判決；CA conflict 觸及節點 → 轉人類 | △ |
| 禁止證據 | 自動挑選首個替代符號（S06）；以「無 class」推斷非模組 | ✓ |
| UNKNOWN 條件 | base 比對不可用 → 目前 no_proposal（域內變化）——**無診斷，屬過度保守靜默**（見 §review；最小修法：limits 加診斷） | ✗ |

## 橫切觀察

1. 六格中「衝突證據」欄的 CA 部分全部只由 conflict 行驅動——T1/T2 類合法主張的加強/衝突作用未接線（W4=PARTIAL 的 lattice 表達）。
2. IMPLEMENTATION_LINK_CHANGE 是唯一完全不需要 B 的 kind——B 不可用時的安全子集的正確成員。
3. 兩處「靜默」違格（RELATION_ADD 的解析失敗、RESPONSIBILITY 的無比對分支）性質相同：**違反的不是安全性，而是「誠實降級」**——它們不產生錯誤候選，但把不確定性藏了起來。
