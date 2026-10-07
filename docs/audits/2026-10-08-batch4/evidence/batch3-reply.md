{
  "package_id": "BATCH-3",
  "target_sha": "c62b5c0789879fa585824471396246ab21161106",
  "scope": "针对上一批9项逐条复验：阅读相关修复 diff、backend_b.py、backend_c.py、context_pack.py、correction.py、service.py、fix_tasks.py、acceptance.py、三个指定测试模块，以及包内 unattended/controller.py、audit_schema.json、selfcheck.json。执行独立内存复现、真实只读 Git 核验和有限版本身份回归；读取提供方 BATCH-2 verdict 与 batch2repair 验收记录。未重新全仓审查。",
  "verdict": "CHANGES_REQUESTED",
  "findings": [
    {
      "id": "A-01",
      "severity": "P2",
      "summary": "新载体场景已修复，但 BATCH-2 的旧载体仍遮蔽 B 的真实分支编辑。",
      "evidence": "backend_b.py:419-421、428、434-436。通过 git show a973d77128ee25e24223f93cb37ee9901ae3392f:archloop/backend_b.py 内存加载旧投影，生成真实旧格式载体；实际 B step.update 将目标改为 s3--n_store，Gateway 预览成功。当前反投影仍得到 branchTargets=null，再投影恢复 s2--n_store。复现退出0。"
    },
    {
      "id": "A-05",
      "severity": "P2",
      "summary": "显式 coverage:null 仍被当作缺省，采用默认覆盖并允许确认。",
      "evidence": "backend_b.py:902-904；service.py:1104 总是使用 request.get(\"coverage\")，无法区分缺失与显式 null。实际 B/Gateway/SQLite 复现：null 与缺省均采用默认节点覆盖并产生发布授权；bad-list 和非对象列表已正确拒绝。脚本退出0。"
    },
    {
      "id": "GEN-01",
      "severity": "P2",
      "summary": "凭据泄漏用例已修复，但新增正则会误排普通配置文件。",
      "evidence": "context_pack.py:37-39 缺少完整键名边界。普通配置 SETTINGS={\"monkey\":\"LongNonSensitiveAnimalName\"} 被匹配为凭据，实际 build_context_pack 将 animal_config.py 排除；同一内容在 BATCH-2 检测结果为 false。普通 service_name 配置保留，api_key/OPENAI_API_KEY、.env、sk-… 均正确排除并记录原因。复现退出0，仅 Git 输入替为合成数据。"
    },
    {
      "id": "C-INCREMENTAL-01",
      "severity": "P2",
      "summary": "基本操作已转换，但连续更新会覆盖先前修改，且仍返回不可应用操作。",
      "evidence": "backend_c.py:231、243-258、268-295。实际 C 候选与 A 操作引擎复现：同一节点 a.py/b.py 两次更新后，a.py 被恢复为 code_fact；删除仍被边引用的节点返回 remove_node，应用报 VALIDATION_FAILED；新增 a/b.py 与 a_b.py 产生同 ID 两次新增，第二条应用失败。后两种均 warnings=[]。脚本退出0，输入图未修改。"
    },
    {
      "id": "G-02",
      "severity": "P2",
      "summary": "恢复已不覆盖新锁，但移走活锁仍允许两个持有者同时执行，互斥目标未闭合。",
      "evidence": "包内 controller.py:569、585-596、637、778-840。真实 acquire_lock 配合内存文件接口和三个工作线程复现：PID11 的活租约被移到 orphan，PID33 成功取得新锁；回收者返回 None、新锁保留，但 first_worker_still_active=true 且 third_worker_still_active=true。tick_audit 未持续核验租约，release_lock:644 也按名称无条件删除。复现退出0。正常死主过期锁回收通过。"
    },
    {
      "id": "ACCEPTANCE-01",
      "severity": "P2",
      "summary": "T01 已修复，T21/T24 谓词仍接受不足或不一致的来源证据为 PASS。",
      "evidence": "acceptance.py:92-98：contentMatches=false 时，revisionMatches 缺失或 null 均返回 PASS。:109-118、454-468：T24 仅检查非空 revision 与文件数，codeRevision=\"HEAD\"、不存在的完整 SHA、其他仓库及不一致来源均可 PASS；创建响应仅取 workspaceId。独立矩阵退出0。STALE_CONTEXT 无关拒绝现为 FAIL；明确同版内容不一致及 EVIDENCE_MISMATCH 正常为 PASS。"
    }
  ],
  "unverified": [
    "指定测试的临时目录初始化受限，未完整执行磁盘集成测试；未重跑提供方完整验收。",
    "未调用真实 AI；纠正载荷通过模拟模型传输捕获，源码与文档读取使用真实固定 Git 字节。",
    "未独立启动 HTTP 服务、操作浏览器或进行跨设备、实体第二副本验收。",
    "未执行新发布或发布事务极端中断测试；仅核验现有真实 Git 版本及来源拒绝。",
    "控制器并发复现使用实际线程和真实控制逻辑，但文件、PID接口替为内存模拟；未运行真实多进程调度或停止进程。",
    "未核验 D 模块及其独立验收；本轮人审旧守卫仅作有限静态回归检查。"
  ],
  "notes": "HEAD 两次核验均与目标一致，git status --porcelain 两次为空，均退出0，工作区 CLEAN。实际执行 python -B -m unittest tests.test_archloop_a_batch2_fixes tests.test_archloop_a_backend_b tests.test_archloop_a_stage23 -v：Ran 47 tests in 2.669s，FAILED(errors=33)，退出1；15个纯测试通过，错误为临时目录不可用并包含类初始化失败。逐条结果：A-01 新格式保留 s3，差分只有 evidence.update、无 step 操作，但旧格式失败；A-05 坏列表及未知ID拒绝，null失败；GEN-01 凭据排除通过、普通键误排回归；CORRECTION-01 已修复——实际 A 纠正忽略过期缓存，旧绑定发送 a973…，20个源码片段匹配 Git、6篇文档非空，并含缺失/排除/limits；回挂 c62…后缓存和下一次载荷均更新，脚本退出0（service.py:316-330、598-601、1520-1523；correction.py:96-109）；C-INCREMENTAL-01 基本操作通过、复杂序列失败；FIX-01 已修复——true/[]→VALIDATION_FAILED，不存在SHA→NOT_FOUND，真实当前提交+列表证据+本人确认→verified、evidenceType=recorded_results，真实cat-file未替换，退出0（fix_tasks.py:49-63、159-183）；G-02 不覆盖及正常回收通过，完整活锁竞态失败；G-03 原丢包问题已修复——真实 mutate_queue/acquire_lock 与两个线程保留两包且均 added=true，无锁对照丢包，退出0，所有队列写入点均经 mutate_queue，但仍共用 G-02 的锁算法；ACCEPTANCE-01 T01失败/空图为FAIL、未配置为NOT_RUN，T21/T24残余如 findings。21个判定自检重跑通过。有限回归读取真实架构提交 3a6555836640e9d146b05caba0c83baee540d033，错误来源SHA拒绝，A/B身份与指纹检查通过，退出0。提供方35 PASS/2 NOT_RUN仅作为记录。复现夹具的初次字段错误修正后重跑退出0，未作为产品缺陷；未修改任何文件。"
}