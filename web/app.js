const stage = document.getElementById("map-stage");
const details = document.getElementById("details-content");
const NODE_WIDTH = 185;
const NODE_HEIGHT = 140;
const STAGE_WIDTH = 680;
const STAGE_HEIGHT = 470;
let snapshot = null;
let selectedId = null;
let comparison = null;
let aiStatus = null;
let aiResult = null;
let aiBusy = false;
let aiMessage = null;
let layoutOverrides = {};
let savedLayoutRevision = null;

function layoutKey() {
  return `projectmind:draft-layout:${snapshot.repository}`;
}

function layoutFor(node) {
  return layoutOverrides[node.id] || node.position;
}

function setLayoutStatus(message) {
  document.getElementById("layout-status").textContent = message;
}

function loadLayout() {
  layoutOverrides = {};
  savedLayoutRevision = null;
  try {
    const stored = JSON.parse(localStorage.getItem(layoutKey()) || "null");
    if (stored?.positions && typeof stored.positions === "object") {
      for (const node of snapshot.nodes) {
        const position = stored.positions[node.id];
        if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) {
          layoutOverrides[node.id] = { x: Math.max(0, Math.min(STAGE_WIDTH - NODE_WIDTH, position.x)), y: Math.max(0, Math.min(STAGE_HEIGHT - NODE_HEIGHT, position.y)) };
        }
      }
      savedLayoutRevision = stored.revision || null;
      setLayoutStatus(savedLayoutRevision === snapshot.revision ? "已恢复此提交的本机临时布局。" : `已恢复旧布局（原提交 ${String(savedLayoutRevision).slice(0, 8)}），请复核后再保存。`);
      return;
    }
    setLayoutStatus("当前使用人工原始布局。拖动节点后可保存临时位置。");
  } catch (error) {
    setLayoutStatus(`无法读取本机临时布局：${error.message}`);
  }
}

function saveLayout() {
  if (!snapshot) return;
  const positions = Object.fromEntries(snapshot.nodes.map((node) => [node.id, layoutFor(node)]));
  try {
    localStorage.setItem(layoutKey(), JSON.stringify({ revision: snapshot.revision, positions }));
    savedLayoutRevision = snapshot.revision;
    setLayoutStatus(`临时布局已保存在本机浏览器，对应提交 ${snapshot.revision.slice(0, 8)}。`);
  } catch (error) {
    setLayoutStatus(`保存失败：${error.message}`);
  }
}

function resetLayout() {
  if (!snapshot) return;
  try {
    localStorage.removeItem(layoutKey());
    layoutOverrides = {};
    savedLayoutRevision = null;
    renderMap();
    setLayoutStatus("已恢复人工原始布局。本机临时布局已清除。");
  } catch (error) {
    setLayoutStatus(`恢复失败：${error.message}`);
  }
}

