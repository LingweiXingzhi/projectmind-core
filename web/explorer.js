// 仓库浏览视图（repo explorer）— A 主线新增，不改动旧地图接口语义。
// 数据全部来自 /api/repo-explorer/*（schemaVersion 1）。
// 异步防串：每个请求携带自增令牌，响应返回时若令牌已过期则丢弃（设计门 Q3）。

const explorerState = {
  projectId: null,
  revision: null,
  repositoryName: "",
  coverage: null,
  repoPath: "",
  contexts: {}, // sha -> {projectId, revision}（版本文件读取用）
  treeEntries: [],
  expanded: new Set(),
  fileCursor: null, // { path, nextLine, totalLines, renderedLines }
  fileElements: null, // { gutter, body } — 分页向同一对列追加（B1-b-03）
  openToken: 0,
  treeToken: 0,
  fileToken: 0,
  symbolToken: 0,
  relationToken: 0,
  compareToken: 0,
};

function explorerElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function explorerFetch(path, options) {
  const response = await fetch(path, options);
  let body = null;
  try { body = await response.json(); } catch (error) { body = {}; }
  if (!response.ok) {
    const detail = body && body.error
      ? (typeof body.error === "string" ? body.error : `${body.error.code}: ${body.error.message}`)
      : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

function resetFilePane(message) {
  // 换仓库/换版本/打开失败都必须丢弃旧正文、游标、目录状态与在途请求
  // （B1-b-01：等待新目录期间不得显示旧仓库目录，失败后搜索不得复活旧条目）。
  explorerState.fileCursor = null;
  explorerState.fileElements = null;
  explorerState.treeEntries = [];
  explorerState.expanded = new Set();
  explorerState.fileToken += 1;
  explorerState.symbolToken += 1;
  explorerState.relationToken += 1;
  explorerState.compareToken += 1;
  explorerState.treeToken += 1;
  const view = document.getElementById("explorer-file-view");
  view.replaceChildren(explorerElement("div", "explorer-empty", message || "从左侧选择一个文件。"));
  document.getElementById("explorer-file-head").hidden = true;
  document.getElementById("explorer-more").hidden = true;
  document.getElementById("explorer-file-path").textContent = "未选择文件";
  document.getElementById("explorer-file-range").textContent = "";
  document.getElementById("explorer-symbols").replaceChildren();
  document.getElementById("explorer-relations").replaceChildren();
  document.getElementById("explorer-tree").replaceChildren(
    explorerElement("div", "explorer-empty", "正在读取目录…"));
  const search = document.getElementById("explorer-search");
  if (search.value) search.value = "";
}

function splitPhysicalLines(text) {
  // 与接口一致：仅按 CRLF/CR/LF 物理换行切分（B1-b-04），U+2028 不算换行。
  if (text === "") return [];
  const lines = text.match(/[^\r\n]*(?:\r\n|\r|\n|$)/g);
  if (lines && lines[lines.length - 1] === "") lines.pop();
  return lines.map((line) => line.replace(/[\r\n]+$/, ""));
}

// ---------- 模式探测：无地图时仓库浏览成为主视图 ----------
async function detectModeAndInitExplorer() {
  let noMap = false;
  let mapConfirmed = false;
  try {
    const response = await fetch("/api/snapshot");
    if (response.status === 400) {
      const body = await response.json().catch(() => ({}));
      noMap = body?.error?.code === "MAP_REQUIRED";
    } else if (response.ok) {
      mapConfirmed = true; // 只有显式成功才算确认地图模式（B1-b-06 残留）
    }
  } catch (error) {
    // 探测失败 = 模式未知：绝不加载扩展 iframe，也不冒认任一模式。
  }
  if (noMap) {
    document.body.dataset.mapMode = "false";
    document.body.classList.add("no-map");
    for (const note of document.querySelectorAll(".needs-map-note")) note.hidden = false;
    const pill = document.querySelector(".demo-pill");
    if (pill) pill.innerHTML = "<span></span> 仓库浏览 · 无人工地图";
    const frame = document.getElementById("collab-frame");
    if (frame) frame.remove(); // R2-Q1：无地图模式不创建扩展 iframe
    activateView("explorer");
    return;
  }
  if (mapConfirmed) {
    document.body.dataset.mapMode = "true";
    // 探测期间用户可能已进入协作视图：确认地图模式后立即补加载（B1-b-06）。
    const frame = document.getElementById("collab-frame");
    if (frame && !frame.getAttribute("src")
        && document.querySelector("#view-collab:not([hidden])")) {
      frame.src = frame.dataset.src || "";
    }
    return;
  }
  // 模式未知：两种模式都不冒认；iframe 保持不加载。
  document.body.dataset.mapMode = "unknown";
}

// ---------- 打开仓库 ----------
async function openRepository(event) {
  event.preventDefault();
  const status = document.getElementById("explorer-status");
  const pathInput = document.getElementById("explorer-repo-path").value.trim();
  const revisionInput = document.getElementById("explorer-revision").value.trim() || "HEAD";
  if (!pathInput) { status.textContent = "请输入本机仓库的绝对路径。"; return; }
  status.textContent = "正在打开仓库…";
  const token = ++explorerState.openToken;
  try {
    const result = await explorerFetch("/api/repo-explorer/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repoPath: pathInput, revision: revisionInput }),
    });
    if (token !== explorerState.openToken) return;
    explorerState.projectId = result.projectId;
    explorerState.revision = result.revision;
    explorerState.repositoryName = result.repositoryName;
    explorerState.coverage = result.coverage;
    explorerState.repoPath = pathInput;
    explorerState.contexts = { [result.revision]: { projectId: result.projectId, revision: result.revision } };
    renderExplorerHeader(result);
    document.getElementById("explorer-compare-form").hidden = false;
    const targetInput = document.getElementById("explorer-target");
    if (!targetInput.value) targetInput.value = result.revision;
    document.getElementById("explorer-changes-result").replaceChildren();
    document.getElementById("explorer-changes-status").textContent =
      "打开仓库后可用；两个版本都必须是完整 SHA。";
    resetFilePane();
    await refreshTree();
    // 整次打开一个代次：目录响应返回时若本次 open 已失效（用户已改为
    // 其他仓库或已失败），不得清除新的状态（B1-b-01 残留）。
    if (token !== explorerState.openToken) return;
    status.textContent = "";
  } catch (error) {
    if (token !== explorerState.openToken) return;
    status.textContent = `打开失败：${error.message}`;
    document.getElementById("explorer-header").hidden = true;
    document.getElementById("explorer-workspace").hidden = true;
    document.getElementById("explorer-compare-form").hidden = true;
    resetFilePane();
  }
}

function renderExplorerHeader(result) {
  document.getElementById("explorer-header").hidden = false;
  document.getElementById("explorer-workspace").hidden = false;
  const coverage = result.coverage;
  document.getElementById("explorer-title").textContent =
    `${result.repositoryName} @ ${result.revision.slice(0, 12)}`;
  const skipped = coverage.skipped.length;
  const line = `已跟踪 ${coverage.trackedFileCount} 个文件 · 可浏览 ${coverage.indexedFileCount} 个`
    + (coverage.partial ? ` · 跳过 ${skipped} 个（见下方原因）` : " · 完整索引");
  document.getElementById("explorer-coverage").textContent = line;
  const skipBox = document.getElementById("explorer-skipped");
  skipBox.replaceChildren();
  if (coverage.partial) {
    skipBox.hidden = false;
    const list = explorerElement("ul", "explorer-skip-list");
    for (const item of coverage.skipped) {
      list.appendChild(explorerElement("li", "", `${item.path} — ${item.reason}`));
    }
    skipBox.appendChild(list);
  } else {
    skipBox.hidden = true;
  }
}

// ---------- 目录树 ----------
async function refreshTree() {
  const token = ++explorerState.treeToken;
  const query = new URLSearchParams({ projectId: explorerState.projectId, revision: explorerState.revision });
  try {
    const result = await explorerFetch(`/api/repo-explorer/tree?${query}`);
    if (token !== explorerState.treeToken) return;
    explorerState.treeEntries = result.entries;
    explorerState.expanded = new Set(
      result.entries.filter((entry) => entry.kind === "directory" && !entry.parentPath)
                    .map((entry) => entry.path));
    renderTree(document.getElementById("explorer-search").value.trim());
    const coverage = result.coverage;
    document.getElementById("explorer-coverage").textContent =
      `已跟踪 ${coverage.trackedFileCount} 个文件 · 可浏览 ${coverage.indexedFileCount} 个`
      + (coverage.partial ? ` · 跳过 ${coverage.skipped.length} 个（见下方原因）` : " · 完整索引");
  } catch (error) {
    if (token !== explorerState.treeToken) return;
    document.getElementById("explorer-tree").replaceChildren(
      explorerElement("div", "explorer-empty", `目录读取失败：${error.message}`));
  }
}

function buildTreeNodes(entries, query) {
  const byPath = new Map();
  const roots = [];
  for (const entry of entries) {
    const node = { ...entry, children: [] };
    byPath.set(entry.path, node);
    const parent = entry.parentPath ? byPath.get(entry.parentPath) : null;
    if (parent) parent.children.push(node); else roots.push(node);
  }
  if (!query) return roots;
  const needle = query.toLowerCase();
  const keep = (node) => {
    const self = node.path.toLowerCase().includes(needle);
    node.children = node.children.filter(keep);
    return self || node.children.length > 0;
  };
  return roots.filter(keep);
}

function renderTree(query) {
  const container = document.getElementById("explorer-tree");
  container.replaceChildren();
  const roots = buildTreeNodes(explorerState.treeEntries, query);
  if (roots.length === 0) {
    container.appendChild(explorerElement("div", "explorer-empty",
      query ? "没有匹配该路径的文件。" : "该提交没有可浏览的文件。"));
    return;
  }
  const list = explorerElement("ul", "explorer-list");
  for (const node of roots) list.appendChild(renderTreeNode(node, query));
  container.appendChild(list);
}

function renderTreeNode(node, query) {
  const item = explorerElement("li", "explorer-item");
  const row = explorerElement("div", "explorer-row");
  const isDir = node.kind === "directory";
  const expanded = explorerState.expanded.has(node.path) || Boolean(query);
  row.classList.add(isDir ? "is-directory" : "is-file");
  if (node.skippedReason) row.classList.add("is-skipped");
  row.appendChild(explorerElement("span", "explorer-caret", isDir ? (expanded ? "▾" : "▸") : ""));
  row.appendChild(explorerElement("span", "explorer-icon", isDir ? "▾" : "·"));
  row.appendChild(explorerElement("span", "explorer-name", node.path.split("/").pop()));
  if (node.skippedReason) {
    row.title = node.skippedReason;
    row.appendChild(explorerElement("span", "explorer-skip-pill", "不可读"));
  }
  item.appendChild(row);
  if (isDir) {
    if (expanded) {
      const childList = explorerElement("ul", "explorer-list");
      for (const child of node.children) childList.appendChild(renderTreeNode(child, query));
      item.appendChild(childList);
    }
    row.addEventListener("click", () => {
      if (explorerState.expanded.has(node.path)) explorerState.expanded.delete(node.path);
      else explorerState.expanded.add(node.path);
      renderTree(document.getElementById("explorer-search").value.trim());
    });
  } else {
    row.addEventListener("click", () => {
      for (const other of document.querySelectorAll(".explorer-row.selected")) {
        other.classList.remove("selected");
      }
      row.classList.add("selected");
      openExplorerFile(node.path);
    });
  }
  return item;
}

// ---------- 文件正文 ----------
function showFileMessage(message) {
  const view = document.getElementById("explorer-file-view");
  view.replaceChildren(explorerElement("div", "explorer-empty", message));
  document.getElementById("explorer-file-head").hidden = true;
  explorerState.fileCursor = null;
}

async function openExplorerFile(path, startLine = 1, ctx = null) {
  const context = ctx || { projectId: explorerState.projectId, revision: explorerState.revision };
  if (!context || !context.projectId) return;
  const token = ++explorerState.fileToken;
  const query = new URLSearchParams({
    projectId: context.projectId, revision: context.revision, path,
    startLine: String(startLine), endLine: String(startLine + 499),
  });
  try {
    const result = await explorerFetch(`/api/repo-explorer/file?${query}`);
    if (token !== explorerState.fileToken) return;
    if (ctx) {
      result.versionLabel = ctx.versionLabel;
      result.versionContext = ctx;
    }
    renderFile(result, startLine === 1);
  } catch (error) {
    if (token !== explorerState.fileToken) return;
    showFileMessage(`无法读取 ${path}：${error.message}`);
  }
}

// ---------- 比较两个提交（changes） ----------
async function ensureContext(sha, versionLabel) {
  if (explorerState.contexts[sha]) return explorerState.contexts[sha];
  const result = await explorerFetch("/api/repo-explorer/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repoPath: explorerState.repoPath, revision: sha }),
  });
  const context = { projectId: result.projectId, revision: result.revision, versionLabel };
  explorerState.contexts[result.revision] = context;
  return context;
}

