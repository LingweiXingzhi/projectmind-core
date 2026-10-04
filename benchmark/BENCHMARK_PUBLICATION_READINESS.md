# BENCHMARK_PUBLICATION_READINESS — 独立复核(轻量)

- 复核人:独立验证 Agent,2026-10-03;基准目录 `G:\jiagou\projectmind-benchmark`(非 git repo,无 remote)
- 基准侧已有一套完整发布审计(PUBLICATION_AUDIT.json / BENCHMARK_UPLOAD_MANIFEST.md / PUBLICATION_VALIDATION_REPORT.md,2026-10-02/03);本复核**不重复其工作**,只做独立抽验与状态确认。

## 独立抽验结果

| 项 | 结果 |
|---|---|
| 发布清单存在且分 INCLUDE/EXCLUDE | ✓ 159 个 publication candidates / 18 个排除项 |
| **指纹抽验** | ✓ 随机抽 5 个 INCLUDE 文件,SHA256 全部与清单一致(5/5) |
| 凭据扫描 | ✓ 自扫(github_pat/ghp_/sk-/PRIVATE KEY 模式)+ 本轮独立 grep:0 命中;`secret.txt`/`win.ini` 等字符串是路径穿越测试用例,非泄露 |
| 大文件 | ✓ 无 >1MB 文件需上传;441KB 的 B_PR22_BENCHMARK_RESULT.json 属 INCLUDE |
| 排除项确实在盘上 | ✓ .runtime/、__pycache__/、B_PR22_HOLDOUT/pr22_tree/(队友源码拷贝)——上传工具必须继续排除 |
| NO REMOTE = NO PUSH | ✓ 目录非 git repo;本轮亦未初始化、未创建远程 |
| 自测证据 | 基准侧报告 34/34 selftests PASS(189s)+ 5/5 holdout harness PASS;本轮未重跑(成本高、与 CA 验收无关),以基准侧留档为准 |

## 状态

**SAFE_TO_UPLOAD_OWNED_ASSETS_AFTER_REMOTE_DECISION(维持)**。剩余唯一阻塞是**人的决定**:选仓库 owner/visibility/URL。之后按既定 plan:只导入 INCLUDE 资产 → `research/benchmark-validation-2026-10-02` 分支 → 核对远端 head → 普通 push;**不建 main、不 force push、不带 excluded 源码**。

## 一条补充建议

上传前在导出脚本里把"排除规则"做成硬断言(逐文件核对不在 EXCLUDE 前缀内),避免人工 rsync 时把 `pr22_tree/` 或 `.runtime/` 带出去——这是当前清单里唯一靠纪律维持的边界。
