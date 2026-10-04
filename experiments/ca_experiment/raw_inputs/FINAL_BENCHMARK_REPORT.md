# FINAL_BENCHMARK_REPORT — Benchmark & Torture Lab 无人值守运行报告

> **EVALUATION ASSET — NOT PRODUCT SOURCE OF TRUTH**
> 运行窗口:2026-10-01 18:17 – 23:00 左右(+0800,无人值守续接任务);基线:`projectmind-core` main @ `7484d44`(REMOTE CONFIRMATION = ENVIRONMENT LIMITED,github 直连不可达,以本地可确认 main 为准)。

## 1. 最终 scenario families 数:**49**
git 16 / code 14 / deps 7 / entry 6 / noise 6(任务书要求的全部类别覆盖,含 module split/merge、cycle create/remove、extension seam、ext→core 依赖、六种噪音)。

## 2. 最终 dataset instances 数
- 主 manifest `benchmark_manifest.jsonl`:**49**(×1 seed)
- 扩展档:`benchmark_manifest_s3.jsonl` **147**、`benchmark_manifest_s7.jsonl` **343**(Stage C ×20=980 未执行)
- 全部 SHA 级确定(提交日期由 seed 固定);跨族抽查 5/5 GT/SHA/tree 全同。

## 3. Validation 结果
三档 manifest 全量 validate:**0 intent mismatch / 0 bad verdict / 0 missing field / 0 GT mismatch / 0 oracle error**。
validator 为**再生等价 + oracle 重跑**(篡改可检;oracle 语义级错误由 3 个 golden 手算测试兜底——对抗审查确认的结构性限制)。

## 4. Self-tests 数和结果:**34/34 OK**(148.7s)
24(前任 Agent)+ 7(对抗性破坏清单)+ 3(golden 手算 GT)。覆盖:确定性、同 seed 复现、异 seed 区分、49 族实例化、7 种坏 manifest 检测、oracle 抓错、mutation killed/survived、清理、Unicode/空格、golden、非法 verdict/缺字段。

## 5. Mutation 初始/最终 score
- 初始(sample=1,12 mutations):**0.917**(11 killed / 1 survived)
- 最终:**1.000**(12/12 killed)

## 6. Survived mutations 及分类
- **M09-unknowns-loser**:分类 **A(TRUE BENCHMARK GAP)**——参考实现缺失"unknowns 披露"语义(非代码文件→如实披露),补齐后 M09 被杀。未为分数发明任何产品要求;修复仅落在参考实现(非产品)。

## 7. Metamorphic properties 数与结果:**24 条,24/24 held**
覆盖:脏区/untracked 隔离、重定位、同树异身份(amend 构造)、rename/move 保符号集、六种噪音不变量、merge 确定性、cycle 对称、入口单调性、Unicode/空格、三种负向可见性。初轮 19/24,5 个违例中 4 个为属性设计错误、1 个为实现 bug,均已修复并复测。

## 8. Reproduce 验证:5/5 跨族场景 GT/SHA/tree 全同(deterministic SHA)。

## 9. Shrinker:已真实验证——`code-duplicate-symbols-s1` + M05 变异:9→6 文件(删 README/css/__init__),mismatch 全程保持;修复了 GT 取键 bug。迭代式 delta-debugging 未实现(记录)。

## 10. Core baseline(main@7484d44,oracle map=理想人工地图口径)
- **changed files:49/49 与 GT 完全一致**;
- 架构复核混淆矩阵:**TP=27 FP=11 TN=4 FN=4**(HUMAN_JUDGMENT=3 排除);precision=0.711,recall=0.871,F1=0.783;
- FN=地图覆盖缺口(前夜 B-1 的量化)、FP=信噪比(声明路径变化即复核)——均为已知产品缺口,非 benchmark 缺陷;
- 能力:snapshot 49/49、evidence 49/49、export 49/49、extension host ✓。

## 11. B/C/D:**NOT IMPLEMENTED**(FutureTarget 如实抛出;无 mock)。

## 12. Scale 结果(6 档 × 3 seeds,全部成功)
1000 文件:生成 3.1s、snapshot 0.129s、compare 0.085s、evidence 133B、code oracle 28.8s(AST 随规模线性,是未来 B 必须缓存的环节)、结构化上下文 67.8KB;内存 NOT MEASURED(声明)。

## 13. Context efficiency
方法论沿用 Round 2(SUFFICIENCY 必须与体积同报)。本轮 benchmark 侧完成了规模维度的体积测量(上表);**未重新执行多问题 sufficiency 实验**——该结论引用 Round 2(结构类 ~29–39×,内容类 ~4.7–9×,盲区内 INSUFFICIENT)。标 **PARTIAL**。

## 14. Architecture review confusion matrix:见 §10(原始计数)。

## 15. Adversarial review findings(3 个独立子代理,全报告 ADVERSARIAL_REVIEW.md)
- **A(契约边界,7 项)**:facts seam ≠ B 契约形状(HIGH→spec 范围声明 + B 交付时需 shim);verdict 规则缺 SPEC 文档(已补);core 走函数面(契约允许,已标注);
- **B(循环自证,8 项)**:validate=再生等价(结构性,已用 golden 缓解);**家族 verdict 交叉核对是死代码(已激活,立刻抓到 3 个 oracle 真 bug)**;mutation 以参考实现为对照(已改为 GT 锚定);seed/family 未比对(已修);is_arch_path 同源(已标注为上限口径);
- **C(作弊设计,10 项)**:记忆者/模式匹配者实测被出样探针识破;主 run 通道对"背题"有结构暴露面(缓解列入 NEXT_STEPS);行号不可测(B 交付后加);clone-the-oracle 原理上不可防(进程分离列为后续)。

## 16. Anti-cheating findings(ANTI_CHEATING_REPORT.md)
C1 记忆者:在册 PASS、**出样 FAIL、转换 FAIL**;C2 模式匹配:全 FAIL;reference 全 PASS。修复了 X2 探针自身的两个缺陷(陈旧 GT 对比、set() 塌缩重复符号)。

## 17. Benchmark 自身性能
49 场景生成 ~106s(每场景 6-8 次 git 子进程调用为主);profile 化优化未做(记录为可选项,禁止破坏确定性/隔离)。

## 18. 环境限制
Windows+Git Bash 单平台;github.com 直连不可达(→ 本地 main);内存未测;symlink 无特权(ENV-LIMITED 路径)。

## 19. 未完成项(NOT COMPLETED / PARTIAL)
- Stage C(980 instances):NOT COMPLETED(147/343 已稳定,980 边际价值低);
- 多问题 context-efficiency 实验:PARTIAL(方法论与体积数据已有,sufficiency 实验未在 benchmark 侧重跑);
- fuzz campaign(§9 高风险族 50-200 seeds):NOT COMPLETED;
- 并发深度测试:设计级检查完成,实验未做;
- 性能 profile(§24):未做;
- 对抗审查 C5/C7/C9/C10 的结构性缓解:未实现(已列 NEXT_STEPS)。

## 20. 明天从哪里继续
见 `NEXT_STEPS.md`(≤5 条)。

## 21. 本轮修复的 benchmark 自身 bug 清单(全部有测试锚定)
intent 列表 vs 元组比较(23 假阳性)、rename "R" 列表成员判断、结构 delta 未过滤非架构路径、顶层赋值表面缺失(路由/常量)、validate 未比 seed/family、check_facts 未知 revision 静默、check_changed 不比变更码、shrinker GT 取键、build→verdict 传参类型、golden 三处手算期望。
