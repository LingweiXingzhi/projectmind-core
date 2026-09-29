const stage = document.getElementById("map-stage");
const details = document.getElementById("details-content");
let snapshot = null;
let selectedId = null;
let comparison = null;

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

function renderMap() {
  stage.replaceChildren();
  const svg = svgElement("svg", { class: "connections", viewBox: "0 0 900 470", "aria-hidden": "true" });
  const byId = new Map(snapshot.nodes.map((node) => [node.id, node]));
  for (const edge of snapshot.edges) {
    const from = byId.get(edge.from);
    const to = byId.get(edge.to);
    if (!from || !to) continue;
    const x1 = from.position.x + 202;
    const y1 = from.position.y + 70;
    const x2 = to.position.x;
    const y2 = to.position.y + 70;
    const line = svgElement("path", {
      d: `M ${x1} ${y1} C ${x1 + 70} ${y1}, ${x2 - 70} ${y2}, ${x2} ${y2}`,
      class: "connection-line",
    });
    svg.append(line);
    if (edge.label) {
      const label = svgElement("text", {
        x: (x1 + x2) / 2,
        y: (y1 + y2) / 2 - 12,
        class: "connection-label",
        "text-anchor": "middle",
      });
      label.textContent = edge.label;
      svg.append(label);
    }
  }
  stage.append(svg);

  snapshot.nodes.forEach((node, index) => {
    const button = element("button", `map-node${node.id === selectedId ? " selected" : ""}${reviewCandidate(node.id) ? " review-candidate" : ""}`);
    button.type = "button";
    button.style.left = `${node.position.x}px`;
    button.style.top = `${node.position.y}px`;
    button.setAttribute("aria-pressed", String(node.id === selectedId));
    button.append(element("span", "node-number", String(index + 1).padStart(2, "0")));
    button.append(element("strong", "node-title", node.title));
    button.append(element("span", "node-summary", node.summary));
    if (reviewCandidate(node.id)) button.append(element("span", "node-review", "待复核"));
    button.append(element("span", "node-arrow", "↗"));
    button.addEventListener("click", () => showDetails(node.id));
    stage.append(button);
  });
}

function showDetails(id) {
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
  } catch (error) {
    comparison = null;
    renderComparison();
    status.textContent = `比较失败：${error.message}`;
    if (selectedId) showDetails(selectedId);
  }
}

async function init() {
  stage.replaceChildren(element("div", "loading", "正在建立地图…"));
  try {
    const response = await fetch("/api/snapshot");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "无法读取仓库");
    snapshot = result;
    comparison = null;
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
  } catch (error) {
    stage.replaceChildren(element("div", "loading error", `地图读取失败：${error.message}`));
    document.getElementById("revision").textContent = "无法读取";
  }
}

document.getElementById("refresh-button").addEventListener("click", init);
document.getElementById("export-button").addEventListener("click", exportSummary);
document.getElementById("compare-button").addEventListener("click", compareVersions);
init();
