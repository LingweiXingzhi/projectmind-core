// Pure evidence-link decision for the review change list (UI-01).
//
// The /api/evidence endpoint only accepts paths declared in the current map
// (otherwise 400) that also exist at the requested revision (otherwise 404).
// This decision picks, per change type, which (path, revision) evidence
// views are valid — and returns none when none are, so the UI never
// presents a broken 400/404 link as valid evidence:
//   ADDED / MODIFIED: the file's content context is the target revision.
//   DELETED: the content context is the base revision — never the target.
//   RENAMED: the old path at base AND the new path at target.
// Only map-declared paths produce evidence views. The B facts badge column
// is independent of this decision.
function evidenceTargetsFor(change, declaredPaths) {
  const declared = declaredPaths instanceof Set ? declaredPaths : new Set(declaredPaths || []);
  const targets = [];
  // Git name-status codes carry similarity suffixes for renames/copies
  // (R100, C75, ...), so the prefix — not an exact match — identifies them.
  if (typeof change.code === "string" && change.code.startsWith("R")) {
    if (change.oldPath && declared.has(change.oldPath)) {
      targets.push({ path: change.oldPath, revision: "base" });
    }
    if (declared.has(change.path)) {
      targets.push({ path: change.path, revision: "target" });
    }
    return targets;
  }
  if (!declared.has(change.path)) {
    return targets;
  }
  if (change.code === "D") {
    targets.push({ path: change.path, revision: "base" });
  } else {
    // A / M: the diff guarantees the path exists at the target revision.
    targets.push({ path: change.path, revision: "target" });
  }
  return targets;
}

// Map evidence paths from a /api/snapshot payload (the same declaration set
// the /api/evidence endpoint validates against).
function mapEvidencePaths(snapshot) {
  const paths = new Set();
  for (const node of (snapshot && snapshot.nodes) || []) {
    for (const item of node.evidence || []) {
      if (item && item.path) paths.add(item.path);
    }
  }
  return paths;
}


// Chinese UI labels for machine enums; unknown technical values stay inspectable.
function projectmindUiLabel(value) {
  const labels = {
    "项目地图提案 (Map Proposal)": "项目地图提案",
    "Context Authority": "上下文事实",
    added: "新增", removed: "移除", changed: "修改", modified: "修改",
    title: "名称", summary: "职责说明", entryPoints: "入口", interfaces: "接口",
    evidence: "证据", process: "期望过程", status: "状态", provenance: "来源",
    fact: "事实", proposal: "候选提案", decision: "决策", research: "研究",
    planning: "新项目规划", existing_project: "已有项目", mixed: "混合工作区",
    ai_candidate: "AI 候选", ai_generated: "AI 生成候选", rule_based: "规则候选",
    human_input: "人工输入", human: "人工", ai: "AI", dev_sample: "演示样例",
    candidate: "候选", confirmed_design: "设计已确认", confirmed_cognition: "认知已确认",
    implemented: "已实现", queued: "待接手", received: "已接手", in_progress: "实施中",
    submitted: "已提交", verification_pending: "待核验", verified: "已核验",
    blocked: "受阻", cancelled: "已取消", failed: "失败", draft: "草稿", published: "已发布",
    UNKNOWN: "未知", unknown: "未知", ALIGNED: "一致", DEVIATION_DETECTED: "检测到偏差",
    PROPOSED: "待裁决候选", ACCEPTED: "已接受", REJECTED: "已拒绝",
    NOT_RUN: "未运行", NOT_RUN_AWAITING_CONFIGURATION: "未运行，等待配置",
    no_change: "无变化", full: "全部", partial: "局部", none: "无",
    requirement: "需求依据", code: "代码", code_fact: "代码事实", source: "源码",
    static_reference: "静态引用", functional_collaboration: "功能协作", expected_sequence: "期望先后",
    ok: "正常", skipped: "已跳过", unavailable: "不可用", unsupported: "不支持",
    parse_error: "解析错误", syntax_error: "语法错误", function: "函数", async_function: "异步函数",
    class: "类", method: "方法", async_method: "异步方法", import: "导入", from_import: "从模块导入",
    git_diff: "提交差异", code_facts: "代码事实", map_node: "地图节点", map_evidence: "地图证据",
    context_claim: "上下文声明", context_authority: "上下文事实", process_trace: "过程追踪",
  };
  return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : String(value ?? "—");
}

function projectmindUiDescription(value) {
  return String(value ?? "").replace(/pinned Git diff/g, "固定版本提交差异")
    .replace(/Context Authority/g, "上下文事实");
}
