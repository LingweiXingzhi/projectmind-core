// explorer-core.js — 仓库浏览的纯函数决策层（无 DOM 依赖）。
// 独立成文件以便 node 沙盒回归（与 evidence-links.js 同一模式）：
// F4/r26 —— 非线性建树与物理行切分都在这里被钉住。

function splitPhysicalLines(text) {
  // 与接口一致：仅按 CRLF/CR/LF 物理换行切分（B1-b-04），U+2028 不算换行。
  if (text === "") return [];
  const lines = text.match(/[^\r\n]*(?:\r\n|\r|\n|$)/g);
  if (lines && lines[lines.length - 1] === "") lines.pop();
  return lines.map((line) => line.replace(/[\r\n]+$/, ""));
}

function buildTreeNodes(entries, query) {
  // 两遍建树（r26 残留）：NUL 身份排序在明文父目录之前，单遍查找会把
  // 子条目丢到根层——先为全部条目建节点索引，再统一连接父子关系。
  const byPath = new Map();
  const nodes = entries.map((entry) => {
    const node = { ...entry, children: [] };
    byPath.set(entry.path, node);
    return node;
  });
  const roots = [];
  for (const node of nodes) {
    const parent = node.parentPath ? byPath.get(node.parentPath) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  if (!query) return roots;
  const needle = query.toLowerCase();
  const keep = (node) => {
    // 搜索按展示文本匹配（F4：非 UTF-8 条目的 path 是身份链接值）
    const self = ((node.displayPath || node.path)).toLowerCase().includes(needle);
    node.children = node.children.filter(keep);
    return self || node.children.length > 0;
  };
  return roots.filter(keep);
}

function buildChangeRows(changes) {
  // F4（changes 侧）：每条 change entry 一行，永不按展示 path 合并或去重。
  // 行 key 取 machine identity（identity/oldIdentity），两个不同 raw byte
  // path 即使展示文本完全相同，key 也必然不同（后端保证 identity 唯一）。
  return changes.map((change) => ({
    key: change.identity || change.path,
    oldKey: change.oldIdentity || change.oldPath || null,
    status: change.status,
    path: change.path,
    oldPath: change.oldPath || null,
    display: change.oldPath ? `${change.oldPath} → ${change.path}` : change.path,
    pathUndecodable: Boolean(change.pathUndecodable),
  }));
}

function relationJumpParams(responseContext, stateContext, path) {
  // R48-04：关系面板的跳转必须携带**产生该关系的版本上下文**。旧版本关系若
  // 不带 context，openExplorerFile 会回落主浏览 SHA，把旧版本的导入/被依赖
  // 跳到另一个版本的文件上；随后的分页也会继续读错版本。
  const context = responseContext && responseContext.projectId
    ? responseContext : stateContext;
  return { path, startLine: 1, context };
}