function exportDraft() {
  if (!snapshot) return;
  const draft = {
    status: "temporary_unconfirmed_draft",
    note: "节点位置仅供查看；职责和关系来自人工演示图，须由团队复核。此文件不是正式 Project Model。",
    exportedAt: new Date().toISOString(),
    repository: snapshot.repository,
    revision: snapshot.revision,
    mapOrigin: snapshot.mapOrigin,
    nodes: snapshot.nodes.map((node) => ({ ...node, position: layoutFor(node) })),
    edges: snapshot.edges,
    comparison: comparison && comparison.targetRevision === snapshot.revision ? comparison : null,
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" }));
  const link = element("a");
  link.href = url;
  link.download = `projectmind-draft-${snapshot.revision.slice(0, 8)}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function reviewCandidate(id) {
  return comparison?.reviewCandidates.find((item) => item.nodeId === id);
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function svgElement(tag, attributes) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

function drawConnections(svg) {
  svg.replaceChildren();
  const byId = new Map(snapshot.nodes.map((node) => [node.id, node]));
  for (const edge of snapshot.edges) {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    if (!from || !to) continue;
    const first = layoutFor(from);
    const second = layoutFor(to);
    const dx = second.x - first.x;
    const dy = second.y - first.y;
    let x1, y1, x2, y2, curve;
    if (Math.abs(dx) >= NODE_WIDTH) {
      const direction = Math.sign(dx);
      x1 = first.x + (direction > 0 ? NODE_WIDTH : 0);
      y1 = first.y + NODE_HEIGHT / 2;
      x2 = second.x + (direction > 0 ? 0 : NODE_WIDTH);
      y2 = second.y + NODE_HEIGHT / 2;
      const bend = Math.min(70, Math.abs(x2 - x1) / 2);
      curve = `M ${x1} ${y1} C ${x1 + bend * direction} ${y1}, ${x2 - bend * direction} ${y2}, ${x2} ${y2}`;
    } else {
      const direction = Math.sign(dy) || 1;
      x1 = first.x + NODE_WIDTH / 2;
      y1 = first.y + (direction > 0 ? NODE_HEIGHT : 0);
      x2 = second.x + NODE_WIDTH / 2;
      y2 = second.y + (direction > 0 ? 0 : NODE_HEIGHT);
      const bend = Math.min(50, Math.abs(y2 - y1) / 2);
      curve = `M ${x1} ${y1} C ${x1} ${y1 + bend * direction}, ${x2} ${y2 - bend * direction}, ${x2} ${y2}`;
    }
    const line = svgElement("path", {
      d: curve,
      class: `connection-line${edge.from === selectedId || edge.to === selectedId ? " active" : ""}`,
    });
    svg.append(line);
  }
}

function renderMap() {
  stage.replaceChildren();
  const svg = svgElement("svg", { class: "connections", viewBox: `0 0 ${STAGE_WIDTH} ${STAGE_HEIGHT}`, "aria-hidden": "true" });
  drawConnections(svg);
  stage.append(svg);

  snapshot.nodes.forEach((node, index) => {
    const button = element("button", `map-node${node.id === selectedId ? " selected" : ""}${reviewCandidate(node.id) ? " review-candidate" : ""}`);
    button.type = "button";
    button.style.left = `${layoutFor(node).x}px`;
    button.style.top = `${layoutFor(node).y}px`;
    button.setAttribute("aria-pressed", String(node.id === selectedId));
    button.append(element("span", "node-number", String(index + 1).padStart(2, "0")));
    button.append(element("strong", "node-title", node.title));
    button.append(element("span", "node-summary", node.summary));
    if (reviewCandidate(node.id)) button.append(element("span", "node-review", "待复核"));
    button.append(element("span", "node-arrow", "↗"));
    let dragged = false;
    button.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      const start = { ...layoutFor(node) };
      const startX = event.clientX;
      const startY = event.clientY;
      dragged = false;
      button.setPointerCapture(event.pointerId);
      const move = (movement) => {
        const dx = movement.clientX - startX;
        const dy = movement.clientY - startY;
        if (Math.abs(dx) + Math.abs(dy) < 4 && !dragged) return;
        dragged = true;
        const position = { x: Math.max(0, Math.min(STAGE_WIDTH - NODE_WIDTH, Math.round(start.x + dx))), y: Math.max(0, Math.min(STAGE_HEIGHT - NODE_HEIGHT, Math.round(start.y + dy))) };
        layoutOverrides[node.id] = position;
        button.style.left = `${position.x}px`;
        button.style.top = `${position.y}px`;
        drawConnections(svg);
        setLayoutStatus("临时布局已调整，尚未保存。");
      };
      const end = () => {
        button.removeEventListener("pointermove", move);
        button.removeEventListener("pointerup", end);
        button.removeEventListener("pointercancel", end);
      };
      button.addEventListener("pointermove", move);
      button.addEventListener("pointerup", end);
      button.addEventListener("pointercancel", end);
    });
    button.addEventListener("click", () => { if (dragged) dragged = false; else showDetails(node.id); });
    stage.append(button);
  });
}

function showDetails(id) {
  if (selectedId !== id) aiMessage = null;
  selectedId = id;
  renderMap();
  details.replaceChildren();
  const node = snapshot.nodes.find((item) => item.id === id);
  if (!node) return;

  const tag = element("div", "detail-tag", "人工整理的演示节点");
  const title = element("h3", "detail-title", node.title);
  const summary = element("p", "detail-summary", node.summary);
  details.append(tag, title, summary);
  const candidate = reviewCandidate(id);
  if (candidate) {
    details.append(element("div", "review-notice", `来源文件发生变化，建议复核：${candidate.changedEvidencePaths.join("、")}。这不表示架构已经改变。`));
  }

  const entry = element("section", "detail-section");
  entry.append(element("h4", "section-title", "关键入口"));
  entry.append(element("div", "entry-point", node.entryPoint));
  details.append(entry);

  const relations = snapshot.edges.filter((edge) => edge.from === id || edge.to === id);
  const relationSection = element("section", "detail-section");
  relationSection.append(element("h4", "section-title", `相关部分 · ${relations.length}`));
  for (const relation of relations) {
    const other = snapshot.nodes.find((item) => item.id === (relation.from === id ? relation.to : relation.from));
    if (!other) continue;
    const row = element("div", "relation-row");
    row.append(element("span", "relation-symbol", relation.from === id ? "→" : "←"));
    row.append(element("span", "relation-name", other.title));
    row.append(element("small", "relation-label", relation.label));
    relationSection.append(row);
  }
  details.append(relationSection);

  const evidenceSection = element("section", "detail-section");
  evidenceSection.append(element("h4", "section-title", `来源证据 · ${node.evidence.length}`));
  for (const source of node.evidence) {
    const card = element("div", "evidence-card");
    const top = element("div", "evidence-top");
    top.append(element("span", "file-icon", "≡"));
    top.append(element("code", "evidence-path", source.path));
    top.append(element("span", source.existsAtCommit ? "evidence-status present" : "evidence-status missing", source.existsAtCommit ? "提交中存在" : "此版本缺失"));
    card.append(top, element("p", "evidence-reason", source.reason));
    if (source.existsAtCommit) {
      const button = element("button", "evidence-button", "查看该提交中的原文 ↗");
      button.type = "button";
      button.addEventListener("click", () => loadEvidence(source.path, card, button));
      card.append(button);
    }
    evidenceSection.append(card);
  }
  details.append(evidenceSection);
  renderAI();
}

function renderAI() {
  const button = document.getElementById("explain-button");
  const result = document.getElementById("ai-result");
  result.replaceChildren();
  const candidate = selectedId && reviewCandidate(selectedId);
  button.disabled = aiBusy || !aiStatus?.configured || !candidate;
  if (!aiBusy) {
    if (aiMessage) document.getElementById("ai-status").textContent = aiMessage;
    else if (!aiStatus?.configured) document.getElementById("ai-status").textContent = aiStatus?.note || "AI 配置尚未读取。";
    else if (!comparison) document.getElementById("ai-status").textContent = "先完成 Git 版本比较。";
    else if (!candidate) document.getElementById("ai-status").textContent = "选中的部分没有直接声明的变化来源。";
    else document.getElementById("ai-status").textContent = `已就绪：将分析 ${candidate.changedEvidencePaths.join("、")}。模型：${aiStatus.model}`;
  }
  if (!aiResult || aiResult.nodeId !== selectedId || aiResult.baseRevision !== comparison?.baseRevision || aiResult.targetRevision !== comparison?.targetRevision) return;
  const explanation = aiResult.explanation;
  result.append(element("div", "ai-candidate-label", "AI 候选 · 未经团队确认"));
  result.append(element("h3", "ai-summary", explanation.summary));
  for (const [title, values] of [["从差异中可观察到", explanation.observations], ["可能的影响", explanation.possibleEffects], ["仍不能确定", explanation.unknowns]]) {
    const section = element("section", "ai-section");
    section.append(element("h4", "section-title", title));
    if (!values.length) section.append(element("p", "ai-empty", "没有列出"));
    for (const value of values) section.append(element("p", "ai-item", value));
    result.append(section);
  }
  result.append(element("p", "ai-provenance", `引用变化来源：${explanation.evidencePaths.join("、") || "未列出"} · ${aiResult.baseRevision.slice(0, 8)} → ${aiResult.targetRevision.slice(0, 8)}${aiResult.diffTruncated ? " · 差异已截断" : ""}`));
  result.append(element("p", "ai-footnote", aiResult.note));
}

async function explainSelected() {
  if (!snapshot || !comparison || !selectedId || !aiStatus?.configured || !reviewCandidate(selectedId)) return;
  aiBusy = true;
  aiResult = null;
  aiMessage = null;
  renderAI();
  document.getElementById("ai-status").textContent = "正在分析选中部分的 Git 差异…";
  try {
    const response = await fetch("/api/explain", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base: comparison.baseRevision, target: comparison.targetRevision, nodeId: selectedId }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "AI 解释失败");
    aiResult = result;
    aiMessage = "已生成候选解释，请对照来源复核。";
  } catch (error) {
    aiMessage = `解释失败：${error.message}`;
  } finally {
    aiBusy = false;
    renderAI();
  }
}

async function loadEvidence(path, card, button) {
  button.disabled = true;
  button.textContent = "读取中…";
  try {
    const params = new URLSearchParams({ path, revision: snapshot.revision });
    const response = await fetch(`/api/evidence?${params}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "无法读取来源");
    const old = card.querySelector("pre");
    if (old) old.remove();
    card.append(element("pre", "source-preview", result.content + (result.truncated ? "\n…内容已截断" : "")));
    button.textContent = "重新读取原文 ↗";
  } catch (error) {
    button.textContent = `读取失败：${error.message}`;
  } finally {
    button.disabled = false;
  }
}

