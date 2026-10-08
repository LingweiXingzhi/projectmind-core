// 仓库浏览视图（repo explorer）— A 主线新增，不改动旧地图接口语义。
// 数据全部来自 /api/repo-explorer/*（schemaVersion 1）。
// 异步防串：每个请求携带自增令牌，响应返回时若令牌已过期则丢弃（设计门 Q3）。
// F1（独立终审）：整体包入 IIFE——本脚本的顶层声明（含与 review.js 冲突的
// renderChanges）不再进入 window，classic script 加载顺序无法再覆盖旧地图流程。
(function () {
"use strict";

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
    // 探测期间用户可能已进入协作视图并切换了页签：补加载读取当前活动
    // 页签的 data-page，而不是固定的 dataset.src（B1-b-06，r14）。
    const frame = document.getElementById("collab-frame");
    if (frame && !frame.getAttribute("src")
        && document.querySelector("#view-collab:not([hidden])")) {
      const active = document.querySelector(".collab-tab.active");
      frame.src = (active && active.dataset.page) || frame.dataset.src || "";
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
  // 展示名取 displayPath（F4：不可解码条目的 path 是 base64 身份链接值）
  row.appendChild(explorerElement("span", "explorer-name",
    (node.displayPath || node.path).split("/").pop()));
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
    if (node.pathUndecodable) {
      // 终审 F4：非 UTF-8 路径仅展示（base64 身份 + 跳过原因），禁止源码
      // 跳转——展示文本不能作为可寻址路径使用。
      return item;
    }
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
  // F2（独立终审）：读取失败的页面不得残留任何上一文件的结果——正文被
  // 错误信息替换时，符号 chips、关系面板、文件标签与在途请求一并清除。
  explorerState.fileCursor = null;
  explorerState.fileElements = null;
  explorerState.symbolToken += 1;
  explorerState.relationToken += 1;
  const view = document.getElementById("explorer-file-view");
  view.replaceChildren(explorerElement("div", "explorer-empty", message));
  document.getElementById("explorer-file-head").hidden = true;
  document.getElementById("explorer-more").hidden = true;
  document.getElementById("explorer-file-path").textContent = "未选择文件";
  document.getElementById("explorer-file-range").textContent = "";
  document.getElementById("explorer-symbols").replaceChildren();
  document.getElementById("explorer-relations").replaceChildren();
}

async function openExplorerFile(path, startLine = 1, ctx = null, retried = false) {
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
    // 分页与符号跳转必须绑定同一版本上下文（B3B5-02）。
    if (explorerState.fileCursor) explorerState.fileCursor.ctx = context;
  } catch (error) {
    if (token !== explorerState.fileToken) return;
    // 410 实际恢复路径（B3B5-04）：上下文被 LRU 淘汰后失效缓存、重新
    // open 并重试一次；恢复链绑定原请求代次与仓库身份——守卫失败（用户
    // 已切换仓库/发起新比较/选择了其他文件）时静默退出，绝不清空新状态。
    if (!retried && /CONTEXT_EVICTED/.test(error.message)) {
      const sha = ctx ? ctx.revision : explorerState.revision;
      const gen = explorerState.compareToken;
      const contexts = explorerState.contexts;
      delete contexts[sha];
      const fresh = await ensureContext(sha, ctx ? ctx.versionLabel : undefined, gen);
      const stale = token !== explorerState.fileToken
        || gen !== explorerState.compareToken
        || explorerState.contexts !== contexts;
      if (stale) return;
      if (fresh) {
        if (!ctx && fresh.projectId !== explorerState.projectId) {
          explorerState.projectId = fresh.projectId;
        }
        return openExplorerFile(path, startLine, fresh, true);
      }
    }
    showFileMessage(`无法读取 ${path}：${error.message}`);
  }
}

document.addEventListener('projectmind:open-evidence',async event=>{
  const source=event.detail;
  document.getElementById('explorer-repo-path').value=source.repoPath;
  document.getElementById('explorer-revision').value=source.revision;
  await openRepository({preventDefault(){}});
  if(document.getElementById('explorer-workspace').hidden||explorerState.repoPath!==source.repoPath||explorerState.revision!==source.revision)return;
  const entry=explorerState.treeEntries.find(e=>e.path===source.path.replace(/\/$/,''));
  if(entry?.kind==='directory'){document.getElementById('explorer-search').value=entry.path;renderTree(entry.path);}
  else await openExplorerFile(source.path);
});

// ---------- 比较两个提交（changes） ----------
async function ensureContext(sha, versionLabel, gen) {
  const cached = explorerState.contexts[sha];
  if (cached) return { ...cached, versionLabel };
  const contexts = explorerState.contexts; // 身份守卫：切换仓库会整体替换该对象
  const result = await explorerFetch("/api/repo-explorer/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repoPath: explorerState.repoPath, revision: sha }),
  });
  // 过期结果不得写入缓存（B3B5-03/B3B5-04）：代次推进或仓库已切换（contexts
  // 对象被替换）时，迟到的 open 响应一律丢弃。
  if (gen !== undefined && gen !== explorerState.compareToken) return null;
  if (explorerState.contexts !== contexts) return null;
  if (result.revision !== sha) return null;
  const context = { projectId: result.projectId, revision: result.revision };
  explorerState.contexts[result.revision] = context;
  return { ...context, versionLabel };
}

