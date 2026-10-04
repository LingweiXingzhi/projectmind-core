# BD_MERGE_CONFLICTS — B+D 集成冲突记录

- 集成时间:2026-10-04;分支 `integration/bd-v1`(基于 main `7484d44`)
- 顺序:先 merge B(PR #31 head `80e091ac`)→ 再 merge D(PR #27 head `8f00be38`),均 `--no-ff`,不 squash

## 冲突清单:无

两次 merge 均由 ort 策略自动完成,零冲突:

| merge | 结果 | 变更 |
|---|---|---|
| B(PR31) | clean | 6 文件,+1175 行(extensions/code_facts/* + tests/test_code_facts.py) |
| D(PR27) | clean | 20 文件,+2308 行(extensions/handoff,continuity,worklog/* + 3 个测试文件) |

## 预判依据(与实测一致)

- merge 前实测:`git diff --name-only main..PR31` 与 `main..PR27` 的交集为**空**(comm -12 无输出)。B 只新增 code_facts 目录;D 只新增 handoff/continuity/worklog 目录;双方都不触碰 Core 现有文件(app.py/extension_host.py/web/data 均未被任何一方修改)。
- 两支 merge-base 均为 main `7484d44`,main 在集成期间未推进。

## 语义裁决

无需 ours/theirs 选择;无共享文件需要裁决。B 与 D 的扩展通过 ExtensionHost 以独立目录 + 独立路由(`/api/extensions/code_facts` vs `/api/extensions/handoff|continuity|worklog`)共存,唯一交互面是 Core 注入的同一 `ExtensionContext`(repo/map_path/snapshot/compare)。

INTEGRATION_HEAD = `0c2a478`(Merge D)。
