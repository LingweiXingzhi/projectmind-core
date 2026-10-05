// 仓库浏览视图（repo explorer）— A 主线新增，不改动旧地图接口语义。
// 数据全部来自 /api/repo-explorer/*（schemaVersion 1）。
// 异步防串：每个请求携带自增令牌，响应返回时若令牌已过期则丢弃（设计门 Q3）。

const explorerState = {
  projectId: null,
  revision: null,
  repositoryName: "",
  coverage: null,
  treeEntries: [],
  expanded: new Set(),
  fileCursor: null, // { path, nextLine, totalLines }
  openToken: 0,
  treeToken: 0,
  fileToken: 0,
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

// ---------- 模式探测：无地图时仓库浏览成为主视图 ----------
async function detectModeAndInitExplorer() {
  let noMap = false;
  try {
    const response = await fetch("/api/snapshot");
    if (response.status === 400) {
      const body = await response.json().catch(() => ({}));
      noMap = body?.error?.code === "MAP_REQUIRED";
    }
  } catch (error) { noMap = false; }
  if (!noMap) return;
  document.body.classList.add("no-map");
  for (const note of document.querySelectorAll(".needs-map-note")) note.hidden = false;
  const pill = document.querySelector(".demo-pill");
  if (pill) pill.innerHTML = "<span></span> 仓库浏览 · 无人工地图";
  const frame = document.getElementById("collab-frame");
  if (frame) frame.remove(); // R2-Q1：无地图模式不创建扩展 iframe
  activateView("explorer");
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
    renderExplorerHeader(result);
    await refreshTree();
    status.textContent = "";
  } catch (error) {
    if (token !== explorerState.openToken) return;
    status.textContent = `打开失败：${error.message}`;
    document.getElementById("explorer-header").hidden = true;
    document.getElementById("explorer-workspace").hidden = true;
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

async function openExplorerFile(path, startLine = 1) {
  if (!explorerState.projectId) return;
  const token = ++explorerState.fileToken;
  const query = new URLSearchParams({
    projectId: explorerState.projectId, revision: explorerState.revision, path,
    startLine: String(startLine), endLine: String(startLine + 499),
  });
  try {
    const result = await explorerFetch(`/api/repo-explorer/file?${query}`);
    if (token !== explorerState.fileToken) return;
    renderFile(result, startLine === 1);
  } catch (error) {
    if (token !== explorerState.fileToken) return;
    showFileMessage(`无法读取 ${path}：${error.message}`);
  }
}

function renderFile(result, replace) {
  document.getElementById("explorer-file-head").hidden = false;
  document.getElementById("explorer-file-path").textContent = result.path;
  document.getElementById("explorer-file-range").textContent =
    result.totalLines === 0 ? "空文件" : `第 ${result.startLine}–${result.endLine} 行 / 共 ${result.totalLines} 行`;
  const view = document.getElementById("explorer-file-view");
  const code = explorerElement("code", "explorer-code");
  const lines = result.content.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  const gutter = explorerElement("div", "explorer-gutter");
  const body = explorerElement("div", "explorer-body");
  const first = replace ? result.startLine : explorerState.fileCursor.renderedLines + 1;
  lines.forEach((text, index) => {
    gutter.appendChild(explorerElement("div", "explorer-line-no", String(first + index)));
    const lineNode = explorerElement("div", "explorer-line");
    lineNode.textContent = text.length ? text : " ";
    body.appendChild(lineNode);
  });
  if (replace) view.replaceChildren();
  view.appendChild(gutter);
  view.appendChild(body);
  const renderedLines = (replace ? 0 : explorerState.fileCursor.renderedLines) + lines.length;
  explorerState.fileCursor = {
    path: result.path, nextLine: result.endLine + 1,
    totalLines: result.totalLines, renderedLines,
  };
  const more = document.getElementById("explorer-more");
  if (result.truncated && result.totalLines > 0) {
    more.hidden = false;
    more.textContent = `继续读取（第 ${result.endLine + 1} 行起）`;
  } else {
    more.hidden = true;
  }
}

async function loadMoreFile() {
  const cursor = explorerState.fileCursor;
  if (!cursor || cursor.nextLine > cursor.totalLines) return;
  await openExplorerFile(cursor.path, cursor.nextLine);
}

// ---------- 初始化 ----------
document.getElementById("explorer-open-form").addEventListener("submit", openRepository);
document.getElementById("explorer-search").addEventListener("input", (event) => {
  renderTree(event.target.value.trim());
});
document.getElementById("explorer-more").addEventListener("click", loadMoreFile);
detectModeAndInitExplorer();