async function runCompare(event, retried = false) {
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
    // 主上下文被淘汰时刷新并自动重试一次（B3B5-04 的比较侧恢复路径）；
    // 守卫失败（新比较已发起/仓库已切换）时静默退出，不覆盖新比较状态。
    if (!retried && /CONTEXT_EVICTED/.test(error.message)) {
      const contexts = explorerState.contexts;
      delete contexts[explorerState.revision];
      const fresh = await ensureContext(explorerState.revision, undefined, token);
      const stale = token !== explorerState.compareToken
        || explorerState.contexts !== contexts;
      if (stale) return;
      if (fresh) {
        if (fresh.projectId !== explorerState.projectId) {
          explorerState.projectId = fresh.projectId;
        }
        return runCompare(event, true);
      }
    }
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
  // F4：行构建走纯函数 buildChangeRows（explorer-core.js）——每条 entry
  // 一行、永不按展示 path 合并；行 key = machine identity，展示文本相同
  // 的碰撞 entry 各自保留（dataset.changeKey 可区分）。
  for (const change of buildChangeRows(result.changes)) {
    const item = explorerElement("li", "explorer-change-item");
    item.dataset.changeKey = change.key;
    if (change.oldKey) item.dataset.changeOldKey = change.oldKey;
    item.appendChild(explorerElement("span",
      `explorer-change-pill is-${change.status}`,
      CHANGE_STATUS_LABELS[change.status] || change.status));
    item.appendChild(explorerElement("code", "explorer-change-path", change.display));
    if (change.pathUndecodable) {
      // 非 UTF-8 文件名：backslashreplace 表示不可寻址，禁止错误跳转（B3B5-07）。
      item.appendChild(explorerElement("span", "explorer-skip-pill",
        "文件名不是 UTF-8，无法打开源码"));
      list.appendChild(item);
      continue;
    }
    const openVersion = async (sha, label, path) => {
      // 点击即推进选择代次（r19 B3B5-03）：多个版本按钮先后挂起时，最后
      // 一次点击胜出——先返回的旧结果因 fileToken 已被后次点击推进而被丢弃。
      explorerState.fileToken += 1;
      const gen = explorerState.compareToken;
      const fileGen = explorerState.fileToken;
      const ctx = await ensureContext(sha, label, gen);
      if (!ctx) return;
      if (gen !== explorerState.compareToken || fileGen !== explorerState.fileToken) return;
      openExplorerFile(path, 1, ctx);
    };
    if (change.status !== "D") {
      const openNew = explorerElement("button", "explorer-symbol-chip", "打开新版");
      openNew.type = "button";
      openNew.addEventListener("click", () => openVersion(result.targetRevision, "新版", change.path));
      item.appendChild(openNew);
    }
    if (change.status === "D" || change.status === "R" || change.status === "M" || change.status === "C") {
      const oldPath = change.oldPath || change.path;
      const openOld = explorerElement("button", "explorer-symbol-chip", "打开旧版");
      openOld.type = "button";
      openOld.addEventListener("click", () => openVersion(result.baseRevision, "旧版", oldPath));
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
    const raw=text.length?text:' ';
    if(/\.(py|js|ts|jsx|tsx|java|c|cpp|h|json)$/.test(result.path)) {
      const tokens=raw.matchAll(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|#.*$|\/\/.*$|\b(?:def|class|return|import|from|if|else|elif|for|while|try|except|with|async|await|function|const|let|var|new|throw|public|private|static|void|true|false|None|null)\b|\b\d+(?:\.\d+)?\b)/g);
      let cursor=0;
      for(const token of tokens){lineNode.append(document.createTextNode(raw.slice(cursor,token.index)));const value=token[0];const kind=value.startsWith('#')||value.startsWith('//')?'comment':value.startsWith('"')||value.startsWith("'")?'string':/^\d/.test(value)?'number':'keyword';lineNode.append(explorerElement('span',`syntax-${kind}`,value));cursor=token.index+value.length;}lineNode.append(document.createTextNode(raw.slice(cursor)));
    } else lineNode.textContent=raw;
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
  // 继续读取绑定打开该文件时的版本上下文（B3B5-02）。
  await openExplorerFile(cursor.path, cursor.nextLine, cursor.ctx);
}

// ---------- 符号（python_ast_v1：起止行 + docstring） ----------
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
        `符号（${result.parser}）：`));
      for (const symbol of result.symbols) {
        const range = symbol.end_line && symbol.end_line !== symbol.start_line
          ? `${symbol.start_line}-${symbol.end_line}` : `${symbol.start_line}`;
        const chip = explorerElement("button", "explorer-symbol-chip",
          `${projectmindUiLabel(symbol.kind)} ${symbol.name} · 行 ${range}`);
        chip.type = "button";
        chip.title = symbol.qualified_name;
        chip.addEventListener("click", () => scrollToLine(symbol.start_line));
        panel.appendChild(chip);
      }
    } else if (result.status === "ok") {
      panel.appendChild(explorerElement("span", "explorer-symbols-note",
        "该文件没有可识别的定义。"));
    } else {
      const detail = result.warnings && result.warnings.length
        ? `${projectmindUiLabel(result.status)}：${result.warnings.join("；")}` : projectmindUiLabel(result.status);
      panel.appendChild(explorerElement("span", "explorer-symbols-note", `符号解析 ${detail}`));
    }
  } catch (error) {
    if (token !== explorerState.symbolToken) return;
    panel.replaceChildren(explorerElement("span", "explorer-symbols-note",
      `符号读取失败：${error.message}`));
  }
}

