# D_SOURCE_DECISION — D / Handoff + Continuity + Worklog 集成来源定案

- 定案时间:2026-10-04(无人值守 overnight,Phase 0)
- 证据方式:`git fetch origin` + `gh pr view`(实时)+ `git merge-base --is-ancestor`(实测,非引用历史材料)
- 结论:**D_DELIVERY_HEAD = PR #27 head `8f00be38532f3f5e9823aec8cbf430038cc9ff4b`**(branch `feat/handoff-continuity`,OPEN draft,实测;本地 worktree `projectmind-core` 正检出此分支,clean)

## 候选与实测 ancestry

| PR | branch | head(实测) | 实测关系 |
|---|---|---|---|
| #24(handoff 导出包) | `feat/23-handoff-draft` | `731135bd87498db766070183455601247a29fbc6` | **是 PR27 的祖先**(`--is-ancestor` → YES) |
| #26(worklog) | `feat/25-worklog` | `9b3d333dbd75ec7a246de646aa28a9d4b3d0ec80` | **是 PR27 的祖先**(→ YES) |
| #27(continuity) | `feat/handoff-continuity` | `8f00be38532f3f5e9823aec8cbf430038cc9ff4b` | 同时包含 #24 与 #26 |

补充实测:PR24 **不是** PR26 的祖先(NO)——#24 与 #26 是兄弟分支,均被 #27 收编。历史材料"PR27 已包含 PR26、PR24 是其祖先"与实测一致。

## PR27 树内容(实测,均位于仓库根 extensions/)

- `extensions/handoff/`(extension.py / handoff.py / index.html / README.md)
- `extensions/continuity/`(extension.py / model.py / store.py / inspection.py / index.html / README.md)
- `extensions/worklog/`(extension.py / store.py / index.html / README.md)
- `tests/test_handoff.py`、`tests/test_continuity.py`、`tests/test_worklog.py`

## why

1. PR27 完整包含 D 最新成果(handoff + worklog + continuity 三 extension + 三测试文件)。
2. 单一 merge PR27 head 即可,禁止逐个 merge 24→26→27(避免重复与冲突)。

## 结果

- **D_DELIVERY_HEAD = `8f00be38532f3f5e9823aec8cbf430038cc9ff4b`**(PR #27 head)
- PR24/PR26 分支不 merge、不修改、不删除。
- 集成注意(来自 handoff §9):continuity 的 `model.py` 有自己的 FORMAT 版本串(`projectmind-continuity-v1`)与状态机(draft/ready/receiving/active/blocked/completed),不得与 CA 的 schema_version/claim 状态混用。
