# BD_API_COMPATIBILITY — B/D API 兼容性与冲突分析

- 生成:2026-10-04,Phase 2;实测于 `integration/bd-v1` @ `0c2a478`
- 方法:读取各 extension.py/handle 全量分支 + `verification/verify_bd.py` 57 项行为实测(3 轮稳定)

## 1. 路由模型

Core(app.py)统一暴露 `/api/extensions/<id>`(GET 查询串 / POST JSON,≤65536 字节)与页面 `/ext/<id>`。**扩展之间无共享路由**;命名空间 = 扩展目录 id。B 与 D 不存在任何重叠 endpoint。

## 2. B / Code Facts(`code_facts`)

| 项 | 契约 |
|---|---|
| 方法 | GET / POST(其他 → 400) |
| 输入键 | **仅** `revision` + 可选 `paths`(多余键 → 400) |
| revision | 必填,40/64 位小写 SHA,须直指 commit(标签对象/HEAD/短 SHA/`~n` → 400;**无 HEAD 静默回退**) |
| paths | list ≤2000(或 GET 换行串,CRLF 归一);相对路径、禁 `\`、禁 `..`/空段/控制字符;重复项静默去重;**glob 字符按字面处理** |
| 输出 | `{revision, files:[{path, language:"python", entries:[{name(词法限定), kind, line}]}], skipped:[{path, reason}]}` |
| kind(5 种) | class / function / async_function / method / async_method;line = def/async def/class 关键字 1-based 行(装饰器不计) |
| 上限 | 2000 文件、1 MiB/文件、16 MiB 总量;对象不在本地 → 显式报错(不懒抓取) |

## 3. D / handoff + continuity + worklog

**handoff**(无 action 键,单操作):
- GET → `{defaultSource, mainRevision, mainError, mainNote}`(本机 origin/main 解析,无网络访问;缺失时优雅降级)
- POST:必填 `expectedRevision`(须等于当前 snapshot revision,否则 400);`comparisonMode` ∈ custom/main;`baseRevision` 须完整 SHA 或省略;`sourceLocator` = `{kind: git_remote|local_path, value}`(必填结构化对象);输出 `{handoff, markdown, aiContext}`

**continuity**(action 分发):
- GET:list / config / logs / get / inspect / evidence / history / export
- POST:create / update / refresh_checkpoint / event / followup / import_start / import_chunk / import_finish / import_cancel / import_packet
- 状态机:FORMAT=`projectmind-continuity-v1`;states draft→ready→receiving→active→blocked/completed;update/event/followup 均要求 `expectedVersion`(过期 → **409**)
- 导入:packet → **新 id + version 1 + state=receiving**(导入态永不当作本机就绪);handoff_draft 包 → 新接续记录
- 注意:continuity 的 FORMAT/状态机与 CA 的 schema_version/claim 状态**完全独立**,不混用(handoff §9 约束,已核)

**worklog**(action 分发):
- GET:list / get / history / file / backup;POST:save / import_start / import_chunk / import_finish / import_cancel
- 分类固定 4 种:daily / decision / goal / issue;ID 服务端生成(uuid4 hex32);导入 MD/DOC/DOCX/PDF(≤10MB),分片须 `offset` 一致(否则 409)

## 4. 冲突分析结果

| 检查项 | 结果 |
|---|---|
| duplicate action names | worklog 与 continuity 均有 import_start/chunk/finish/cancel —— **路由按扩展 id 命名空间隔离,不冲突**;实测互不影响 |
| duplicate IDs | 扩展 id 唯一(目录名即 id);记录 id 各自服务端生成;无碰撞 |
| shared routes | 无 |
| shared mutable state | 无。存储物理分离:`<git-common-dir>/projectmind-worklog/records.sqlite3` vs `<git-common-dir>/projectmind-continuity/records.sqlite3`;B 纯只读零写盘 |
| 意外共享状态变异 | 实测 S13.1/S13.2:D 写入后 B 输出逐字节不变;B 调用前后两个 D store 快照不变 |
| ExtensionHost 加载隔离 | SystemExit 于 import → 该扩展 unavailable,其余 ready(S14.1);运行期异常 → 500 且 host 存活、其他扩展可服务(S14.3/S14.4) |

## 5. 有意的内部依赖(记录,非问题)

- `extensions/continuity/extension.py` import 了 `extensions/worklog/store.py` 的 `repository_store`(action=logs 读取 worklog 条目)。两者同属 D(PF #27 内部),只读复用,不构成 B/D 污染;但**升级 worklog store 时 continuity 的 logs 只读面需一并回归**。
- handoff POST 的 `comparisonMode: "main"` 依赖本机 `refs/remotes/origin/main`(只读 git;无网络)。

## 6. 结论

B 与 D API 面完全兼容:路由命名空间隔离、无重复 ID、无共享可变状态、加载与运行故障互不拖累。57 项行为验证(含 3 轮稳定)全部通过 → 无 BLOCKER/HIGH API 冲突。