function exportSummary() {
  if (!snapshot) return;
  const link = element("a");
  const params = new URLSearchParams({ revision: snapshot.revision });
  if (comparison) params.set("base", comparison.baseRevision);
  link.href = `/api/export?${params}`;
  link.download = `projectmind-map-${snapshot.revision.slice(0, 8)}.md`;
  document.body.append(link);
  link.click();
  link.remove();
}

function renderComparison() {
  const result = document.getElementById("compare-result");
  result.replaceChildren();
  document.getElementById("change-count").textContent = comparison ? `${comparison.changes.length} 个变化文件` : "—";
  if (!comparison) return;
  document.getElementById("compare-status").textContent = comparison.note;
  const files = element("div", "change-list");
  files.append(element("h3", "section-title", "真实 Git 变化"));
  if (!comparison.changes.length) files.append(element("p", "no-changes", "这两个提交之间没有文件变化。"));
  for (const change of comparison.changes) {
    const row = element("div", "change-row");
    const label = change.code.startsWith("R") ? "重命名" : ({ A: "新增", M: "修改", D: "删除" }[change.code] || change.code);
    row.append(element("span", "change-code", label));
    row.append(element("code", "change-path", change.oldPath ? `${change.oldPath} → ${change.path}` : change.path));
    files.append(row);
  }
  const candidates = element("div", "candidate-list");
  candidates.append(element("h3", "section-title", `待复核节点 · ${comparison.reviewCandidates.length}`));
  if (!comparison.reviewCandidates.length) candidates.append(element("p", "no-changes", "当前地图没有节点直接引用这些变化文件。"));
  for (const candidate of comparison.reviewCandidates) {
    const node = snapshot.nodes.find((item) => item.id === candidate.nodeId);
    if (!node) continue;
    const button = element("button", "candidate-button", `${node.title} ↗`);
    button.type = "button";
    button.addEventListener("click", () => showDetails(node.id));
    candidates.append(button);
  }
  result.append(files, candidates);
}