async function runCompare(event) {
  event.preventDefault();
  if (!explorerState.projectId) return;
  const base = document.getElementById("explorer-base").value.trim();
  const target = document.getElementById("explorer-target").value.trim();
  const status = document.getElementById("explorer-changes-status");
  const token = ++explorerState.compareToken;
  status.textContent = "正在比较…";
  const query = new URLSearchParams({
    projectId: explorerState.projectId, base, target,
  });
  try {
    const result = await explorerFetch(`/api/repo-explorer/changes?${query}`);
    if (token !== explorerState.compareToken) return;
    renderChanges(result);
    status.textContent = "";
  } catch (error) {
    if (token !== explorerState.compareToken) return;
    status.textContent = `比较失败：${error.message}`;
  }
}

const CHANGE_STATUS_LABELS = {
  A: "新增", M: "修改", D: "删除", R: "重命名", C: "复制", T: "类型变更",
};

function renderChanges(result) {
  const container = document.getElementById("explorer-changes-result");
  container.replaceChildren();
  container.appendChild(explorerElement("p", "explorer-symbols-note",
    `基准 ${result.baseRevision.slice(0, 12)} → 目标 ${result.targetRevision.slice(0, 12)} · ${result.changes.length} 项变化（静态 Git 差异，不含语义判断）`));
  if (!result.changes.length) {
    container.appendChild(explorerElement("div", "explorer-empty", "两个提交之间没有文件变化。"));
    return;
  }
  const list = explorerElement("ul", "explorer-change-list");
  for (const change of result.changes) {
    const item = explorerElement("li", "explorer-change-item");
    item.appendChild(explorerElement("span",
      `explorer-change-pill is-${change.status}`,
      CHANGE_STATUS_LABELS[change.status] || change.status));
    item.appendChild(explorerElement("code", "explorer-change-path",
      change.oldPath ? `${change.oldPath} → ${change.path}` : change.path));
    const targetCtx = () => ensureContext(result.targetRevision, "新版");
    const baseCtx = () => ensureContext(result.baseRevision, "旧版");
    if (change.status !== "D") {
      const openNew = explorerElement("button", "explorer-symbol-chip", "打开新版");
      openNew.type = "button";
      openNew.addEventListener("click", async () => {
        const ctx = await targetCtx();
        openExplorerFile(change.path, 1, ctx);
      });
      item.appendChild(openNew);
    }
    if (change.status === "D" || change.status === "R" || change.status === "M" || change.status === "C") {
      const oldPath = change.oldPath || change.path;
      const openOld = explorerElement("button", "explorer-symbol-chip", "打开旧版");
      openOld.type = "button";
      openOld.addEventListener("click", async () => {
        const ctx = await baseCtx();
        openExplorerFile(oldPath, 1, ctx);
      });
      item.appendChild(openOld);
    }
    list.appendChild(item);
  }
  container.appendChild(list);
}

