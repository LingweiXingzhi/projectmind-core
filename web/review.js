// 变更审查 view: composes the SAME backend contracts the individual modules
// expose — Core compare (/api/compare), B code facts
// (/api/extensions/code_facts), C map proposal (/api/extensions/map_proposal)
// — into one evidence chain for human review. Nothing here redefines
// proposal semantics: candidates are rendered exactly as C published them
// (PROPOSED / human_required), unresolved and limits are always shown.
const reviewBase = document.getElementById("review-base");
const reviewTarget = document.getElementById("review-target");
const reviewRun = document.getElementById("review-run");
const reviewStatus = document.getElementById("review-status");
const reviewOutput = document.getElementById("review-output");
const reviewChanges = document.getElementById("review-changes");
const reviewProposals = document.getElementById("review-proposals");
const reviewHuman = document.getElementById("review-human");

const KIND_LABELS = {
  NODE_ADD: "新增节点",
  RELATION_ADD: "新增关系",
  RELATION_REMOVE_CANDIDATE: "关系移除候选",
  IMPLEMENTATION_LINK_CHANGE: "实现链接更新",
  NODE_REMOVE_CANDIDATE: "节点移除候选",
  RESPONSIBILITY_CHANGE: "职责变化",
};

async function currentRevision() {
  const response = await fetch("/api/snapshot");
  const snapshot = await response.json();
  if (!response.ok) throw new Error(snapshot.error || "无法读取快照");
  return snapshot;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `请求失败（${response.status}）`);
  return result;
}

function shortSha(value) {
  return value ? `${value.slice(0, 8)}…` : "—";
}

async function runReview() {
  reviewRun.disabled = true;
  reviewStatus.textContent = "正在生成审查包…";
  reviewOutput.hidden = true;
  try {
    const snapshot = await currentRevision();
    const target = snapshot.revision;
    reviewTarget.textContent = target;
    const base = (reviewBase.value || "").trim() || snapshot.parentRevision || "";
    if (!base) throw new Error("该提交没有父提交；请输入基准提交 SHA");

    const compare = await fetchJson(`/api/compare?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`);
    const currentMap = await currentRevision();

    // Core compare shape (同一 diff 口径，C 不另建口径)。
    const proposalRequest = {
      baseRevision: base,
      targetRevision: target,
      changes: compare.changes,
      current_map: {
        note: currentMap.mapNote || "",
        nodes: currentMap.nodes,
        edges: currentMap.edges,
      },
    };
    const review = await fetchJson("/api/extensions/map_proposal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(proposalRequest),
    });

    await renderChanges(base, target, compare.changes);
    renderProposals(review);
    renderHuman(review);
    reviewStatus.textContent =
      `审查包已生成：${compare.changes.length} 个变化文件，` +
      `${review.proposals.length} 个候选提案（全部待人工裁决）。`;
    reviewOutput.hidden = false;
  } catch (error) {
    reviewStatus.textContent = `生成失败：${error.message}`;
  } finally {
    reviewRun.disabled = false;
  }
}

async function renderChanges(base, target, changes) {
  document.getElementById("review-change-count").textContent = `${changes.length} 个文件`;
  reviewChanges.replaceChildren();
  if (!changes.length) {
    const empty = document.createElement("p");
    empty.textContent = "该范围内没有 Git 变化。";
    reviewChanges.append(empty);
    return;
  }
  let facts = null;
  try {
    facts = await fetchJson("/api/extensions/code_facts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision: target }),
    });
  } catch (error) {
    facts = null; // B 不可用时该列显示为不可用，不伪造事实。
  }
  const factPaths = new Set((facts && facts.files ? facts.files : []).map((f) => f.path));
  const skipped = new Set((facts && facts.skipped ? facts.skipped : []).map((s) => s.path));
  for (const change of changes) {
    const row = document.createElement("div");
    row.className = "review-change-row";
    const code = document.createElement("code");
    code.className = "review-change-code";
    code.textContent = change.code;
    const path = document.createElement("a");
    path.href = `/api/evidence?path=${encodeURIComponent(change.path)}&revision=${encodeURIComponent(target)}`;
    path.target = "_blank";
    path.rel = "noopener";
    path.textContent = change.path;
    const badge = document.createElement("span");
    badge.className = "review-fact-badge";
    if (skipped.has(change.path)) {
      badge.textContent = "B: skipped";
      badge.classList.add("warn");
    } else if (factPaths.has(change.path)) {
      badge.textContent = "B: 已声明";
      badge.classList.add("ok");
    } else {
      badge.textContent = "B: 无条目 ≠ 不存在";
    }
    row.append(code, path, badge);
    reviewChanges.append(row);
  }
}

function renderProposals(review) {
  document.getElementById("review-proposal-count").textContent =
    `${review.proposals.length} 个候选`;
  reviewProposals.replaceChildren();
  if (!review.proposals.length) {
    const empty = document.createElement("p");
    empty.textContent = "本次变更没有产生候选提案（无交叉信号 ≠ 不存在变化）。";
    reviewProposals.append(empty);
    return;
  }
  for (const proposal of review.proposals) {
    const card = document.createElement("div");
    card.className = "review-proposal";

    const head = document.createElement("div");
    head.className = "review-proposal-head";
    const kind = document.createElement("span");
    kind.className = "review-kind";
    kind.textContent = KIND_LABELS[proposal.kind] || proposal.kind;
    const subject = document.createElement("strong");
    subject.textContent = proposal.subject;
    const status = document.createElement("span");
    status.className = "review-status-pill";
    status.textContent = `${proposal.status}${proposal.human_required ? " · 需人工" : ""}`;
    head.append(kind, subject, status);
    card.append(head);

    const rationale = document.createElement("p");
    rationale.className = "review-rationale";
    rationale.textContent = proposal.rationale;
    card.append(rationale);

    if (proposal.uncertainty && proposal.uncertainty.length) {
      const list = document.createElement("ul");
      list.className = "review-uncertainty";
      for (const item of proposal.uncertainty) {
        const li = document.createElement("li");
        li.textContent = item;
        list.append(li);
      }
      card.append(list);
    }

    const evidence = document.createElement("div");
    evidence.className = "review-evidence";
    for (const item of proposal.evidence || []) {
      const line = document.createElement("span");
      line.className = "review-evidence-item";
      line.textContent = `${item.kind}: ${item.path || item.detail || ""}`;
      evidence.append(line);
    }
    card.append(evidence);
    reviewProposals.append(card);
  }
}

function renderHuman(review) {
  reviewHuman.replaceChildren();
  const sections = [
    ["unresolved（需要人工判断）", review.unresolved],
    ["no_proposal（明确不提案的原因）", review.no_proposal],
    ["limits（降级与已知限制）", review.limits],
  ];
  for (const [title, items] of sections) {
    const head = document.createElement("h3");
    head.textContent = `${title}（${Array.isArray(items) ? items.length : 0}）`;
    reviewHuman.append(head);
    const list = document.createElement("ul");
    list.className = "review-human-list";
    for (const item of Array.isArray(items) ? items : []) {
      const li = document.createElement("li");
      li.textContent = typeof item === "string"
        ? item
        : JSON.stringify(item, null, 0);
      list.append(li);
    }
    reviewHuman.append(list);
  }
}

reviewRun.addEventListener("click", runReview);
currentRevision().then((snapshot) => {
  reviewTarget.textContent = snapshot.revision;
  if (snapshot.parentRevision) reviewBase.placeholder = `父提交 ${snapshot.parentRevision.slice(0, 8)}…`;
}).catch(() => {
  reviewTarget.textContent = "读取失败";
});
