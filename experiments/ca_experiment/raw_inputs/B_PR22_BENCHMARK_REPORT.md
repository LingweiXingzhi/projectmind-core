# B_PR22_BENCHMARK_REPORT — PR #22(B / Code Facts 首版)只读评测

> **EVALUATION ASSET — NOT PRODUCT SOURCE OF TRUTH**。机器可读:[B_PR22_BENCHMARK_RESULT.json](B_PR22_BENCHMARK_RESULT.json)。
> 评测对象:PR #22 `docs/b-first-version-wang-haining-2026-10-01` @ `0c46747`(经 `gh api` tarball 取回,见环境限制);**未 merge、未修改 PR、未修改 B 业务代码、未修改 Benchmark v0.1 的 GT/verdict**。
> 方法:new adapter(`benchmark/adapters/b_pr22.py`)以 PR #22 自有调用约定(POST `{revision, paths}`)接入;指标由适配器对**冻结的 343 条 Ground Truth**独立计算。

## 1. 结论(一句话)

**PR #22 在冻结 benchmark 上得分为满分:686 个评测单元(343 场景 × before/after)中 0 失败;符号名 P=R=1.0(5149 TP / 0 FP / 0 FN);revision=1.0、evidence=1.0、行号 5149/5149、skipped=1.0;契约探针 B-S01…S14(含 9 个输入拒绝路径)17/17 通过。**

## 2. 主评测(343 scenario full benchmark)

| 指标 | 结果 |
|---|---|
| 评测单元 | **686**(343 场景 × before/after 两次调用) |
| **symbol precision / recall**(声明名基线) | **1.0 / 1.0**(tp=5149, fp=0, fn=0) |
| **revision correctness** | **1.0**(686/686,含 before/after 双修订) |
| **evidence correctness**(报告路径须存在于该提交) | **1.0**(零捏造路径) |
| **行号正确性**(独立 AST oracle,多重集) | **5149/5149** |
| **skipped 正确性**(=该提交全部非 .py 文件) | **1.0** |
| 失败家族 | **0**(49/49 家族 PASS) |
| 耗时 | 448.6 s(686 次真实 git 子进程调用) |

**dependency precision/recall:NOT SUPPORTED**——契约 PROPOSED-B 明示"不建立全量调用图",B 输出无依赖字段;按冻结基准的分类规则标记,不折算为 0 分。

## 3. 契约探针(REFINED B-S01…S14 + 3 扩展)

**17/17 通过**,其中亮点:
- **输入拒绝矩阵 9/9**:非完整 SHA(分支名/`HEAD~1`/短 SHA/大写/65 位/不存在 40 位)、非字符串、缺失 revision、空仓库——全部显式拒绝;
- **路径穿越 6/6 拒绝**(`../`、绝对路径、`..`、空串);GET 的换行分隔 `paths` 约定与 POST 列表约定均生效;缺失路径被拒绝;
- dirty worktree 前后 facts **逐字节一致**(B-S02);rename/delete 归属正确;merge 提交确定性;~50KB 文件在 1MiB 上限内正常解析;空提交返回合法空输出。

## 4. PR #22 自带测试套件(只读运行)

21 项:**19 通过,2 ENVIRONMENT LIMITED**(Windows 文件名不能含 `*`;无 symlink 特权 winerror 1314)——与 benchmark 自身记录的环境限制同源,非产品缺陷。日志:`logs/b_pr22_own_tests.log`。

## 5. 失败分类(按要求五分法,全部证据在 logs)

| 分类 | 条目 | 证据 |
|---|---|---|
| **PRODUCT BUG** | **无**(0 项) | 686 单元 0 失败 |
| **CONTRACT MISMATCH** | **无**(0 项)——B 输出形状与 PROPOSED-B 逐字段一致(revision/files[path,language,entries[name,kind,line]]/skipped[path,reason]) | 适配器映射对比 |
| **BENCHMARK GAP** | ①行号诊断初版用 dict 键控限定名,重定义(同名类两次)被塌缩为最后一处,曾误判 2/11;**已修**(多重集比较,与符号 Counter 语义一致);②strict-seam 0/98 属映射差异(seam 富於契约),已文档化 | REPRO-4;metrics_note |
| **NOT SUPPORTED**(契约/声明范围外) | 依赖提取、entry_points、函数签名、顶层常量值、非 .py 语言 | REPRO-1/2/3 + PROPOSED-B 原文 |
| **ENVIRONMENT LIMITED** | PR 自带测试 2 项;github git-over-https 超时(改 gh api tarball) | 对应日志 |

## 6. 最小复现(4 个,`logs/b_pr22_minrepro.log`)

- **REPRO-1 签名变化**:`def beta(name)` → `def beta(name, suffix='s')`,B 两版报告 identical(name/kind/line 不变)——**NOT SUPPORTED(契约 range)**;
- **REPRO-2 路由表变化**:`ROUTES=['/api/a']` → `['/api/a','/api/b']`,B 无感知——同分类;
- **REPRO-3 依赖/入口**:B 输出仅 `{files, revision, skipped}`,files 内仅 `{entries, language, path}`——契约设计内;
- **REPRO-4 重定义行号**:`class Item` 定义两次,B 如实报告 `(Item,1),(Item.get,2),(Item,5),(Item.get,6)`;初版诊断误判,已修为多重集——**BENCHMARK GAP(评测侧,已修)**。

## 7. 对下游的含义(事实陈述,不含 merge 建议)

- B 交付的输出是**声明级事实**(name/kind/line/结构性跳过),与 C(候选结构)、C/A 的架构复核信号所需字段存在已知差距:签名/常量/依赖/入口四处信息不在 B 输出内——任何要用这些信息的消费者需按 COLLABORATION_CONTRACT §5 走契约变更流程;
- B 的 skipped 语义(带 reason 的可解释跳过)已在 343 场景验证完备,可直接作为"未知/不支持"层的信息来源;
- benchmark 侧新增的 b_pr22 适配器与 4 个复现已落盘,可随 B 后续提交重跑(`python run_b_pr22.py --seeds 7 --pr-tree <tree>`)。

## 8. 环境与限制

- 本机 git-over-https 到 github.com 不可达(300s 超时),PR 树经 `gh api .../tarball/<branch>` 取回后本地评测;`gh` 通道全程只读;
- 评测在系统临时目录的 343+ 个临时 Git 仓库上执行,结束清理;PR 树与 core 均未被写入;
- `strict_seam_match=0/98` 的解释见 metrics_note——它反映"benchmark seam 的符号/依赖/入口要求富於 B 契约",不是失败,也不得据此调低/调高 B 分数。

## 9. 安全核对

```
MERGE PERFORMED: NO
PR #22 MODIFIED: NO
B BUSINESS CODE MODIFIED: NO
BENCHMARK v0.1 GT/VERDICT MODIFIED: NO
PROJECT MODEL / main / model repo: UNTOUCHED
PAID API CALLED: NO
```