async function compareVersions() {
  if (!snapshot) return;
  const base = document.getElementById("base-revision").value.trim();
  const status = document.getElementById("compare-status");
  aiResult = null;
  aiMessage = null;
  if (!/^[0-9a-f]{40,64}$/i.test(base)) {
    comparison = null;
    renderComparison();
    status.textContent = "请输入完整的基准提交 ID。";
    if (selectedId) showDetails(selectedId);
    return;
  }
  status.textContent = "正在读取 Git 差异…";
  try {
    const params = new URLSearchParams({ base, target: snapshot.revision });
    const response = await fetch(`/api/compare?${params}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "无法比较提交");
    comparison = result;
    renderComparison();
    if (selectedId) showDetails(selectedId);
    else renderMap();
    renderAI();
  } catch (error) {
    comparison = null;
    renderComparison();
    status.textContent = `比较失败：${error.message}`;
    if (selectedId) showDetails(selectedId);
    renderAI();
  }
}

async function init() {
  stage.replaceChildren(element("div", "loading", "正在建立地图…"));
  try {
    const response = await fetch("/api/snapshot");
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.error === "string" ? result.error : (result.error && result.error.message) || "无法读取仓库");
    snapshot = result;
    comparison = null;
    aiResult = null;
    aiStatus = null;
    aiMessage = null;
    loadLayout();
    for (const id of ["save-layout-button", "reset-layout-button", "export-draft-button"]) document.getElementById(id).disabled = false;
    document.getElementById("repo-name").textContent = result.repository;
    document.getElementById("revision").textContent = result.revision;
    document.getElementById("branch-name").textContent = result.branch;
    document.getElementById("node-count").textContent = `${result.nodes.length} 个功能部分`;
    document.getElementById("map-note").textContent = result.mapNote;
    document.getElementById("target-revision").textContent = result.revision;
    document.getElementById("base-revision").value = result.parentRevision || "";
    document.getElementById("compare-button").disabled = !result.parentRevision;
    document.getElementById("compare-status").textContent = result.parentRevision ? "准备比较相邻提交…" : "当前提交没有父提交。";
    renderComparison();
    document.getElementById("export-button").disabled = false;
    selectedId = result.nodes[0]?.id || null;
    if (selectedId) showDetails(selectedId);
    else renderMap();
    if (result.parentRevision) await compareVersions();
    try {
      const aiResponse = await fetch("/api/ai-status");
      aiStatus = await aiResponse.json();
      if (!aiResponse.ok) throw new Error(aiStatus.error || "无法读取 AI 配置");
    } catch (error) {
      aiStatus = { configured: false, note: `无法读取 AI 配置：${error.message}` };
    }
    renderAI();
  } catch (error) {
    stage.replaceChildren(element("div", "loading error", `地图读取失败：${error.message}`));
    document.getElementById("revision").textContent = "无法读取";
  }
}

document.getElementById("refresh-button").addEventListener("click", init);
document.getElementById("export-button").addEventListener("click", exportSummary);
document.getElementById("compare-button").addEventListener("click", compareVersions);
document.getElementById("explain-button").addEventListener("click", explainSelected);
document.getElementById("save-layout-button").addEventListener("click", saveLayout);
document.getElementById("reset-layout-button").addEventListener("click", resetLayout);
document.getElementById("export-draft-button").addEventListener("click", exportDraft);
init();
