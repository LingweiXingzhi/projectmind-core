const stage = document.getElementById("map-stage");
const details = document.getElementById("details-content");
let snapshot = null;
let selectedId = null;

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
    const button = element("button", `map-node${node.id === selectedId ? " selected" : ""}`);
    button.type = "button";
    button.style.left = `${node.position.x}px`;
    button.style.top = `${node.position.y}px`;
    button.setAttribute("aria-pressed", String(node.id === selectedId));
    button.append(element("span", "node-number", String(index + 1).padStart(2, "0")));
    button.append(element("strong", "node-title", node.title));
    button.append(element("span", "node-summary", node.summary));
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
  const lines = [
    `# ${snapshot.repository} · 功能地图演示`,
    "",
    `Git 提交：${snapshot.revision}`,
    "",
    `> ${snapshot.mapNote}`,
    "",
  ];
  for (const node of snapshot.nodes) {
    lines.push(`## ${node.title}`, "", node.summary, "", `关键入口：${node.entryPoint}`, "", "来源：");
    for (const item of node.evidence) {
      lines.push(`- ${item.path} — ${item.existsAtCommit ? "该提交中存在" : "该提交中缺失"}；${item.reason}`);
    }
    lines.push("");
  }
  lines.push("## 关系", "");
  for (const edge of snapshot.edges) {
    lines.push(`- ${byTitle(edge.from)} → ${byTitle(edge.to)}：${edge.label}`);
  }
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" }));
  const link = element("a");
  link.href = url;
  link.download = `projectmind-map-${snapshot.revision.slice(0, 8)}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function byTitle(id) {
  return snapshot.nodes.find((node) => node.id === id)?.title || id;
}

async function init() {
  stage.replaceChildren(element("div", "loading", "正在建立地图…"));
  try {
    const response = await fetch("/api/snapshot");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "无法读取仓库");
    snapshot = result;
    document.getElementById("repo-name").textContent = result.repository;
    document.getElementById("revision").textContent = result.revision;
    document.getElementById("branch-name").textContent = result.branch;
    document.getElementById("node-count").textContent = `${result.nodes.length} 个功能部分`;
    document.getElementById("map-note").textContent = result.mapNote;
    document.getElementById("export-button").disabled = false;
    selectedId = result.nodes[0]?.id || null;
    if (selectedId) showDetails(selectedId);
    else renderMap();
  } catch (error) {
    stage.replaceChildren(element("div", "loading error", `地图读取失败：${error.message}`));
    document.getElementById("revision").textContent = "无法读取";
  }
}

document.getElementById("refresh-button").addEventListener("click", init);
document.getElementById("export-button").addEventListener("click", exportSummary);
init();