function renderFile(result, replace) {
  document.getElementById("explorer-file-head").hidden = false;
  document.getElementById("explorer-file-path").textContent = result.path;
  const versionTag = result.versionLabel ? `（${result.versionLabel}）` : "";
  document.getElementById("explorer-file-range").textContent =
    (result.totalLines === 0 ? "空文件" : `第 ${result.startLine}–${result.endLine} 行 / 共 ${result.totalLines} 行`) + versionTag;
  const view = document.getElementById("explorer-file-view");
  if (replace || !explorerState.fileElements) {
    view.replaceChildren();
    const gutter = explorerElement("div", "explorer-gutter");
    const body = explorerElement("div", "explorer-body");
    view.append(gutter, body);
    explorerState.fileElements = { gutter, body };
  }
  const { gutter, body } = explorerState.fileElements;
  const lines = splitPhysicalLines(result.content);
  const first = replace ? result.startLine : explorerState.fileCursor.renderedLines + 1;
  lines.forEach((text, index) => {
    gutter.appendChild(explorerElement("div", "explorer-line-no", String(first + index)));
    const lineNode = explorerElement("div", "explorer-line");
    lineNode.textContent = text.length ? text : " ";
    body.appendChild(lineNode);
  });
  const renderedLines = (replace ? 0 : explorerState.fileCursor.renderedLines) + lines.length;
  explorerState.fileCursor = {
    path: result.path, nextLine: result.endLine + 1,
    totalLines: result.totalLines, renderedLines,
  };
  const more = document.getElementById("explorer-more");
  // 继续按钮看“文件还有没有下一页”，与 truncated（任一行未返回）区分（B1-b-03）。
  if (result.endLine < result.totalLines) {
    more.hidden = false;
    more.textContent = `继续读取（第 ${result.endLine + 1} 行起）`;
  } else {
    more.hidden = true;
  }
  if (replace) {
    loadSymbols(result.path, result.versionContext || null);
    loadRelations(result.path, result.versionContext || null);
  }
}

