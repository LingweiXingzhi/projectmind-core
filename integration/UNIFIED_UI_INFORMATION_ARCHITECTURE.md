# UNIFIED_UI_INFORMATION_ARCHITECTURE — 统一 UI 信息架构设计审计(仅设计,不实现)

- 前提:V1 各模块是独立扩展页(ExtensionHost 自动发现,每扩展自带 index.html)。不做 CSS/重构,只定义信息架构与页面关系。

## 1. 问题

按现状合入全部 PR,用户将面对 **8 个互相独立的页面**:主图(首页)、project_summary、context_authority、code_facts、handoff、continuity、worklog、map_proposal。它们操作同一批底层对象(同一 repo、同一 revision、同一张地图、同一批 PR),但:
- 各页有自己的状态语言(PR 状态/claim 状态/checkpoint 状态);
- "待复核"类信息出现在至少 3 处(A 的 compare reviewCandidates、D 的交接包、未来的 C proposal);
- 证据(revision/SHA)在每个页面重复展示但口径不一致的风险。

## 2. 信息架构提案(三层)

```
L1  项目驾驶舱(新,聚合层)
    ├─ 当前状态条:revision(SHA 短码+完整可复制)· main 与 PR 概览(OPEN/DRAFT/MERGED 徽章统一映射)
    ├─ "需要人做的事"收件箱:统一聚合 ↓ 三个来源的候选
    │   · 地图待复核(A compare reviewCandidates)
    │   · Map Proposal(C,PROPOSED)
    │   · 交接/接续待办(D handoff/continuity)
    ├─ 冲突与告警:CA known_conflicts(HUMAN_REQUIRED)+ registry_problems + verification_unavailable
    └─ 底座身份:Context Pack 的 schema_version/registry_hash/生成时间(可信度提示)

L2  领域工作台(现有扩展页归组,不改其内部)
    ├─ 地图与证据:主图(A)+ code_facts(声明查询)+ map_proposal(C)
    ├─ 事实底座:context_authority(state/claims/conflicts/inspector)
    └─ 协作流:handoff / continuity / worklog(D)

L3  原子视图(复用,不新增)
    · claim/evidence 详情卡(来源 kind+ref+revision 行)
    · diff 视图(A 已有)
    · 决策记录(人工 accept/reject,落 worklog 或 decision log)
```

关键规则:
1. **候选只在一个收件箱出现一次**,来源标注(A/B/C/D),点击跳到对应工作台;三个后端结构不合并,只做展示层聚合——避免逼任何角色改 schema。
2. **每个页面右上角统一显示"证据上下文"**:revision + (若该页消费 pack)registry_hash;让"这条页面数据对应哪个提交/哪个底座"永远可见(呼应 map_version=none 的缺口——UI 层先补偿)。
3. **导航是唯一的跨页机制**:扩展页继续自包含(遵循 EXTENSION_INTERFACE 的独立性原则),驾驶舱只链接,不 iframe 嵌套。

## 3. 统一状态映射表(展示层唯一需要的新约定)

| 底层状态 | 徽章 | 出现处 |
|---|---|---|
| PR_OPEN / PR_OPEN+draft | 蓝 "OPEN" / 蓝 "DRAFT" | CA current、驾驶舱 |
| MERGED(CA)/ GitHub merged | 紫 "MERGED" | 同上 |
| CLOSED | 灰 "CLOSED" | 同上 |
| claim ACTIVE(current) | 绿 "现行" | CA 页 |
| STALE/SUPERSEDED | 黄 "已过期" / 橙 "已取代" | CA 页、收件箱 |
| CONFLICTED + HUMAN_REQUIRED | 红 "需人裁决" | 收件箱(置顶) |
| proposal PROPOSED | 蓝 "待复核" | C 页、收件箱 |
| checkpoint draft/ready/…(D) | 徽章组原样保留,不映射语义 | D 页(避免错误翻译 D 的流程语义) |
| 团队批准 team_approved=false | 红字 "未团队批准" 常驻驾驶舱 | 驾驶舱 |

## 4. 明确不做

- 不把 8 个页面合并成单页应用(违背扩展独立性与四人并行开发)。
- 不让驾驶舱直接执行任何写操作(收件箱只跳转;动作在各工作台内、仍由人点击)。
- 不在 V1 引入统一 CSS 框架;只统一徽章语义与"证据上下文"条。
- 不让驾驶舱自己解析 pack——它调用 CA 的 GET state/conflicts,消费方仍遵守 validate 规则。
