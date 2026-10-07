// Architecture workbench (A role, this round's main entry).
// One adapter conversation with /api/archloop/*: create/open workspaces,
// generate candidates (AI or clearly-labeled dev sample), correct via natural
// language preview, direct-edit nodes/relations/processes with CAS drafts,
// submit human review (refused until the real version backend lands), recheck
// code changes and export fix tasks. Every dev-sample surface stays labeled.
(() => {
  const stage = document.getElementById("arch-map-stage");
  const details = document.getElementById("arch-details-content");
  const NODE_W = 200;
  const NODE_H = 150;

  const state = {
    envelope: null,        // workspace envelope from the server
    pendingCandidate: null, // generation result awaiting user's apply decision
    selectedNodeId: null,
    correctionPreview: null,
    busy: false,
    lastGenerateStatus: null, // survives re-renders (MID-1 finding 11)
    lastGenerateError: false,
  };

  function el(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function svg(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
    return node;
  }

  function short(sha) { return sha ? String(sha).slice(0, 12) : "—"; }

  async function api(method, path, body) {
    const options = { method, headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    let result = null;
    try { result = await response.json(); } catch (error) { result = null; }
    if (!response.ok) {
      const error = (result && result.error) || {};
      const err = new Error(error.message || `请求失败 (${response.status})`);
      err.code = error.code || "HTTP_" + response.status;
      err.details = error.details || {};
      throw err;
    }
    return result;
  }

  function setStatus(id, message, isError) {
    const target = document.getElementById(id);
    if (!target) return;
    target.textContent = message;
    target.classList.toggle("error", Boolean(isError));
  }

  function graph() {
    return state.envelope && state.envelope.draft ? state.envelope.draft.graph : null;
  }

  function requireDraft() {
    const current = graph();
    if (!current) { setStatus("arch-generate-status", "还没有候选图：先生成或载入演示候选。", true); return null; }
    return current;
  }

  // ---------- entry forms ----------

  for (const tab of document.querySelectorAll(".arch-tab")) {
    tab.addEventListener("click", () => {
      for (const other of document.querySelectorAll(".arch-tab")) other.classList.toggle("active", other === tab);
      const planning = tab.dataset.entry === "planning";
      document.getElementById("arch-create-existing").hidden = planning;
      document.getElementById("arch-create-planning").hidden = !planning;
    });
  }

  document.getElementById("arch-create-existing").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      context: "existing_project",
      title: document.getElementById("arch-existing-title").value.trim(),
      repoPath: document.getElementById("arch-repo-path").value.trim(),
      description: document.getElementById("arch-existing-desc").value.trim(),
    };
    if (!payload.title || !payload.repoPath) {
      setStatus("arch-create-status", "请填写仓库路径与工作区名称。", true);
      return;
    }
    setStatus("arch-create-status", "正在创建工作区并读取仓库…");
    try {
      const result = await api("POST", "/api/archloop/workspaces", payload);
      openEnvelope(result);
      await loadHistory();
      setStatus("arch-create-status", `工作区已创建：${result.workspace.workspaceId}（代码 ${short(result.identity.codeRevision)}）`);
    } catch (error) {
      setStatus("arch-create-status", `创建失败：${error.message}`, true);
    }
  });

  document.getElementById("arch-create-planning").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      context: "planning",
      title: document.getElementById("arch-planning-title").value.trim(),
      goals: document.getElementById("arch-planning-goals").value.trim(),
      constraints: document.getElementById("arch-planning-constraints").value.trim(),
    };
    if (!payload.title || !payload.goals) {
      setStatus("arch-create-status", "请填写工作区名称与目标。", true);
      return;
    }
    setStatus("arch-create-status", "正在创建规划工作区…");
    try {
      const result = await api("POST", "/api/archloop/workspaces", payload);
      openEnvelope(result);
      await loadHistory();
      setStatus("arch-create-status", `规划工作区已创建：${result.workspace.workspaceId}（无代码 SHA，属正常状态）`);
    } catch (error) {
      setStatus("arch-create-status", `创建失败：${error.message}`, true);
    }
  });

  async function loadHistory() {
    try {
      const result = await api("GET", "/api/archloop/workspaces");
      const card = document.getElementById("arch-history-card");
      const list = document.getElementById("arch-history-list");
      list.replaceChildren();
      card.hidden = result.workspaces.length === 0;
      for (const workspace of result.workspaces) {
        const row = el("div", "arch-history-row");
        row.append(el("strong", null, workspace.title || workspace.workspaceId),
          el("small", "arch-history-meta", `${workspace.context} · ${workspace.workspaceId}`));
        const open = el("button", "button ghost", "打开 ↗");
        open.type = "button";
        open.addEventListener("click", async () => {
          try { openEnvelope(await api("GET", `/api/archloop/workspaces/${workspace.workspaceId}`)); }
          catch (error) { setStatus("arch-create-status", `打开失败：${error.message}`, true); }
        });
        row.append(open);
        list.append(row);
      }
    } catch (error) { /* history is optional; create/open still work */ }
  }

  // ---------- workspace rendering ----------

  function openEnvelope(envelope) {
    state.envelope = envelope;
    state.pendingCandidate = null;
    state.selectedNodeId = null;
    state.correctionPreview = null;
    document.getElementById("arch-workspace").hidden = false;
    document.getElementById("arch-review-result").replaceChildren();
    document.getElementById("arch-correction-preview").replaceChildren();
    renderWorkspace();
  }

  function setGenStatus(message, isError) {
    state.lastGenerateStatus = message;
    state.lastGenerateError = Boolean(isError);
    const target = document.getElementById("arch-generate-status");
    if (target) {
      target.textContent = message;
      target.classList.toggle("error", Boolean(isError));
    }
  }

  function renderWorkspace() {
    const envelope = state.envelope;
    if (!envelope) return;
    const identity = envelope.identity;
    const planning = envelope.workspace.context === "planning";
    document.getElementById("arch-context-pill").textContent =
      planning ? "planning · 无代码" : `existing · ${short(identity.codeRevision)}`;
    const identityLine = `codeRepoId ${identity.codeRepoId || "—"} · mapId ${identity.mapId || "—"} · 代码 ${short(identity.codeRevision)} · 图 ${short(identity.mapRevision)} · 草稿 ${short(identity.draftRevision)} · mapSource ${short(identity.mapSourceRevision)} · verifiedCode ${short(identity.verifiedCodeRevision)}`;
    document.getElementById("arch-identity-line").textContent = identityLine;

    const banner = document.getElementById("arch-sample-banner");
    if (envelope.backend && envelope.backend.origin === "dev_sample") {
      banner.hidden = false;
      banner.textContent = `演示数据：${envelope.backend.labeled}`;
    } else {
      banner.hidden = true;
    }

    // The latest action's status (incl. machine codes) survives re-renders;
    // only the initial idle hint is derived (MID-1 finding 11).
    const genStatus = document.getElementById("arch-generate-status");
    if (state.lastGenerateStatus !== null) {
      genStatus.textContent = state.lastGenerateStatus;
      genStatus.classList.toggle("error", state.lastGenerateError);
    } else {
      const generation = envelope.generation || {};
      genStatus.textContent = generation.configured
        ? `已就绪：模型 ${generation.model}。点击生成候选图。`
        : (generation.note || "AI 未配置。");
    }

    document.getElementById("arch-recheck-button").hidden = planning;
    const hasDraft = Boolean(graph());
    document.getElementById("arch-review-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-fixtask-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-correction-button").disabled = !hasDraft || !state.selectedNodeId || state.busy;
    document.getElementById("arch-diff-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-gen-count").textContent = hasDraft
      ? `草稿修订 ${short(state.envelope.identity.draftRevision)}`
      : "—";

    renderGraph();
    renderDetails();
    renderCorrectionPreview();
  }

  // ---------- graph rendering ----------

  function autoPositions(nodes) {
    const perRow = 3;
    return nodes.map((node, index) => ({
      x: (index % perRow) * (NODE_W + 24) + 20,
      y: Math.floor(index / perRow) * (NODE_H + 28) + 20,
    }));
  }

  function nodeBadge(node) {
    if (node.provenance === "ai_candidate") return "AI 候选";
    if (node.provenance === "rule_based") return "规则候选";
    if (node.status === "confirmed_design") return "设计已确认";
    if (node.status === "implemented") return "已实现";
    return "候选";
  }

  function renderGraph() {
    const current = graph();
    stage.replaceChildren();
    if (!current) return;
    const positions = autoPositions(current.nodes);
    const width = Math.max(720, (Math.min(current.nodes.length, 3)) * (NODE_W + 24) + 40);
    const rows = Math.ceil(current.nodes.length / 3);
    const height = Math.max(500, rows * (NODE_H + 28) + 40);
    const connections = svg("svg", { class: "connections", viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
    const byId = new Map(current.nodes.map((node, index) => [node.id, positions[index]]));
    for (const edge of current.edges) {
      const from = byId.get(edge.from);
      const to = byId.get(edge.to);
      if (!from || !to) continue;
      const x1 = from.x + NODE_W / 2, y1 = from.y + NODE_H / 2;
      const x2 = to.x + NODE_W / 2, y2 = to.y + NODE_H / 2;
      const active = state.selectedNodeId && (edge.from === state.selectedNodeId || edge.to === state.selectedNodeId);
      connections.append(svg("path", {
        d: `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`,
        class: `connection-line${active ? " active" : ""}`,
      }));
    }
    stage.append(connections);
    current.nodes.forEach((node, index) => {
      const button = el("button", `map-node${node.id === state.selectedNodeId ? " selected" : ""}`);
      button.type = "button";
      button.style.left = `${positions[index].x}px`;
      button.style.top = `${positions[index].y}px`;
      button.style.width = `${NODE_W}px`;
      button.style.height = `${NODE_H}px`;
      button.setAttribute("aria-pressed", String(node.id === state.selectedNodeId));
      button.append(el("span", "node-number", String(index + 1).padStart(2, "0")));
      button.append(el("strong", "node-title", node.title));
      button.append(el("span", "node-summary", node.summary));
      button.append(el("span", "node-review", nodeBadge(node)));
      button.append(el("span", "node-arrow", "↗"));
      button.addEventListener("click", () => { state.selectedNodeId = node.id; renderWorkspace(); });
      stage.append(button);
    });
    document.getElementById("arch-node-count").textContent = `${current.nodes.length} 个功能节点 · ${current.edges.length} 条关系`;
  }

  // ---------- details & editing ----------

  function currentDraftRevision() {
    return state.envelope.identity.draftRevision;
  }

  async function applyOps(operations, note) {
    if (!requireDraft()) return false;
    state.busy = true;
    renderWorkspace();
    setStatus("arch-draft-status", "正在应用修改…");
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/apply-ops`, {
        expectedDraftRevision: currentDraftRevision(),
        operations,
      });
      state.envelope = result;
      setStatus("arch-draft-status", note || "修改已保存到草稿。");
      renderWorkspace();
      return true;
    } catch (error) {
      if (error.code === "REVISION_CONFLICT") {
        setStatus("arch-draft-status", "草稿已被其他窗口修改（版本冲突）。请重新打开工作区，对比差异后再继续。", true);
      } else {
        setStatus("arch-draft-status", `应用失败：${error.message}`, true);
      }
      return false;
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  }

  function labeledField(labelText, input) {
    const wrap = el("label", "arch-wide");
    wrap.append(el("span", "arch-field-label", labelText), input);
    return wrap;
  }

  function renderDetails() {
    details.replaceChildren();
    const current = graph();
    if (!current) {
      details.append(el("div", "empty-details", "还没有候选图。"));
      return;
    }
    const node = current.nodes.find((item) => item.id === state.selectedNodeId);
    if (!node) {
      details.append(el("div", "empty-details", "点击图中节点查看与编辑。"));
      return;
    }

    details.append(el("div", "detail-tag", `${nodeBadge(node)} · ${node.id}`));
    const title = el("h3", "detail-title", node.title);
    details.append(title);

    // responsibility + title editing
    const titleInput = el("input");
    titleInput.value = node.title;
    const summaryInput = el("textarea");
    summaryInput.rows = 3;
    summaryInput.value = node.summary;
    const statusSelect = el("select");
    for (const [value, label] of [["candidate", "候选"], ["confirmed_design", "设计已确认（仍非已实现）"], ["implemented", "已实现"]]) {
      const option = el("option", null, label);
      option.value = value;
      statusSelect.append(option);
    }
    statusSelect.value = node.status;
    const saveBasics = el("button", "button primary", "保存职责修改");
    saveBasics.type = "button";
    saveBasics.addEventListener("click", () => {
      const fields = {};
      if (titleInput.value.trim() && titleInput.value !== node.title) fields.title = titleInput.value.trim();
      if (summaryInput.value.trim() && summaryInput.value !== node.summary) fields.summary = summaryInput.value.trim();
      if (statusSelect.value !== node.status) fields.status = statusSelect.value;
      if (!Object.keys(fields).length) { setStatus("arch-draft-status", "职责没有变化。"); return; }
      applyOps([{ type: "update_node", nodeId: node.id, fields }], "职责修改已保存。");
    });
    const basics = el("section", "detail-section");
    basics.append(el("h4", "section-title", "职责与状态"));
    basics.append(labeledField("名称", titleInput), labeledField("职责说明", summaryInput), labeledField("状态", statusSelect), saveBasics);
    details.append(basics);

    // entry points + interfaces
    const entriesInput = el("input");
    entriesInput.value = (node.entryPoints || []).join(", ");
    const interfacesInput = el("input");
    interfacesInput.value = (node.interfaces || []).join(", ");
    const saveSeams = el("button", "button primary", "保存入口/接口");
    saveSeams.type = "button";
    saveSeams.addEventListener("click", () => {
      const split = (value) => value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
      applyOps([{ type: "update_node", nodeId: node.id,
        fields: { entryPoints: split(entriesInput.value), interfaces: split(interfacesInput.value) } }],
        "入口/接口已保存。");
    });
    const seams = el("section", "detail-section");
    seams.append(el("h4", "section-title", "公开入口 / 团队接口"));
    seams.append(labeledField("入口（逗号分隔）", entriesInput), labeledField("接口（逗号分隔）", interfacesInput), saveSeams);
    details.append(seams);

    // evidence
    const evidenceSection = el("section", "detail-section");
    evidenceSection.append(el("h4", "section-title", `证据 · ${(node.evidence || []).length}`));
    (node.evidence || []).forEach((item, index) => {
      const card = el("div", "evidence-card");
      const top = el("div", "evidence-top");
      top.append(el("code", "evidence-path", item.path),
        el("span", "evidence-status present", item.kind === "requirement" ? "需求依据" : (item.kind === "unknown" ? "未知" : "代码事实")));
      card.append(top, el("p", "evidence-reason", item.reason));
      const remove = el("button", "evidence-button", "移除该证据");
      remove.type = "button";
      remove.addEventListener("click", () => {
        const next = (node.evidence || []).filter((_, i) => i !== index);
        applyOps([{ type: "update_node", nodeId: node.id, fields: { evidence: next } }], "证据已移除。");
      });
      card.append(remove);
      evidenceSection.append(card);
    });
    const pathInput = el("input");
    pathInput.placeholder = "仓库相对路径";
    const reasonInput = el("input");
    reasonInput.placeholder = "为什么相关";
    const addEvidence = el("button", "button ghost", "添加证据");
    addEvidence.type = "button";
    addEvidence.addEventListener("click", () => {
      if (!pathInput.value.trim() || !reasonInput.value.trim()) { setStatus("arch-draft-status", "证据需要路径与理由。", true); return; }
      const next = [...(node.evidence || []), { path: pathInput.value.trim(), reason: reasonInput.value.trim(), kind: "unknown" }];
      applyOps([{ type: "update_node", nodeId: node.id, fields: { evidence: next } }], "证据已添加（默认标记未知，可在确认时说明）。");
    });
    evidenceSection.append(pathInput, reasonInput, addEvidence);
    details.append(evidenceSection);

    renderProcessEditor(node);
    renderRelationEditor(current, node);

    // removal with impact preview
    const danger = el("section", "detail-section");
    danger.append(el("h4", "section-title", "删除节点"));
    const previewImpact = el("button", "button ghost", "查看删除影响");
    previewImpact.type = "button";
    previewImpact.addEventListener("click", async () => {
      try {
        const impact = await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/impact?nodeId=${encodeURIComponent(node.id)}`);
        const lines = [`${impact.edges.length} 条关系、${impact.processReferences.length} 处过程引用将受影响。`];
        danger.replaceChildren(el("h4", "section-title", "删除节点"), el("p", "arch-impact", lines.join("")));
        const confirmRemove = el("button", "button primary", "仍然删除（级联移除关系）");
        confirmRemove.type = "button";
        confirmRemove.addEventListener("click", () => {
          applyOps([{ type: "remove_node", nodeId: node.id, force: impact.edges.length > 0 }], "节点已删除。");
          state.selectedNodeId = null;
        });
        danger.append(confirmRemove);
      } catch (error) {
        setStatus("arch-draft-status", `影响读取失败：${error.message}`, true);
      }
    });
    danger.append(previewImpact);
    details.append(danger);
  }

  function renderProcessEditor(node) {
    const section = el("section", "detail-section");
    section.append(el("h4", "section-title", `期望过程 · ${(node.process || []).length} 步（步骤 ID 保持稳定）`));
    const steps = (node.process || []).map((step) => ({ ...step, inputs: [...(step.inputs || [])], outputs: [...(step.outputs || [])], branches: [...(step.branches || [])], next: [...(step.next || [])] }));
    const rows = [];
    const rebuild = () => {
      section.replaceChildren(el("h4", "section-title", `期望过程 · ${steps.length} 步（步骤 ID 保持稳定）`));
      steps.forEach((step, index) => {
        const row = el("div", "arch-step-row");
        const idTag = el("code", "arch-step-id", step.stepId);
        const titleInput = el("input");
        titleInput.value = step.title;
        titleInput.addEventListener("change", () => { step.title = titleInput.value; });
        const detailInput = el("input");
        detailInput.value = step.detail || "";
        detailInput.placeholder = "这一步发生什么";
        detailInput.addEventListener("change", () => { step.detail = detailInput.value; });
        const lists = el("input");
        lists.value = [step.inputs, step.outputs, step.branches].map((list) => list.join("/")).join(" | ");
        lists.placeholder = "输入/输出/分支，用 | 分隔";
        lists.addEventListener("change", () => {
          const [inputs, outputs, branches] = lists.value.split("|").map((part) => part.split("/").map((item) => item.trim()).filter(Boolean));
          step.inputs = inputs || []; step.outputs = outputs || []; step.branches = branches || [];
        });
        const up = el("button", "button ghost", "↑");
        up.type = "button";
        up.addEventListener("click", () => { if (index > 0) { [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]]; rebuild(); } });
        const down = el("button", "button ghost", "↓");
        down.type = "button";
        down.addEventListener("click", () => { if (index < steps.length - 1) { [steps[index + 1], steps[index]] = [steps[index], steps[index + 1]]; rebuild(); } });
        const remove = el("button", "button ghost", "删");
        remove.type = "button";
        remove.addEventListener("click", () => { steps.splice(index, 1); rebuild(); });
        row.append(idTag, titleInput, detailInput, lists, up, down, remove);
        section.append(row);
      });
      const actions = el("div", "arch-step-actions");
      const add = el("button", "button ghost", "添加步骤");
      add.type = "button";
      add.addEventListener("click", () => {
        let suffix = steps.length + 1;
        let stepId = `s${suffix}`;
        while (steps.some((step) => step.stepId === stepId)) { suffix += 1; stepId = `s${suffix}`; }
        steps.push({ stepId, title: "新步骤", detail: "", inputs: [], outputs: [], branches: [], next: [] });
        rebuild();
      });
      const save = el("button", "button primary", "保存过程");
      save.type = "button";
      save.addEventListener("click", () => {
        for (const step of steps) step.next = step.next.filter((entry) => steps.some((other) => other.stepId === entry));
        applyOps([{ type: "update_process", nodeId: node.id, process: steps }], "过程已保存（stepId 保持不变）。");
      });
      actions.append(add, save);
      section.append(actions);
    };
    rows.push(rebuild);
    rebuild();
    details.append(section);
  }

  function renderRelationEditor(current, node) {
    const section = el("section", "detail-section");
    section.append(el("h4", "section-title", `关系 · ${current.edges.filter((edge) => edge.from === node.id || edge.to === node.id).length}`));
    for (const edge of current.edges) {
      if (edge.from !== node.id && edge.to !== node.id) continue;
      const other = current.nodes.find((item) => item.id === (edge.from === node.id ? edge.to : edge.from));
      const row = el("div", "relation-row");
      row.append(el("span", "relation-symbol", edge.from === node.id ? "→" : "←"),
        el("span", "relation-name", other ? other.title : edge.to),
        el("small", "relation-label", `${edge.type} · ${edge.label}`));
      const remove = el("button", "evidence-button", "删除");
      remove.type = "button";
      remove.addEventListener("click", () => {
        applyOps([{ type: "remove_edge", match: { from: edge.from, to: edge.to, type: edge.type } }], "关系已删除。");
      });
      row.append(remove);
      section.append(row);
    }
    const targets = el("select");
    for (const option of current.nodes) {
      if (option.id === node.id) continue;
      const item = el("option", null, option.title);
      item.value = option.id;
      targets.append(item);
    }
    const typeSelect = el("select");
    for (const [value, label] of [["static_reference", "静态引用"], ["functional_collaboration", "功能协作"], ["expected_sequence", "期望先后"]]) {
      const item = el("option", null, label);
      item.value = value;
      typeSelect.append(item);
    }
    const labelInput = el("input");
    labelInput.placeholder = "关系说明";
    const addEdge = el("button", "button ghost", "添加关系到所选目标");
    addEdge.type = "button";
    addEdge.addEventListener("click", () => {
      if (!targets.value || !labelInput.value.trim()) { setStatus("arch-draft-status", "请选择目标节点并填写关系说明。", true); return; }
      applyOps([{ type: "add_edge", edge: { from: node.id, to: targets.value, type: typeSelect.value, label: labelInput.value.trim() } }], "关系已添加。");
    });
    const addReverse = el("button", "button ghost", "从目标添加到本节点");
    addReverse.type = "button";
    addReverse.addEventListener("click", () => {
      if (!targets.value || !labelInput.value.trim()) { setStatus("arch-draft-status", "请选择来源节点并填写关系说明。", true); return; }
      applyOps([{ type: "add_edge", edge: { from: targets.value, to: node.id, type: typeSelect.value, label: labelInput.value.trim() } }], "关系已添加。");
    });
    section.append(labeledField("目标节点", targets), labeledField("关系类型", typeSelect), labeledField("说明", labelInput), addEdge, addReverse);
    details.append(section);

    const addNode = el("section", "detail-section");
    addNode.append(el("h4", "section-title", "新增功能节点"));
    const newNodeTitle = el("input");
    newNodeTitle.placeholder = "新节点名称";
    const newNodeSummary = el("input");
    newNodeSummary.placeholder = "职责说明";
    const createNode = el("button", "button primary", "添加节点");
    createNode.type = "button";
    createNode.addEventListener("click", () => {
      if (!newNodeTitle.value.trim()) { setStatus("arch-draft-status", "请填写节点名称。", true); return; }
      const nodeId = `n_${Date.now().toString(36)}`;
      applyOps([{ type: "add_node", node: { id: nodeId, title: newNodeTitle.value.trim(), summary: newNodeSummary.value.trim() || "（待补充职责）", status: "candidate", provenance: "human_input", entryPoints: [], interfaces: [], evidence: [], process: [] } }], "节点已添加。");
    });
    addNode.append(labeledField("名称", newNodeTitle), labeledField("职责", newNodeSummary), createNode);
    details.append(addNode);
  }

  // ---------- generation ----------

  document.getElementById("arch-generate-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    state.busy = true;
    renderWorkspace();
    setGenStatus("正在调用已配置模型生成候选图…（最长约 1 分钟）");
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/generate`, {});
      if (result.status === "ai_generated") {
        state.pendingCandidate = result;
        showCandidateForApply(result, "AI 候选图已生成。请检查后点击「应用到草稿」。");
      } else {
        setGenStatus(`${result.status}：${result.note}`, true);
      }
    } catch (error) {
      setGenStatus(`生成失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  document.getElementById("arch-sample-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    state.busy = true;
    renderWorkspace();
    setGenStatus("正在载入演示样例…");
    try {
      const planning = state.envelope.workspace.context === "planning";
      const sample = await api("GET", `/api/archloop/sample-graph?context=${planning ? "planning" : "existing_project"}`);
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/generate`,
        { mode: "dev_sample", sampleGraph: sample.graph });
      if (result.status === "dev_sample") {
        state.pendingCandidate = result;
        showCandidateForApply(result, "演示候选已载入（明确标注：非真实 AI 生成）。");
        const banner = document.getElementById("arch-sample-banner");
        banner.hidden = false;
        banner.textContent = "演示数据：当前候选是明确标注的开发样例，用于验证界面交互，不代表 AI 分析结果。";
      } else {
        setGenStatus(`${result.status}：${result.note}`, true);
      }
    } catch (error) {
      setGenStatus(`载入失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  function showCandidateForApply(result, message) {
    setGenStatus(message);
    const area = document.getElementById("arch-review-result");
    area.replaceChildren();
    const apply = el("button", "button primary", "应用到草稿");
    apply.type = "button";
    apply.addEventListener("click", async () => {
      try {
        // apply by candidateId: the server-stored candidate (with its real
        // origin) is the only thing that can become a draft
        const envelope = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/apply-candidate`,
          { candidateId: result.candidateId, expectedDraftRevision: state.envelope.identity.draftRevision });
        state.pendingCandidate = null;
        openEnvelope(envelope);
        setGenStatus(result.status === "dev_sample"
          ? "演示候选已作为草稿（标注保留）。"
          : "AI 候选已应用为草稿（全部节点仍为候选状态）。");
      } catch (error) {
        setGenStatus(`应用失败（${error.code}）：${error.message}`, true);
      }
    });
    const discard = el("button", "button ghost", "放弃该候选");
    discard.type = "button";
    discard.addEventListener("click", () => { state.pendingCandidate = null; area.replaceChildren(); setGenStatus("候选已放弃。"); });
    area.append(el("p", "ai-provenance", result.note), apply, discard);
  }

  // ---------- correction ----------

  document.getElementById("arch-correction-button").addEventListener("click", async () => {
    if (!state.envelope || !state.selectedNodeId || state.busy) return;
    const instruction = document.getElementById("arch-correction-input").value.trim();
    if (!instruction) { setStatus("arch-correction-status", "请先描述要纠正的内容。", true); return; }
    state.busy = true;
    renderWorkspace();
    setStatus("arch-correction-status", "正在生成纠正预览…");
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/correction-preview`, {
        expectedDraftRevision: currentDraftRevision(),
        instruction,
        selectedNodeIds: [state.selectedNodeId],
        mode: "dev_sample", // until C's real backend is registered; responses stay labeled
      });
      state.correctionPreview = result;
      renderCorrectionPreview();
      setStatus("arch-correction-status", result.origin === "dev_sample"
        ? "演示纠正预览（本地规则生成，非 AI）。确认后应用到草稿。"
        : "纠正预览已生成。");
    } catch (error) {
      setStatus("arch-correction-status", `预览失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  function renderCorrectionPreview() {
    const area = document.getElementById("arch-correction-preview");
    area.replaceChildren();
    const preview = state.correctionPreview;
    if (!preview) return;
    // a preview based on an older draft revision is void (MID-1 finding 9)
    if (preview.baseDraftRevision !== state.envelope.identity.draftRevision) {
      state.correctionPreview = null;
      area.append(el("div", "review-notice", "纠正预览已过期（草稿在此期间发生了变化）；请重新生成预览。"));
      return;
    }
    const label = el("div", "ai-candidate-label", preview.origin === "dev_sample"
      ? "演示纠正预览 · 非真实 AI 输出" : "纠正预览");
    area.append(label);
    const changed = preview.diff || {};
    for (const node of changed.nodes || []) {
      area.append(el("p", "ai-item", `节点 ${node.id}（${node.title || ""}）：${node.change}${node.fields ? ` · ${node.fields.join("、")}` : ""}`));
    }
    for (const edge of changed.edges?.added || []) area.append(el("p", "ai-item", `新增关系 ${edge.from} → ${edge.to}`));
    for (const edge of changed.edges?.removed || []) area.append(el("p", "ai-item", `移除关系 ${edge.from} → ${edge.to}`));
    const apply = el("button", "button primary", "应用到草稿");
    apply.type = "button";
    apply.addEventListener("click", async () => {
      try {
        // apply by proposalId with the preview's own basis revision; the
        // server re-checks expiry under the workspace lock
        const envelope = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/apply-correction`,
          { proposalId: preview.proposalId, expectedDraftRevision: preview.baseDraftRevision });
        state.correctionPreview = null;
        state.envelope = envelope;
        setStatus("arch-draft-status", "纠正已应用到草稿。");
        renderCorrectionPreview();
        renderWorkspace();
      } catch (error) {
        setStatus("arch-draft-status", `应用失败（${error.code}）：${error.message}`, true);
      }
    });
    const discard = el("button", "button ghost", "放弃纠正");
    discard.type = "button";
    discard.addEventListener("click", () => { state.correctionPreview = null; renderCorrectionPreview(); setStatus("arch-correction-status", "纠正已放弃。"); });
    area.append(apply, discard);
  }

  // ---------- review / publish ----------

  document.getElementById("arch-review-button").addEventListener("click", async () => {
    if (!state.envelope || !graph() || state.busy) return;
    const actor = window.prompt("确认并保存版本：请输入复核人（本机操作者声明）");
    if (!actor) return;
    const reason = window.prompt("复核理由（将随决定一起记录）") || "";
    state.busy = true;
    renderWorkspace();
    try {
      await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/review`, {
        expectedMapRevision: graph().mapRevision,
        decision: "accept",
        actor,
        reason,
      });
      setStatus("arch-review-status", "版本已保存。");
    } catch (error) {
      const area = document.getElementById("arch-review-result");
      area.replaceChildren();
      if (error.code === "BACKEND_UNAVAILABLE") {
        area.append(el("div", "review-notice",
          `如实说明：${error.message} 决定已记录在草稿历史（decision: accept，actor: ${actor}），但当前没有产生任何正式认知版本。`));
        setStatus("arch-review-status", "人审后端未接入：决定已记录，版本未产生。", true);
      } else if (error.code === "REVISION_CONFLICT") {
        setStatus("arch-review-status", "图版本已变化，请刷新后按最新预览重试。", true);
      } else {
        setStatus("arch-review-status", `提交失败（${error.code}）：${error.message}`, true);
      }
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  // ---------- fix task ----------

  document.getElementById("arch-fixtask-button").addEventListener("click", async () => {
    if (!state.envelope || !graph() || state.busy) return;
    const deviation = window.prompt("偏差描述：期望过程与实际观察有什么差异？");
    if (!deviation) return;
    const acceptance = window.prompt("验收标准（实施者提交什么算修复）") || "";
    state.busy = true;
    renderWorkspace();
    try {
      const task = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/fix-task`, {
        deviation,
        acceptance,
        expectedProcessRef: state.selectedNodeId,
        mode: "dev_sample",
      });
      const area = document.getElementById("arch-review-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", task.labeled || "修正实现任务"));
      area.append(el("p", "ai-item", `任务 ${task.deviationId} · 状态 ${task.status}`));
      area.append(el("p", "ai-item", task.observation));
      area.append(el("p", "ai-provenance", task.note));
      setStatus("arch-review-status", "演示任务已生成（真实交接后端接入前仅为样例）。");
    } catch (error) {
      setStatus("arch-review-status", `任务创建失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  // ---------- recheck & diff ----------

  document.getElementById("arch-recheck-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    state.busy = true;
    renderWorkspace();
    setStatus("arch-generate-status", "正在检查代码变化…");
    try {
      // POST: recheck mutates workspace state, so it sits behind the same
      // loopback/Origin protection as every other write (MID-1 finding 12)
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/recheck`, {});
      const area = document.getElementById("arch-recheck-result");
      area.replaceChildren();
      area.append(el("p", "ai-provenance", `${short(result.oldCodeRevision)} → ${short(result.newCodeRevision)}${result.changed ? "（代码已前进）" : "（无变化）"}`));
      if (result.note) area.append(el("p", "ai-item", result.note));
      for (const node of result.staleNodes || []) {
        area.append(el("p", "ai-item", `待复核节点：${node.title}（${node.paths.join("、")}）`));
      }
      if (result.changed) {
        const rebind = el("button", "button ghost", "复核完成后回挂到当前 HEAD");
        rebind.type = "button";
        rebind.addEventListener("click", async () => {
          const actor = window.prompt("回挂需要复核人（本机操作者声明）");
          if (!actor) return;
          try {
            const envelope = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/rebind`,
              { expectedNewCodeRevision: result.newCodeRevision, actor, note: "复核后回挂" });
            state.envelope = envelope;
            setGenStatus("已回挂到新提交（本地记录；verifiedCodeRevision 仍为空，等待独立验证）。");
            renderWorkspace();
          } catch (error) {
            setGenStatus(`回挂失败（${error.code}）：${error.message}`, true);
          }
        });
        area.append(rebind);
      }
      setGenStatus(result.changed ? "代码有新提交，请复核列出的节点。" : "代码没有新提交。");
    } catch (error) {
      setStatus("arch-generate-status", `复核失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  document.getElementById("arch-diff-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      const diff = await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/diff`);
      const area = document.getElementById("arch-review-result");
      area.replaceChildren();
      area.append(el("h3", "section-title", "候选前后对照（基准候选 → 当前草稿）"));
      const changedNodes = diff.nodes || [];
      if (!changedNodes.length && !(diff.edges?.added || []).length && !(diff.edges?.removed || []).length) {
        area.append(el("p", "ai-item", "与基准候选没有语义差异（仅布局或无变化）。"));
      }
      for (const node of changedNodes) {
        area.append(el("p", "ai-item", `节点 ${node.id}（${node.title || ""}）：${node.change}${node.fields ? ` · ${node.fields.join("、")}` : ""}`));
      }
      for (const edge of diff.edges?.added || []) area.append(el("p", "ai-item", `新增关系 ${edge.from} → ${edge.to}（${edge.type}）`));
      for (const edge of diff.edges?.removed || []) area.append(el("p", "ai-item", `移除关系 ${edge.from} → ${edge.to}（${edge.type}）`));
    } catch (error) {
      setStatus("arch-draft-status", `差异读取失败：${error.message}`, true);
    }
  });

  // ---------- boot ----------

  loadHistory();
})();