async function loadMoreFile() {
  const cursor = explorerState.fileCursor;
  if (!cursor || cursor.nextLine > cursor.totalLines) return;
  await openExplorerFile(cursor.path, cursor.nextLine);
}

// ---------- 符号（legacy_code_facts 过渡：只有定义行，无结束行） ----------
async function loadSymbols(path, ctx = null) {
  const panel = document.getElementById("explorer-symbols");
  const token = ++explorerState.symbolToken;
  const context = ctx || { projectId: explorerState.projectId, revision: explorerState.revision };
  if (!context || !context.projectId) return;
  panel.replaceChildren(explorerElement("span", "explorer-symbols-note", "正在读取符号…"));
  const query = new URLSearchParams({
    projectId: context.projectId, revision: context.revision, path,
  });
  try {
    const result = await explorerFetch(`/api/repo-explorer/symbols?${query}`);
    if (token !== explorerState.symbolToken) return;
    panel.replaceChildren();
    if (result.status === "ok" && result.symbols.length) {
      panel.appendChild(explorerElement("span", "explorer-symbols-note",
        `符号（${result.parser}，仅定义行）：`));
      for (const symbol of result.symbols) {
        const chip = explorerElement("button", "explorer-symbol-chip",
          `${symbol.kind} ${symbol.name} · 行 ${symbol.start_line}`);
        chip.type = "button";
        chip.addEventListener("click", () => scrollToLine(symbol.start_line));
        panel.appendChild(chip);
      }
    } else if (result.status === "ok") {
      panel.appendChild(explorerElement("span", "explorer-symbols-note",
        "该文件没有可识别的定义。"));
    } else {
      const detail = result.warnings && result.warnings.length
        ? `${result.status}：${result.warnings.join("；")}` : result.status;
      panel.appendChild(explorerElement("span", "explorer-symbols-note", `符号解析 ${detail}`));
    }
  } catch (error) {
    if (token !== explorerState.symbolToken) return;
    panel.replaceChildren(explorerElement("span", "explorer-symbols-note",
      `符号读取失败：${error.message}`));
  }
}