async function scrollToLine(line) {
  let cursor = explorerState.fileCursor;
  if (!cursor || line < 1 || line > cursor.totalLines) return;
  // 跨页跳转每次循环都重读最新游标：分页渲染会替换游标对象，旧引用会
  // 导致重复请求同一页（B3B5-01）；无进展或文件已切换即停止。
  while (cursor.renderedLines < line && cursor.nextLine <= cursor.totalLines) {
    await openExplorerFile(cursor.path, cursor.nextLine, cursor.ctx);
    const latest = explorerState.fileCursor;
    if (!latest || latest.path !== cursor.path
        || (latest.ctx ? latest.ctx.projectId : null) !== (cursor.ctx ? cursor.ctx.projectId : null)) {
      return;
    }
    if (latest.renderedLines <= cursor.renderedLines) return;
    cursor = latest;
  }
  const lines = document.querySelectorAll(".explorer-line");
  const index = line - 1;
  if (index < lines.length) {
    lines[index].scrollIntoView({ block: "center" });
    lines[index].classList.add("explorer-line-target");
    setTimeout(() => lines[index] && lines[index].classList.remove("explorer-line-target"), 1500);
  }
}

// ---------- 关系（导入 + resolution + 已确认的反向依赖） ----------
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
    panel.replaceChildren();
    const note = (text) => panel.appendChild(
      explorerElement("span", "explorer-symbols-note", text));
    if (result.status !== "ok") {
      const detail = result.warnings && result.warnings.length
        ? `：${result.warnings.join("；")}` : "";
      note(`静态导入关系 ${projectmindUiLabel(result.status)}${detail}`);
    }
    if (result.imports && result.imports.length) {
      note(`导入（${result.imports.length}）：`);
      for (const item of result.imports) {
        const resolution = item.resolution || {};
        const module = ".".repeat(item.level || 0)
          + (item.module ? `${item.module}.` : "") + (item.name || "");
        const suffix = resolution.status === "resolved" ? `→ ${resolution.targetPath}`
          : resolution.status === "ambiguous"
            ? `→ 待确认（${(resolution.candidates || []).join(" / ")}）` : "→ 未解析";
        const chip = explorerElement("button", "explorer-symbol-chip",
          `${projectmindUiLabel(item.kind)} ${module} · 行 ${item.line} ${suffix}`);
        chip.type = "button";
        if (resolution.status === "resolved" && resolution.targetPath) {
          // The jump stays bound to the relations response's own version
          // context, so opening a relation of an OLD revision reads that
          // revision — never the main browser's SHA (R48-04).
          chip.addEventListener("click", () => {
            const jump = relationJumpParams(
              context, { projectId: explorerState.projectId, revision: explorerState.revision },
              resolution.targetPath);
            openExplorerFile(jump.path, jump.startLine, jump.context);
          });
        } else {
          chip.disabled = true;
        }
        panel.appendChild(chip);
      }
    } else if (result.status === "ok") {
      note("该文件没有静态导入。");
    }
    if (result.dependents && result.dependents.length) {
      note(`被依赖（${result.dependents.length}）：`);
      for (const dep of result.dependents) {
        const chip = explorerElement("button", "explorer-symbol-chip",
          `${dep.path} · 行 ${dep.line}`);
        chip.type = "button";
        chip.addEventListener("click", () => {
          const jump = relationJumpParams(
            context, { projectId: explorerState.projectId, revision: explorerState.revision },
            dep.path);
          openExplorerFile(jump.path, jump.startLine, jump.context);
        });
        panel.appendChild(chip);
      }
    } else if (result.status === "ok") {
      note("已解析范围内未发现导入本文件的记录。");
    }
    if (result.importScan) {
      const scan = result.importScan;
      note(`导入扫描覆盖：${scan.scanned}/${scan.total}`
        + (scan.parseFailed ? `（${scan.parseFailed} 个解析失败）` : ""));
    }
    if (result.warnings && result.warnings.length) {
      note(result.warnings.join("；"));
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
})();