async function scrollToLine(line) {
  const cursor = explorerState.fileCursor;
  if (!cursor || line < 1 || line > cursor.totalLines) return;
  while (cursor.renderedLines < line && cursor.nextLine <= cursor.totalLines) {
    await openExplorerFile(cursor.path, cursor.nextLine);
  }
  const lines = document.querySelectorAll(".explorer-line");
  const index = line - 1;
  if (index < lines.length) {
    lines[index].scrollIntoView({ block: "center" });
    lines[index].classList.add("explorer-line-target");
    setTimeout(() => lines[index] && lines[index].classList.remove("explorer-line-target"), 1500);
  }
}

// ---------- 关系（C 未接入前显示 unavailable，不伪装成空结果） ----------
async function loadRelations(path, ctx = null) {
  const panel = document.getElementById("explorer-relations");
  const token = ++explorerState.relationToken;
  const context = ctx || { projectId: explorerState.projectId, revision: explorerState.revision };
  if (!context || !context.projectId) return;
  const query = new URLSearchParams({
    projectId: context.projectId, revision: context.revision, path,
  });
  try {
    const result = await explorerFetch(`/api/repo-explorer/relations?${query}`);
    if (token !== explorerState.relationToken) return;
    if (result.status === "unavailable") {
      panel.replaceChildren(explorerElement("span", "explorer-symbols-note",
        "静态导入关系：尚未接入解析器（目录与源码浏览不受影响）。"));
    } else {
      panel.replaceChildren(explorerElement("span", "explorer-symbols-note",
        `静态导入关系：${result.status}`));
    }
  } catch (error) {
    if (token !== explorerState.relationToken) return;
    panel.replaceChildren(explorerElement("span", "explorer-symbols-note",
      `关系读取失败：${error.message}`));
  }
}

// ---------- 初始化 ----------
document.getElementById("explorer-open-form").addEventListener("submit", openRepository);
document.getElementById("explorer-search").addEventListener("input", (event) => {
  renderTree(event.target.value.trim());
});
document.getElementById("explorer-more").addEventListener("click", loadMoreFile);
document.getElementById("explorer-compare-form").addEventListener("submit", runCompare);
detectModeAndInitExplorer();
