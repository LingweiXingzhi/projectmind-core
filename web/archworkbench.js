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
  const NODE_H = 132;
  let inspectorTab = 'overview';
  let canvasTab = 'canvas';
  let zoom = 1;
  let nodePositions = {};
  let workspacePaths={};

  // Window-local edit buffers: never silently submit, approve, or persist input.
  const editorBuffers = new Map();
  const editorKey = (nodeId, group) => `${state.envelope.workspace.workspaceId}|${nodeId}|${group}`;
  function buffered(nodeId, group, baseline) {
    return structuredClone(editorBuffers.get(editorKey(nodeId, group))?.value ?? baseline);
  }
  function bufferValue(nodeId, group, value, baseline) {
    const key = editorKey(nodeId, group);
    if (JSON.stringify(value) === JSON.stringify(baseline)) editorBuffers.delete(key);
    else editorBuffers.set(key, {nodeId, group, value:structuredClone(value)});
    emitWorkspace();
  }
  function bindEditor(input, nodeId, group, baseline) {
    input.value = buffered(nodeId, group, baseline);
    const record = () => bufferValue(nodeId, group, input.value, baseline);
    input.addEventListener('input', record); input.addEventListener('change', record);
  }
  function pendingEditors() {
    const prefix = `${state.envelope?.workspace.workspaceId}|`;
    return [...editorBuffers].filter(([key]) => key.startsWith(prefix)).map(([,value]) => ({nodeId:value.nodeId, group:value.group}));
  }
  function clearEditorGroups(nodeId, groups) {
    const prefix=editorKey(nodeId, '');
    for (const key of editorBuffers.keys()) if(key.startsWith(prefix) && groups.some(group=>group==='*' || key.slice(prefix.length).startsWith(group))) editorBuffers.delete(key);
  }
  function requireSavedEditors() {
    const pending=pendingEditors();
    if(!pending.length)return true;
    document.dispatchEvent(new CustomEvent('projectmind:select-node', {detail:pending[0].nodeId}));
    openNodeEditor();
    setStatus('arch-draft-status','还有未保存的编辑。请先保存或放弃这些输入，再生成候选、确认版本或创建任务。',true);
    return false;
  }
  window.addEventListener('beforeunload',event=>{
    if(editorBuffers.size){event.preventDefault();event.returnValue='';}
  });
  document.addEventListener('projectmind:discard-edits',event=>{
    clearEditorGroups(event.detail, ['*']);renderWorkspace();
  });


  try{workspacePaths=JSON.parse(localStorage.getItem('projectmind:workspace-paths')||'{}')||{};}catch(e){}
  function rememberPath(id,path){workspacePaths[id]=path;try{localStorage.setItem('projectmind:workspace-paths',JSON.stringify(workspacePaths));}catch(e){}}

  const correctionCard = document.getElementById('arch-correction-card');
  const inspector = details.closest('.details');
  inspector.append(correctionCard);
  const inspectorClose=document.createElement('button');inspectorClose.type='button';
  inspectorClose.id='ux-inspector-close';inspectorClose.className='button ghost';inspectorClose.textContent='返回功能图';
  inspectorClose.onclick=()=>{inspector.classList.remove('ux-inspector-open');document.getElementById('arch-canvas-scroll').scrollIntoView({block:'center',behavior:'smooth'});};
  inspector.querySelector('.details-heading').append(inspectorClose);
  const inspectorMessage=document.createElement('p');inspectorMessage.id='ux-editor-status';inspectorMessage.className='ux-editor-status';inspectorMessage.setAttribute('role','status');
  inspector.querySelector('.details-heading').after(inspectorMessage);
  document.addEventListener('projectmind:close-inspector',()=>inspector.classList.remove('ux-inspector-open'));
  function focusInspector(){document.body.classList.remove('inspector-hidden');inspector.classList.add('ux-inspector-open');inspectorMessage.textContent='';if(window.innerWidth<=900)inspectorClose.focus({preventScroll:true});}


  function emitWorkspace() {
    if(state.envelope)document.dispatchEvent(new CustomEvent('projectmind:workspace', {detail:state.envelope}));
    document.dispatchEvent(new CustomEvent('projectmind:guide-state', {detail:{
      envelope:state.envelope, selectedNodeId:state.selectedNodeId, busy:state.busy,
      pendingCandidate:Boolean(state.pendingCandidate), syncedRevision:state.syncedRevision,
      review:{...reviewFlow}, unsaved:pendingEditors(),
    }}));
  }
  function positionKey(){return `projectmind:arch-layout:${state.envelope?.workspace.workspaceId}`;}
  function setZoom(value){zoom=Math.max(.4,Math.min(1.6,value));stage.style.transform=`scale(${zoom})`;document.getElementById('canvas-zoom').textContent=`${Math.round(zoom*100)}%`;}
  document.getElementById('canvas-zoom-in').onclick=()=>setZoom(zoom+.1);
  document.getElementById('canvas-zoom-out').onclick=()=>setZoom(zoom-.1);
  document.getElementById('canvas-fit').onclick=()=>{const scroll=document.getElementById('arch-canvas-scroll');setZoom(Math.min(1,(scroll.clientWidth-60)/(parseFloat(stage.style.width)||720)));scroll.scrollLeft=scroll.scrollTop=0;};
  let pan=null;
  const scroll=document.getElementById('arch-canvas-scroll');
  scroll.addEventListener('pointerdown',e=>{if(e.target.closest('.map-node,[data-edge-edit]')||e.button!==0)return;pan={x:e.clientX,y:e.clientY,left:scroll.scrollLeft,top:scroll.scrollTop};scroll.setPointerCapture(e.pointerId);scroll.style.cursor='grabbing';});
  scroll.addEventListener('pointermove',e=>{if(pan){scroll.scrollLeft=pan.left+pan.x-e.clientX;scroll.scrollTop=pan.top+pan.y-e.clientY;}});
  for(const type of ['pointerup','pointercancel'])scroll.addEventListener(type,()=>{pan=null;scroll.style.cursor='';});
  for(const tab of document.querySelectorAll('[data-arch-tab]'))tab.onclick=()=>{canvasTab=tab.dataset.archTab;renderCanvasTab();};
  function renderCanvasTab(){
    for(const tab of document.querySelectorAll('[data-arch-tab]'))tab.classList.toggle('active',tab.dataset.archTab===canvasTab);
    const mapCard=stage.closest('.map-card');mapCard.hidden=canvasTab!=='canvas';
    document.getElementById('arch-outline').hidden=canvasTab!=='outline';
    document.getElementById('arch-history-card').hidden=canvasTab!=='versions';
  }
  function beginEntry(context) {
    state.envelope=null;state.pendingCandidate=null;state.selectedNodeId=null;state.lastGenerateStatus=null;state.syncedRevision=null;
    clearReview();
    document.getElementById('view-arch').classList.remove('has-workspace');
    document.getElementById('arch-entry-card').hidden=false;
    document.getElementById('arch-workspace').hidden=true;
    document.querySelector(`.arch-tab[data-entry="${context==='planning'?'planning':'existing'}"]`).click();
    loadHistory();emitWorkspace();
  }
  document.getElementById('arch-new-workspace').onclick=()=>{beginEntry();document.dispatchEvent(new CustomEvent('projectmind:choose-entry'));};
  document.addEventListener('projectmind:begin-entry',event=>beginEntry(event.detail));
  document.getElementById('arch-add-node').onclick=async()=>{
    if(!requireDraft())return;
    const form=await workspaceDialog('新增架构节点',[['title','名称'],['summary','职责说明','textarea']], '添加到草稿');if(!form)return;
    const title=form.title;
    const id=`n_${Date.now().toString(36)}`;
    const ok=await applyOps([{type:'add_node',node:{id,title:title.trim(),summary:form.summary||'待补充职责',status:'candidate',provenance:'human_input',entryPoints:[],interfaces:[],evidence:[],process:[]}}],'节点已添加到草稿。');
    if(ok){state.selectedNodeId=id;inspectorTab='edit';renderWorkspace();}
  };
  document.addEventListener('projectmind:open-workspace',async event=>{try{openEnvelope(await api('GET',`/api/archloop/workspaces/${encodeURIComponent(event.detail)}`));}catch(error){setStatus('arch-create-status',error.message,true);}});
  document.addEventListener('projectmind:select-node',event=>{if(graph()?.nodes.some(n=>n.id===event.detail)){state.selectedNodeId=event.detail;inspectorTab='overview';focusInspector();renderWorkspace();}});
  function openNodeEditor(section='basics', edgeMatch=null) {
    if(!graph()?.nodes.some(n=>n.id===state.selectedNodeId))return;
    focusInspector();inspectorTab='edit';renderWorkspace();
    const editorIds={relations:'arch-relation-editor',process:'arch-process-editor',evidence:'arch-evidence-editor',basics:'arch-basics-editor'};
    let target=document.getElementById(editorIds[section]||editorIds.basics);
    if(edgeMatch){const form=[...target.querySelectorAll('.ux-relation-edit')].find(item=>item.dataset.from===edgeMatch.from&&item.dataset.to===edgeMatch.to&&item.dataset.type===edgeMatch.type);if(form){form.open=true;target=form;}}
    target?.scrollIntoView({block:'start',behavior:'smooth'});target?.querySelector('input,select')?.focus({preventScroll:true});
  }
  document.addEventListener('projectmind:edit-node',event=>openNodeEditor(event.detail?.section));


  const state = {
    envelope: null,        // workspace envelope from the server
    pendingCandidate: null, // generation result awaiting user's apply decision
    selectedNodeId: null,
    correctionPreview: null,
    busy: false,
    lastGenerateStatus: null, // survives re-renders (MID-1 finding 11)
    lastGenerateError: false,
    syncedRevision: null, // this browser's successful sync, never inferred approval
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


  function workspaceDialog(title, fields, action='继续') {
    return new Promise(resolve=>{
      const dialog=el('dialog','workspace-dialog');const form=el('form');form.method='dialog';
      form.append(el('h2',null,title));const inputs={};
      for (const [id, label, type] of fields) {
        const session = window.projectmindSession;
        const registered = id === 'repoPath' && session;
        const choices=Array.isArray(type)?{options:type}:type&&typeof type==='object'?type:null;
        const input = el(registered || choices ? 'select' : type === 'textarea' ? 'textarea' : 'input');
        if(choices){input.multiple=Boolean(choices.multiple);for(const choice of choices.options){const option=el('option',null,choice.label);option.value=choice.value;option.selected=Boolean(choice.selected);input.append(option);}}
        input.name = id; input.required = ['title','actor','operator','deviation','acceptance','repoPath','reason','processRef','evidencePaths'].includes(id);
        if (type === 'textarea') input.rows = 3;
        if (registered) for (const repo of session.repositories) {
          const option = el('option', null, repo.label); option.value = repo.key; input.append(option);
        }
        if(['actor','operator'].includes(id)&&!session)input.value=writeSession.operator||'';
        if (id === 'actor' && session) { input.value = session.actor; input.readOnly = true; }
        const name = registered ? '服务器登记的代码仓库' : id === 'actor' && session ? '登录账户' : label;
        input.setAttribute('aria-label', name); inputs[id] = input; form.append(labeledField(name, input));
      }
      const buttons=el('div','dialog-actions');const cancel=el('button','button ghost','取消');cancel.type='button';cancel.onclick=()=>dialog.close('cancel');const submit=el('button','button primary',action);submit.type='submit';buttons.append(cancel,submit);form.append(buttons);dialog.append(form);document.body.append(dialog);
      form.addEventListener('submit',event=>{event.preventDefault();if(!form.reportValidity())return;dialog.close('submit');});
      dialog.addEventListener('close',()=>{resolve(dialog.returnValue==='submit'?Object.fromEntries(Object.entries(inputs).map(([id,input])=>[id,input.multiple?[...input.selectedOptions].map(option=>option.value):input.value.trim()])):null);dialog.remove();},{once:true});dialog.showModal();Object.values(inputs)[0]?.focus();
    });
  }

  function short(sha) { return sha ? String(sha).slice(0, 12) : "—"; }

  // Server-side write session (CONTRACT_V1 write seam): every POST needs the
  // session cookie plus this anti-forgery header, and the same session carries
  // the declared local operator that human review and fix tasks are bound to.
  const writeSession = { csrfToken: null, operator: null, pending: null };

  async function ensureSession(operator) {
    const wanted = operator === undefined ? writeSession.operator : (operator || "");
    if (writeSession.csrfToken && wanted === writeSession.operator) return writeSession;
    if (writeSession.pending) return writeSession.pending;
    writeSession.pending = (async () => {
      const suffix = wanted ? `?operator=${encodeURIComponent(wanted)}` : "";
      const response = await fetch(`/api/archloop/session${suffix}`, { method: "GET" });
      const body = await response.json();
      if (!response.ok) throw new Error("无法建立写会话");
      writeSession.csrfToken = body.csrfToken;
      writeSession.operator = (body.session && body.session.operator) || "";
      return writeSession;
    })();
    try { return await writeSession.pending; } finally { writeSession.pending = null; }
  }

  window.projectmindAISettingsRequest = async (path, body, method='POST') => {
    const target=new URL(path,location.origin);
    if(target.origin!==location.origin||!['/api/ai-settings','/api/ai-settings/test','/api/ai-settings/check','/api/ai-settings/select'].includes(target.pathname))throw Error('无效的 AI 配置操作');
    if(method==='GET')await ensureSession();
    return api(method,path,body);
  };
  async function api(method, path, body) {
    const options = { method, headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    } else if (method !== "GET") {
      options.headers["Content-Type"] = "application/json";
      options.body = "{}";
    }
    if (method !== "GET") {
      await ensureSession();
      if (writeSession.csrfToken) options.headers["X-CSRF-Token"] = writeSession.csrfToken;
    }
    let response = await fetch(path, options);
    let result = null;
    try { result = await response.json(); } catch (error) { result = null; }
    const code = result && result.error && result.error.code;
    if (!response.ok && (code === "FORBIDDEN_SESSION" || code === "FORBIDDEN_CSRF")) {
      writeSession.csrfToken = null;
      await ensureSession();
      options.headers["X-CSRF-Token"] = writeSession.csrfToken;
      response = await fetch(path, options);
      try { result = await response.json(); } catch (error) { result = null; }
    }
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
    if(id==="arch-draft-status"){inspectorMessage.textContent=message;inspectorMessage.classList.toggle("error",Boolean(isError));}
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
      rememberPath(result.workspace.workspaceId,payload.repoPath);
      openEnvelope(result);
      await loadHistory();
      setStatus("arch-create-status", `工作区已创建：${result.workspace.workspaceId}（代码 ${short(result.identity.codeRevision)}）`);
    } catch (error) {
      setStatus("arch-create-status", `未能导入项目：${error.message}`, true);
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
      setStatus("arch-create-status", `未能保存项目想法：${error.message}`, true);
    }
  });

  async function loadHistory() {
    try {
      const result = await api("GET", "/api/archloop/workspaces");
      const card = document.getElementById("arch-history-card");
      const list = document.getElementById("arch-history-list");
      list.replaceChildren();
      card.hidden = Boolean(state.envelope) ? canvasTab!=="versions" : result.workspaces.length === 0;
      for (const workspace of result.workspaces) {
        const row = el("div", "arch-history-row");
        row.append(el("strong", null, workspace.title || workspace.workspaceId),
          el("small", "arch-history-meta", `${projectmindUiLabel(workspace.context)} · ${workspace.workspaceId}`));
        const open = el("button", "button ghost", "打开 ↗");
        open.type = "button";
        open.addEventListener("click", async () => {
          try { openEnvelope(await api("GET", `/api/archloop/workspaces/${workspace.workspaceId}`)); }
          catch (error) { setStatus("arch-create-status", `打开失败（${error.code}）：${error.message}`, true); }
        });
        row.append(open);
        list.append(row);
      }
    } catch (error) { /* history is optional; create/open still work */ }
  }

  // ---------- workspace rendering ----------

  function openEnvelope(envelope) {
    clearReview();
    const sameWorkspace=state.envelope?.workspace.workspaceId===envelope.workspace.workspaceId;
    const keepNode=sameWorkspace&&envelope.draft?.graph.nodes.some(n=>n.id===state.selectedNodeId)?state.selectedNodeId:null;
    if(!sameWorkspace){state.lastGenerateStatus=null;state.lastGenerateError=false;}
    state.envelope = envelope;
    try { const saved=JSON.parse(localStorage.getItem(positionKey())||'{}');nodePositions=Object.fromEntries(Object.entries(saved||{}).filter(([id,p])=>p&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&p.x>=0&&p.y>=0&&p.x<10000&&p.y<10000)); } catch(e){nodePositions={};}
    try { localStorage.setItem('projectmind:last-workspace',envelope.workspace.workspaceId); } catch(e){}
    inspectorTab='overview';canvasTab='canvas';
    document.getElementById('view-arch').classList.add('has-workspace');
    document.getElementById('arch-entry-card').hidden=true;
    document.getElementById('arch-history-card').hidden=true;
    document.getElementById('arch-add-node').disabled=!envelope.draft;
    state.pendingCandidate = null;
    state.selectedNodeId = keepNode;
    state.correctionPreview = null;
    if(state.syncedRevision!==envelope.identity.draftRevision)state.syncedRevision=null;
    document.getElementById("arch-correction-input").value="";
    document.getElementById("arch-workspace").hidden = false;
    document.getElementById("ux-generation-panel").open = !envelope.draft;
    document.getElementById("arch-review-result").replaceChildren();
    document.getElementById('arch-candidate-preview').replaceChildren();
    document.getElementById('arch-candidate-preview').hidden=true;
    document.getElementById("arch-correction-preview").replaceChildren();
    renderWorkspace();
    document.getElementById('view-arch').scrollTop=0;
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
      planning ? "新项目规划 · 无代码" : `已有项目 · ${short(identity.codeRevision)}`;
    const identityLine = `代码仓库标识 ${identity.codeRepoId || "—"} · 图标识 ${identity.mapId || "—"} · 代码 ${short(identity.codeRevision)} · 图 ${short(identity.mapRevision)} · 草稿 ${short(identity.draftRevision)} · 架构来源 ${short(identity.mapSourceRevision)} · 已核查代码 ${short(identity.verifiedCodeRevision)}`;
    document.getElementById("arch-identity-line").textContent = identityLine;

    const banner = document.getElementById("arch-sample-banner");
    const contentIsSample = Boolean(envelope.draft && (envelope.draft.origin === "dev_sample"
      || (envelope.draft.lineage || []).includes("dev_sample")));
    if (contentIsSample) {
      // content-based marking survives backend registration (FINAL-2 F4)
      banner.hidden = false;
      banner.textContent = "演示数据：当前草稿的来源链包含开发样例；它不能提交人审或发布版本。";
    } else if (envelope.backend && envelope.backend.origin === "dev_sample") {
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
        ? `已就绪：${generation.model} @ ${generation.provider || "已配置端点"}`
          + `${generation.protocol ? "（" + generation.protocol + "）" : ""}。点击生成候选图。`
        : (generation.note || "AI 未配置。");
    }

    document.getElementById("arch-recheck-button").hidden = planning;
    document.getElementById("arch-rulegen-button").textContent=planning?"根据目标起草（规则候选）":"根据代码起草（规则候选）";
    const hasDraft = Boolean(graph());
    document.getElementById("arch-map-heading").textContent=identity.mapSourceRevision?"项目功能图 · 已发布版本":"项目功能图 · 当前草稿";
    document.getElementById("arch-add-node").disabled=!hasDraft||state.busy;
    document.getElementById("arch-sync-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-review-preview-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-sync-button").hidden=Boolean(reviewFlow.previewDigest);
    document.getElementById("arch-review-preview-button").hidden=Boolean(reviewFlow.previewDigest);
    document.getElementById("arch-review-mode").disabled=state.busy||Boolean(reviewFlow.previewDigest);
    for(const id of ['arch-review-confirm-button','arch-review-reject-button']){
      const b=document.getElementById(id);b.hidden=!reviewFlow.previewDigest||reviewFlow.accepted;b.disabled=state.busy;
    }
    document.getElementById("arch-versions-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-handover-button").disabled = !envelope.lastPublish || state.busy;
    document.getElementById("arch-handover-button").textContent=envelope.lastPublish&&!identity.mapSourceRevision?'导出上次确认版本的交接包':'导出同版交接包';
    const localTaskButton = document.getElementById('arch-fixtask-button');
    localTaskButton.disabled = !identity.mapSourceRevision || state.busy;
    localTaskButton.hidden = Boolean(window.projectmindSession);
    const fixTasksButton = document.getElementById("arch-fixtasks-button");
    if (fixTasksButton) {
      fixTasksButton.disabled = !hasDraft || state.busy;
      fixTasksButton.hidden = Boolean(window.projectmindSession);
    }
    document.getElementById("arch-correction-button").disabled = !hasDraft || !state.selectedNodeId || state.busy;
    for (const id of ["arch-deviations-button", "arch-incremental-button"]) {
      const button = document.getElementById(id);
      if (button) button.disabled = !hasDraft || state.busy;
    }
    // candidate generation only needs an open workspace (it creates the first
    // draft); the rejection paths are shown as machine codes when unavailable
    const rulegenButton = document.getElementById("arch-rulegen-button");
    if (rulegenButton) rulegenButton.disabled = !state.envelope || state.busy;
    document.getElementById("arch-diff-button").disabled = !hasDraft || state.busy;
    document.getElementById("arch-gen-count").textContent = hasDraft
      ? `草稿修订 ${short(state.envelope.identity.draftRevision)}`
      : "—";

    renderGraph();
    renderDetails();
    for(const input of details.querySelectorAll('input,select,textarea,button'))input.disabled=state.busy;
    renderCorrectionPreview();
    renderCanvasTab();
    emitWorkspace();
  }

  // ---------- graph rendering ----------

  function autoPositions(nodes) {
    const perRow = 3;
    return nodes.map((node, index) => ({
      x: (index % perRow) * (NODE_W + 24) + 20,
      y: Math.floor(index / perRow) * (NODE_H + 28) + 20,
    }));
  }

  function connectionPath(from,to){
    const dx=to.x-from.x,dy=to.y-from.y;
    if(Math.abs(dy)>Math.abs(dx)*.8){const x1=from.x+NODE_W/2,x2=to.x+NODE_W/2,y1=from.y+(dy>=0?NODE_H:0),y2=to.y+(dy>=0?0:NODE_H);return `M ${x1} ${y1} C ${x1} ${(y1+y2)/2}, ${x2} ${(y1+y2)/2}, ${x2} ${y2}`;}
    const x1=from.x+(dx>=0?NODE_W:0),x2=to.x+(dx>=0?0:NODE_W),y1=from.y+NODE_H/2,y2=to.y+NODE_H/2;return `M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`;
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
    const outline=document.getElementById('arch-outline');outline.replaceChildren();
    if (!current){stage.append(el('div','loading','工作区已就绪。生成候选或载入明确标注的演示样例。'));return;}
    const positions = autoPositions(current.nodes).map((pos,index)=>nodePositions[current.nodes[index].id]||pos);
    const width = Math.max(720, (Math.min(current.nodes.length, 3)) * (NODE_W + 24) + 40);
    const rows = Math.ceil(current.nodes.length / 3);
    const height = Math.max(480, rows * (NODE_H + 28) + 40, ...positions.map(p=>p.y+NODE_H+30));
    stage.style.width=`${Math.max(width,...positions.map(p=>p.x+NODE_W+30))}px`;
    stage.style.height=`${height}px`;
    setZoom(zoom);
    const connections = svg("svg", { class: "connections", viewBox: `0 0 ${parseFloat(stage.style.width)} ${height}`, "aria-label": "功能关系，点击连线编辑" });
    const defs=svg('defs',{});const marker=svg('marker',{id:'arch-arrow',viewBox:'0 -4 8 8',refX:7,refY:0,markerWidth:6,markerHeight:6,orient:'auto'});marker.append(svg('path',{d:'M 0 -3 L 7 0 L 0 3',fill:'none',stroke:'#9cafcc','stroke-width':1}));defs.append(marker);connections.append(defs);
    const byId = new Map(current.nodes.map((node, index) => [node.id, positions[index]]));
    for (const edge of current.edges) {
      const from = byId.get(edge.from);
      const to = byId.get(edge.to);
      if (!from || !to) continue;
      const x1 = from.x + NODE_W / 2, y1 = from.y + NODE_H / 2;
      const x2 = to.x + NODE_W / 2, y2 = to.y + NODE_H / 2;
      const active = state.selectedNodeId && (edge.from === state.selectedNodeId || edge.to === state.selectedNodeId);
      connections.append(svg("path", {
        d: connectionPath(from,to),
        "marker-end":"url(#arch-arrow)",
        class: `connection-line${active ? " active" : ""}`,
        "data-from":edge.from,"data-to":edge.to,
      }));
      const fromTitle=current.nodes.find(n=>n.id===edge.from)?.title||edge.from;
      const toTitle=current.nodes.find(n=>n.id===edge.to)?.title||edge.to;
      const hit=svg('path',{d:connectionPath(from,to),class:'ux-edge-hit',
        'data-from':edge.from,'data-to':edge.to,'data-edge-edit':'true',
        'aria-hidden':'true'});
      const edit=()=>{state.selectedNodeId=edge.from;openNodeEditor('relations',edge);};
      hit.addEventListener('click',edit);
      connections.append(hit);
      // A native button also makes horizontal/vertical lines with a zero-height
      // SVG bounding box reachable by keyboard and easy to point at.
      const control=el('button','ux-edge-control','✎');control.type='button';
      control.dataset.from=edge.from;control.dataset.to=edge.to;control.dataset.edgeEdit='true';
      control.setAttribute('aria-label',`编辑关系：${fromTitle} → ${toTitle} · ${edge.label}`);control.title=edge.label;
      control.style.left=`${(x1+x2)/2-12}px`;control.style.top=`${(y1+y2)/2-12}px`;control.onclick=edit;stage.append(control);
    }
    connections.style.width=stage.style.width;connections.style.height=stage.style.height;
    stage.append(connections);
    current.nodes.forEach((node, index) => {
      const button = el("button", `map-node${node.id === state.selectedNodeId ? " selected" : ""}`);
      button.type = "button";
      button.dataset.nodeId=node.id;button.dataset.status=node.status;button.title=`${node.title}\n${node.summary}`;
      button.style.left = `${positions[index].x}px`;
      button.style.top = `${positions[index].y}px`;
      button.style.width = `${NODE_W}px`;
      button.style.height = `${NODE_H}px`;
      button.setAttribute("aria-pressed", String(node.id === state.selectedNodeId));
      button.append(el("span", "node-number", `${(node.evidence||[]).length} 项证据`));
      button.append(el("strong", "node-title", node.title));
      button.append(el("span", "node-summary", node.summary));
      button.append(el("span", "node-review", nodeBadge(node)));
      button.append(el("span", "node-arrow", "↗"));
      let drag=null,moved=false;
      button.addEventListener('pointerdown',event=>{if(event.button!==0)return;moved=false;drag={x:event.clientX,y:event.clientY,origin:{...positions[index]}};button.setPointerCapture(event.pointerId);});
      button.addEventListener('pointermove',event=>{if(!drag)return;const dx=(event.clientX-drag.x)/zoom,dy=(event.clientY-drag.y)/zoom;if(Math.abs(dx)+Math.abs(dy)>5)moved=true;if(!moved)return;nodePositions[node.id]={x:Math.max(10,drag.origin.x+dx),y:Math.max(10,drag.origin.y+dy)};button.style.left=`${nodePositions[node.id].x}px`;button.style.top=`${nodePositions[node.id].y}px`;
        for(const line of connections.querySelectorAll('path[data-from]')){const a=nodePositions[line.dataset.from]||byId.get(line.dataset.from),b=nodePositions[line.dataset.to]||byId.get(line.dataset.to);if(!a||!b)continue;const x1=a.x+NODE_W/2,y1=a.y+NODE_H/2,x2=b.x+NODE_W/2,y2=b.y+NODE_H/2;line.setAttribute('d',connectionPath(a,b));}
        for(const control of stage.querySelectorAll('.ux-edge-control')){const a=nodePositions[control.dataset.from]||byId.get(control.dataset.from),b=nodePositions[control.dataset.to]||byId.get(control.dataset.to);if(!a||!b)continue;control.style.left=`${(a.x+b.x)/2+NODE_W/2-12}px`;control.style.top=`${(a.y+b.y)/2+NODE_H/2-12}px`;}
      });
      button.addEventListener('pointerup',()=>{drag=null;if(moved){try{localStorage.setItem(positionKey(),JSON.stringify(nodePositions));setStatus('arch-draft-status','查看布局已保存在当前浏览器；没有改变架构关系。');}catch(e){setStatus('arch-draft-status','布局无法保存到当前浏览器。',true);}renderGraph();}});
      button.addEventListener('pointercancel',()=>{drag=null;renderGraph();});
      button.addEventListener('click',()=>{if(moved)return;state.selectedNodeId=node.id;inspectorTab='overview';focusInspector();renderWorkspace();});
      button.addEventListener('dblclick',()=>{state.selectedNodeId=node.id;inspectorTab='edit';renderDetails();});
      const outlineRow=el('button','outline-row');outlineRow.type='button';const copy=el('span');copy.append(el('strong',null,node.title),el('small',null,node.summary));outlineRow.append(copy,el('span','outline-badge',nodeBadge(node)));outlineRow.onclick=()=>{state.selectedNodeId=node.id;inspectorTab='overview';focusInspector();renderWorkspace();};outline.append(outlineRow);
      stage.append(button);
    });
    document.getElementById("arch-node-count").textContent = `${current.nodes.length} 个功能节点 · ${current.edges.length} 条关系`;
  }

  // ---------- details & editing ----------

  function currentDraftRevision() {
    return state.envelope.identity.draftRevision;
  }

  async function applyOps(operations, note, savedGroups = []) {
    if (!requireDraft()) return false;
    const editingNode=state.selectedNodeId;
    state.busy = true;
    renderWorkspace();
    setStatus("arch-draft-status", "正在应用修改…");
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/apply-ops`, {
        expectedDraftRevision: currentDraftRevision(),
        operations,
      });
      state.envelope = result;
      if(editingNode)clearEditorGroups(editingNode, savedGroups);
      clearReview();state.syncedRevision=null;
      setStatus("arch-draft-status", note || "修改已保存到草稿。");
      renderWorkspace();
      return true;
    } catch (error) {
      if (error.code === "REVISION_CONFLICT") {
        setStatus("arch-draft-status", `编辑冲突（${error.code}）：草稿已被其他窗口修改。请重新打开工作区，对比差异后再继续。`, true);
      } else {
        setStatus("arch-draft-status", `应用失败（${error.code}）：${error.message}`, true);
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
    correctionCard.hidden=!current||!state.selectedNodeId;
    if (!current) {
      details.append(el("div", "empty-details", "还没有候选图。"));
      return;
    }
    const node = current.nodes.find((item) => item.id === state.selectedNodeId);
    if (!node) {
      inspector.classList.remove("ux-inspector-open");
      details.append(el("div", "empty-details", "点击图中节点查看与编辑。"));
      return;
    }

    details.append(el("div", "detail-tag", `${nodeBadge(node)} · ${node.id}`));
    const title = el("h3", "detail-title", node.title);
    details.append(title);
    const tabs=el('div','inspector-tabs');
    for(const [id,label] of [['overview','概览'],['evidence','证据'],['relations','关系'],['edit','编辑']]){const b=el('button',inspectorTab===id?'active':'',label);b.type='button';b.onclick=()=>{inspectorTab=id;renderDetails();};tabs.append(b);}details.append(tabs);
    if(inspectorTab!=='edit'){
      const body=el('div','inspector-readonly');
      if(inspectorTab==='overview'){
        body.append(el('h4',null,'职责'),el('p',null,node.summary),el('h4',null,'来源与状态'),el('p',null,`${nodeBadge(node)} · ${projectmindUiLabel(node.provenance)}`),el('h4',null,'入口 / 接口'));
        [...(node.entryPoints||[]),...(node.interfaces||[])].forEach(value=>body.append(el('div','inspector-evidence',value)));
        if(!(node.entryPoints||[]).length&&!(node.interfaces||[]).length)body.append(el('p','inspector-empty','尚未记录入口和接口'));
        body.append(el('h4',null,'期望过程'));
        (node.process||[]).forEach(step=>body.append(el('p',null,`${step.title} · ${step.detail||''}`)));
        if(!(node.process||[]).length)body.append(el('p','inspector-empty','尚未描述过程'));
      }
      if(inspectorTab==='overview'||inspectorTab==='evidence'){
        body.append(el('h4',null,`证据文件 · ${(node.evidence||[]).length}`));
        (node.evidence||[]).forEach(item=>{const evidence=el('div','evidence-card');evidence.append(el('code','evidence-path',item.path),el('p','evidence-reason',item.reason),el('small','evidence-status',projectmindUiLabel(item.kind||'unknown')));
        if(state.envelope.identity.codeRevision){const open=el('button','evidence-button','查看固定版本代码 ↗');open.type='button';open.onclick=async()=>{const workspaceId=state.envelope.workspace.workspaceId,revision=state.envelope.identity.codeRevision;let repoPath=workspacePaths[workspaceId];if(!repoPath){const choice=await workspaceDialog('选择此工作区的代码仓库',[['repoPath','本机仓库绝对路径']], '查看代码');if(!choice)return;repoPath=choice.repoPath;rememberPath(workspaceId,repoPath);}activateView('explorer');document.dispatchEvent(new CustomEvent('projectmind:open-evidence',{detail:{repoPath,revision,path:item.path}}));};evidence.append(open);}body.append(evidence);});
        if(!(node.evidence||[]).length)body.append(el('p','inspector-empty','没有声明证据'));
      }
      if(inspectorTab==='relations'){
        body.append(el('h4',null,'关联模块'));
        const linked=current.edges.filter(e=>e.from===node.id||e.to===node.id);
        linked.forEach(edge=>{const target=current.nodes.find(n=>n.id===(edge.from===node.id?edge.to:edge.from));const b=el('button','outline-row',`${edge.from===node.id?'→':'←'} ${target?.title||'未知'} · ${edge.label||projectmindUiLabel(edge.type)}`);b.onclick=()=>{state.selectedNodeId=target.id;focusInspector();renderWorkspace();};body.append(b);});
        if(!linked.length)body.append(el('p','inspector-empty','尚未记录关系'));
      }
      details.append(body);return;
    }

    // responsibility + title editing
    const titleInput = el("input");
    bindEditor(titleInput, node.id, "basics:title", node.title);
    const summaryInput = el("textarea");
    summaryInput.rows = 3;
    bindEditor(summaryInput, node.id, "basics:summary", node.summary);
    const statusSelect = el("select");
    for (const [value, label] of [["candidate", "候选"], ["confirmed_design", "设计已确认（仍非已实现）"], ["implemented", "已实现"]]) {
      const option = el("option", null, label);
      option.value = value;
      statusSelect.append(option);
    }
    bindEditor(statusSelect, node.id, "basics:status", node.status);
    const saveBasics = el("button", "button primary", "保存职责修改");
    saveBasics.type = "button";
    saveBasics.addEventListener("click", () => {
      const fields = {};
      if (titleInput.value.trim() && titleInput.value !== node.title) fields.title = titleInput.value.trim();
      if (summaryInput.value.trim() && summaryInput.value !== node.summary) fields.summary = summaryInput.value.trim();
      if (statusSelect.value !== node.status) fields.status = statusSelect.value;
      if (!Object.keys(fields).length) { setStatus("arch-draft-status", "职责没有变化。"); return; }
      applyOps([{ type: "update_node", nodeId: node.id, fields }], "职责修改已保存。", ["basics:"]);
    });
    const basics = el("section", "detail-section");
    basics.id='arch-basics-editor';
    basics.append(el("h4", "section-title", "职责与状态"));
    basics.append(labeledField("名称", titleInput), labeledField("职责说明", summaryInput), labeledField("状态", statusSelect), saveBasics);
    details.append(basics);

    // entry points + interfaces
    const entriesInput = el("input");
    bindEditor(entriesInput, node.id, "seams:entry", (node.entryPoints || []).join(", "));
    const interfacesInput = el("input");
    bindEditor(interfacesInput, node.id, "seams:interface", (node.interfaces || []).join(", "));
    const saveSeams = el("button", "button primary", "保存入口/接口");
    saveSeams.type = "button";
    saveSeams.addEventListener("click", () => {
      const split = (value) => value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
      applyOps([{ type: "update_node", nodeId: node.id,
        fields: { entryPoints: split(entriesInput.value), interfaces: split(interfacesInput.value) } }],
        "入口/接口已保存。", ["seams:"]);
    });
    const seams = el("section", "detail-section");
    seams.append(el("h4", "section-title", "公开入口 / 团队接口"));
    seams.append(labeledField("入口（逗号分隔）", entriesInput), labeledField("接口（逗号分隔）", interfacesInput), saveSeams);
    details.append(seams);

    // evidence
    const evidenceSection = el("section", "detail-section");
    evidenceSection.id='arch-evidence-editor';
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
    pathInput.setAttribute("aria-label","新增证据路径");reasonInput.setAttribute("aria-label","新增证据理由");
    bindEditor(pathInput,node.id,"evidence:path","");bindEditor(reasonInput,node.id,"evidence:reason","");
    const addEvidence = el("button", "button ghost", "添加证据");
    addEvidence.type = "button";
    addEvidence.addEventListener("click", () => {
      if (!pathInput.value.trim() || !reasonInput.value.trim()) { setStatus("arch-draft-status", "证据需要路径与理由。", true); return; }
      const next = [...(node.evidence || []), { path: pathInput.value.trim(), reason: reasonInput.value.trim(), kind: "unknown" }];
      applyOps([{ type: "update_node", nodeId: node.id, fields: { evidence: next } }], "证据已添加（默认标记未知，可在确认时说明）。", ["evidence:"]);
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
        const confirmRemove = el("button", "button primary", "仍然删除（级联移除关系与过程引用）");
        confirmRemove.type = "button";
        confirmRemove.addEventListener("click", () => {
          const hasRefs = impact.edges.length > 0 || impact.processReferences.length > 0;
          applyOps([{ type: "remove_node", nodeId: node.id, force: hasRefs }], "节点已删除。", ["*"]);
          state.selectedNodeId = null;
        });
        danger.append(confirmRemove);
      } catch (error) {
        setStatus("arch-draft-status", `影响读取失败（${error.code}）：${error.message}`, true);
      }
    });
    danger.append(previewImpact);
    details.append(danger);
  }

  function renderProcessEditor(node) {
    const section = el("section", "detail-section");
    section.id='arch-process-editor';
    const baseline = structuredClone(node.process || []);
    const steps = buffered(node.id, "process", baseline).map((step) => ({ ...step, inputs: [...(step.inputs || [])], outputs: [...(step.outputs || [])], branches: [...(step.branches || [])], next: [...(step.next || [])] }));
    const rows = [];
    // edits commit on every keystroke as well as on blur: relying on `change`
    // alone loses text when the field never loses focus before the save button
    // is used (observed in a real browser session)
    const onEdit = (element, handler) => {
      const record=()=>{handler();bufferValue(node.id,"process",steps,baseline);};
      element.addEventListener("input", record);
      element.addEventListener("change", record);
    };
    const rebuild = (changed=false) => {
      if(changed)bufferValue(node.id,"process",steps,baseline);
      section.replaceChildren(el("h4", "section-title", `期望执行步骤 · ${steps.length} 步`),el('p','ux-relation-help','先写步骤名称和这一步要发生什么。按实际顺序排列，点“保存过程”后才能用于开发任务。输入、输出和分支可稍后补充。'));
      steps.forEach((step, index) => {
        const row = el("div", "arch-step-row");
        const idTag = el("code", "arch-step-id", step.stepId);
        const titleInput = el("input");
        titleInput.value = step.title;
        titleInput.placeholder='步骤名称，例如保存订单';titleInput.setAttribute('aria-label',`第 ${index+1} 步名称`);
        onEdit(titleInput, () => { step.title = titleInput.value; });
        const detailInput = el("input");
        detailInput.value = step.detail || "";
        detailInput.placeholder = "这一步发生什么";
        detailInput.setAttribute('aria-label',`第 ${index+1} 步说明`);
        onEdit(detailInput, () => { step.detail = detailInput.value; });
        const lists = el("input");
        lists.value = [step.inputs, step.outputs, step.branches].map((list) => list.join("/")).join(" | ");
        lists.placeholder = "输入/输出/分支，用 | 分隔";
        lists.setAttribute('aria-label',`第 ${index+1} 步输入输出分支`);
        onEdit(lists, () => {
          const [inputs, outputs, branches] = lists.value.split("|").map((part) => part.split("/").map((item) => item.trim()).filter(Boolean));
          step.inputs = inputs || []; step.outputs = outputs || []; step.branches = branches || [];
        });
        const up = el("button", "button ghost", "↑");
        up.type = "button";
        up.addEventListener("click", () => { if (index > 0) { [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]]; rebuild(true); } });
        const down = el("button", "button ghost", "↓");
        down.type = "button";
        down.addEventListener("click", () => { if (index < steps.length - 1) { [steps[index + 1], steps[index]] = [steps[index], steps[index + 1]]; rebuild(true); } });
        const remove = el("button", "button ghost", "删");
        remove.type = "button";
        remove.addEventListener("click", () => { steps.splice(index, 1); rebuild(true); });
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
        rebuild(true);
      });
      const save = el("button", "button primary", "保存过程");
      save.type = "button";
      save.addEventListener("click", () => {
        if(steps.some(step=>!step.title.trim()||!step.detail.trim())){setStatus("arch-draft-status","请填写每一步的名称和说明，再保存期望过程。",true);return;}
        for (const step of steps) step.next = step.next.filter((entry) => steps.some((other) => other.stepId === entry));
        applyOps([{ type: "update_process", nodeId: node.id, process: steps }], "期望步骤已保存；请重新确认设计与过程后再创建任务。", ["process"]);
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
    section.id='arch-relation-editor';
    section.append(el("h4", "section-title", `关系 · ${current.edges.filter((edge) => edge.from === node.id || edge.to === node.id).length}`));
    section.append(el('p','ux-relation-help','修改现有关系可展开“修改这条关系”；选择目标、类型和说明可添加新关系。方向由起点 → 终点表示。保存会更新草稿，不会自动发布。'));
    for (const edge of current.edges) {
      if (edge.from !== node.id && edge.to !== node.id) continue;
      const other = current.nodes.find((item) => item.id === (edge.from === node.id ? edge.to : edge.from));
      const row = el("div", "relation-row");
      row.append(el("span", "relation-symbol", edge.from === node.id ? "→" : "←"),
        el("span", "relation-name", other ? other.title : edge.to),
        el("small", "relation-label", `${projectmindUiLabel(edge.type)} · ${edge.label}`));
      const remove = el("button", "evidence-button", "删除");
      remove.type = "button";
      remove.addEventListener("click", () => {
        applyOps([{ type: "remove_edge", match: { from: edge.from, to: edge.to, type: edge.type } }], "关系已删除。");
      });
      row.append(remove);
      const edit=el('details','ux-relation-edit');edit.dataset.from=edge.from;edit.dataset.to=edge.to;edit.dataset.type=edge.type;edit.append(el('summary',null,'修改这条关系'));
      const fromSelect=el('select'),toSelect=el('select'),kindSelect=el('select'),text=el('input');
      for(const option of current.nodes){for(const select of [fromSelect,toSelect]){const item=el('option',null,option.title);item.value=option.id;select.append(item);}}
      fromSelect.value=edge.from;toSelect.value=edge.to;
      for(const [value,label] of [['static_reference','静态引用'],['functional_collaboration','功能协作'],['expected_sequence','期望先后']]){const item=el('option',null,label);item.value=value;kindSelect.append(item);}
      const editGroup=`relation:${edge.from}/${edge.to}/${edge.type}:`;
      bindEditor(fromSelect,node.id,editGroup+'from',edge.from);bindEditor(toSelect,node.id,editGroup+'to',edge.to);
      bindEditor(kindSelect,node.id,editGroup+'type',edge.type);bindEditor(text,node.id,editGroup+'label',edge.label);
      fromSelect.setAttribute('aria-label','关系起点');toSelect.setAttribute('aria-label','关系终点');kindSelect.setAttribute('aria-label','修改关系类型');text.setAttribute('aria-label','修改关系说明');
      const save=el('button','button primary','保存这条关系');save.type='button';
      save.onclick=()=>{
        if(!fromSelect.value||!toSelect.value||fromSelect.value===toSelect.value||!text.value.trim()){setStatus('arch-draft-status','关系需要不同的起点与终点，以及说明。',true);return;}
        // Existing CAS operation batch performs the replacement atomically.
        applyOps([{type:'remove_edge',match:{from:edge.from,to:edge.to,type:edge.type}},
          {type:'add_edge',edge:{from:fromSelect.value,to:toSelect.value,type:kindSelect.value,label:text.value.trim()}}],'关系修改已保存到草稿。',[editGroup]);
      };
      edit.append(labeledField('起点',fromSelect),labeledField('终点',toSelect),labeledField('类型',kindSelect),labeledField('关系说明',text),save);row.append(edit);
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
    bindEditor(targets,node.id,"newrelation:target",targets.value);bindEditor(typeSelect,node.id,"newrelation:type",typeSelect.value);bindEditor(labelInput,node.id,"newrelation:label","");
    const addEdge = el("button", "button ghost", "添加关系到所选目标");
    addEdge.type = "button";
    addEdge.addEventListener("click", () => {
      if (!targets.value || !labelInput.value.trim()) { setStatus("arch-draft-status", "请选择目标节点并填写关系说明。", true); return; }
      applyOps([{ type: "add_edge", edge: { from: node.id, to: targets.value, type: typeSelect.value, label: labelInput.value.trim() } }], "关系已添加。", ["newrelation:"]);
    });
    const addReverse = el("button", "button ghost", "从目标添加到本节点");
    addReverse.type = "button";
    addReverse.addEventListener("click", () => {
      if (!targets.value || !labelInput.value.trim()) { setStatus("arch-draft-status", "请选择来源节点并填写关系说明。", true); return; }
      applyOps([{ type: "add_edge", edge: { from: targets.value, to: node.id, type: typeSelect.value, label: labelInput.value.trim() } }], "关系已添加。", ["newrelation:"]);
    });
    section.append(labeledField("目标节点", targets), labeledField("关系类型", typeSelect), labeledField("说明", labelInput), addEdge, addReverse);
    details.append(section);

    const addNode = el("section", "detail-section");
    addNode.append(el("h4", "section-title", "新增功能节点"));
    const newNodeTitle = el("input");
    newNodeTitle.placeholder = "新节点名称";
    const newNodeSummary = el("input");
    newNodeSummary.placeholder = "职责说明";
    bindEditor(newNodeTitle,node.id,"newnode:title","");bindEditor(newNodeSummary,node.id,"newnode:summary","");
    const createNode = el("button", "button primary", "添加节点");
    createNode.type = "button";
    createNode.addEventListener("click", () => {
      if (!newNodeTitle.value.trim()) { setStatus("arch-draft-status", "请填写节点名称。", true); return; }
      const nodeId = `n_${Date.now().toString(36)}`;
      applyOps([{ type: "add_node", node: { id: nodeId, title: newNodeTitle.value.trim(), summary: newNodeSummary.value.trim() || "（待补充职责）", status: "candidate", provenance: "human_input", entryPoints: [], interfaces: [], evidence: [], process: [] } }], "节点已添加。", ["newnode:"]);
    });
    addNode.append(labeledField("名称", newNodeTitle), labeledField("职责", newNodeSummary), createNode);
    details.append(addNode);
  }

  // ---------- generation ----------

  document.getElementById("arch-generate-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy || !requireSavedEditors()) return;
    state.busy = true;
    renderWorkspace();
    const wait = state.envelope.generation?.requestTimeoutSeconds;
    const waitHint = Number.isFinite(wait) && wait > 0 ? `（最长约 ${Math.ceil(wait / 60)} 分钟）` : "（请等待完整结果）";
    setGenStatus(`正在调用已配置模型生成候选图…${waitHint}。请勿重复提交。`);
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/generate`, {});
      if (result.status === "ai_generated") {
        state.pendingCandidate = result;
        showCandidateForApply(result, "AI 候选图已生成。请检查后点击「应用到草稿」。");
      } else {
        setGenStatus(`${projectmindUiLabel(result.status)}：${result.note}`, true);
      }
    } catch (error) {
      setGenStatus(`生成失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  document.getElementById("arch-sample-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy || !requireSavedEditors()) return;
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
        setGenStatus(`${projectmindUiLabel(result.status)}：${result.note}`, true);
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
    const area = document.getElementById("arch-candidate-preview");
    area.replaceChildren();area.hidden=false;
    area.append(el('h3',null,'候选预览 · 尚未应用'));
    const graph=result.graph||{nodes:[],edges:[]};
    area.append(el('p',null,`${graph.nodes.length} 个功能节点 · ${graph.edges.length} 条关系 · ${result.origin==='rule_based'?'规则起草，待人工核对':result.status==='dev_sample'?'演示数据，不能用于真实项目确认':'AI 候选，待人工核对'}`));
    const list=el('ul');
    for(const node of graph.nodes)list.append(el('li',null,`${node.title}：${node.summary}`));
    area.append(list);
    for(const edge of graph.edges)area.append(el('p','ux-relation-help',`${graph.nodes.find(n=>n.id===edge.from)?.title||edge.from} → ${graph.nodes.find(n=>n.id===edge.to)?.title||edge.to}：${edge.label}`));
    for(const note of [...(result.warnings||[]),...(result.unknowns||[]),...(result.openQuestions||[])])area.append(el('p','ux-relation-help',typeof note==='string'?note:JSON.stringify(note)));
    const apply = el("button", "button primary", "应用到草稿");
    apply.type = "button";
    apply.addEventListener("click", async () => {
      if(state.busy || !requireSavedEditors())return;
      if(state.envelope.draft && !window.confirm("采用这个候选会替换当前草稿中的节点、关系和过程。已发布的版本保留。确定采用吗？"))return;
      state.busy=true;renderWorkspace();
      try {
        // apply by candidateId: the server-stored candidate (with its real
        // origin) is the only thing that can become a draft
        const envelope = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/apply-candidate`,
          { candidateId: result.candidateId, expectedDraftRevision: state.envelope.identity.draftRevision });
        state.pendingCandidate = null;
        openEnvelope(envelope);
        setGenStatus(result.status === "dev_sample"
          ? "演示候选已作为草稿（标注保留）。"
          : result.origin==='rule_based' ? '规则候选已应用为草稿（来源标记保留，仍需人工核对）。'
          : "AI 候选已应用为草稿（全部节点仍为候选状态）。");
      } catch (error) {
        setGenStatus(`应用失败（${error.code}）：${error.message}`, true);
      } finally { state.busy=false;renderWorkspace(); }
    });
    const discard = el("button", "button ghost", "放弃该候选");
    discard.type = "button";
    discard.addEventListener("click", () => { state.pendingCandidate = null; area.replaceChildren();area.hidden=true; setGenStatus("候选已放弃。");emitWorkspace(); });
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
      // production path only: the real model when configured, otherwise C's
      // rule engine (labeled rule_based). The dev-sample path is reachable
      // solely through the explicitly labeled sample button (FINAL-UI-01).
      const modeSelect = document.getElementById("arch-correction-mode");
      const mode = modeSelect ? modeSelect.value : "production";
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/correction-preview`, {
        expectedDraftRevision: currentDraftRevision(),
        instruction,
        selectedNodeIds: [state.selectedNodeId],
        mode,
      });
      state.correctionPreview = result;
      renderCorrectionPreview();
      setStatus("arch-correction-status", result.origin === "rule_based"
        ? `规则纠正预览（规则引擎；${result.note || "确认后应用到草稿"}）`
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
      setStatus("arch-correction-status", "纠正预览已过期（草稿在此期间发生了变化）；请重新生成预览。", true);
      area.append(el("div", "review-notice", "纠正预览已过期（草稿在此期间发生了变化）；请重新生成预览。"));
      return;
    }
    const label = el("div", "ai-candidate-label", preview.origin === "dev_sample"
      ? "演示纠正预览 · 非真实 AI 输出" : "纠正预览");
    area.append(label);
    const changed = preview.diff || {};
    for (const node of changed.nodes || []) {
      area.append(el("p", "ai-item", `节点 ${node.id}（${node.title || ""}）：${projectmindUiLabel(node.change)}${node.fields ? ` · ${node.fields.map(projectmindUiLabel).join("、")}` : ""}`));
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

// ---------- rule-based candidate / deviations / incremental (C engine) ----------

  document.getElementById("arch-rulegen-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy || !requireSavedEditors()) return;
    state.busy = true; renderWorkspace();
    setGenStatus("正在根据项目资料起草规则候选…");
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/generate`, { mode: "rule_based" });
      state.pendingCandidate = result;
      const coverage = result.contextCoverage;
      const coverageText = coverage
        ? `覆盖：读取 ${coverage.filesIncluded} 个文件 / 共 ${coverage.pythonFiles} 个 Python 文件`
        : "规划模式：没有代码事实，依据是目标与约束";
      showCandidateForApply(result, `规则候选已起草（${coverageText}；职责与关系待人工核对）`);
    } catch (error) {
      setGenStatus(`规则候选生成失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false; renderWorkspace();
    }
  });

  document.getElementById("arch-deviations-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/deviations`, { observedTraces: [] });
      const area = document.getElementById("arch-diff-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", result.labeled));
      area.append(el("p", "ai-item", `结论：${projectmindUiLabel(result.verdict)}（${result.deviations.length} 项）`));
      area.append(el("p", "ai-provenance", result.reason || ""));
    } catch (error) {
      setStatus("arch-review-status", `偏差检查失败（${error.code}）：${error.message}`, true);
    }
  });

  document.getElementById("arch-incremental-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/incremental`, {});
      const area = document.getElementById("arch-diff-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", result.labeled || "代码变化候选"));
      if (result.status === "no_change") {
        area.append(el("p", "ai-provenance", "代码未变化。"));
      } else {
        area.append(el("p", "ai-item",
          `变化：新增 ${result.changeSummary.added} · 修改 ${result.changeSummary.modified} · 删除 ${result.changeSummary.deleted}`));
        area.append(el("p", "ai-provenance", `候选操作 ${result.operations.length} 条（仅候选，不自动写入草稿）`));
      }
    } catch (error) {
      setStatus("arch-review-status", `增量候选失败（${error.code}）：${error.message}`, true);
    }
  });

// ---------- fix task lifecycle (D authoritative store, reachable from the UI) ----------

  async function refreshFixTasks() {
    if (!state.envelope) return;
    const listing = await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/fix-tasks`);
    const area = document.getElementById("arch-task-result");
    area.replaceChildren();
    area.append(el("div", "ai-candidate-label", "当前项目的实施任务"));
    if (listing.backend?.kind === 'd_governed_tasks') {
      area.append(el('p', 'ai-item', '在下方的修正任务面板中创建、接手和回挂任务。'));
      return;
    }
    const tasks = listing.tasks || [];
    if (!tasks.length) {
      area.append(el("p", "ai-item", "该工作区还没有修正任务；先在图上选中节点并创建。"));
      return;
    }
    for (const task of tasks) {
      const row = el("div", "compare-card");
      const taskId = task.id || task.taskId;
      row.append(el("p", "ai-item", `任务 ${taskId} · 状态 ${projectmindUiLabel(task.status)} · 范围 ${(task.scope || []).join("、") || "—"}`));
      row.append(el("p", "ai-provenance", task.deviation || task.observation || ""));
      if (task.submittedRevision) row.append(el("p", "ai-provenance", `回挂提交 ${short(task.submittedRevision)}`));
      if (task.verification) {
        row.append(el("p", "ai-provenance",
          `核查：退出码 ${task.verification.exitCode} · 摘要 ${String(task.verification.outputDigest || "").slice(0, 20)}… 由 ${task.verification.actor} 确认`));
      }
      const actions = el("div", "compare-controls");
      const addAction = (label, handler) => {
        const button = el("button", "button ghost", label);
        button.type = "button";
        button.addEventListener("click", handler);
        actions.append(button);
      };
      const act = async (body, note) => {
        // D's authoritative store needs a declared local operator in the
        // server-side write session; declare one before any state change
        // (same declaration pattern as the review and create flows).
        let operator = window.projectmindSession?.actor || writeSession.operator;
        if (!operator) {
          const declared = await workspaceDialog("声明本机操作者",
            [["actor", "本机操作者（声明，绑定本机会话）"]], "继续");
          if (!declared) return;
          operator = declared.actor;
        }
        await ensureSession(operator);
        state.busy = true; renderWorkspace();
        try {
          // state changes carry the revision and map revision this page saw;
          // the server (and D's transaction) validate them instead of
          // adopting whatever is current (FINAL-D-03)
          const payload = { expectedRevision: task.revision, expectedMapRevision: task.mapRevision, ...body };
          const updated = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/fix-tasks/${taskId}`, payload);
          setStatus("arch-review-status", `${note}（当前状态：${projectmindUiLabel(updated.status)}）`);
          await refreshFixTasks();
        } catch (error) {
          setStatus("arch-review-status", `操作失败（${error.code}）：${error.message}`, true);
        } finally {
          state.busy = false; renderWorkspace();
        }
      };
      if (task.status === "queued") {
        addAction("接手任务", () => act({ status: "received", note: "本机操作者接手该任务" }, "已接手"));
      } else if (task.status === "received") {
        addAction("开始实施", () => act({ status: "in_progress", note: "在独立分支按范围实施" }, "已开始实施"));
      } else if (task.status === "in_progress") {
        addAction("回挂提交", async () => {
          const submit = await workspaceDialog("回挂实施提交",
            [["commitSha", "实施提交（完整 SHA）"], ["summary", "提交说明（做了什么、验证依据）", "textarea"]],
            "回挂");
          if (!submit) return;
          await act({ status: "submitted", commitSha: submit.commitSha, summary: submit.summary }, "提交已回挂，等待实测核验");
        });
      } else if (task.status === "verification_pending") {
        addAction("实测并核验（关闭偏差）", async () => {
          const confirm = await workspaceDialog("实测核验确认",
            [["reason", "确认理由（本轮实测结论）", "textarea"]], "确认关闭");
          if (!confirm) return;
          await act({ status: "verified", reason: confirm.reason }, "实测通过并已人确认，偏差关闭");
        });
      } else if (task.status === "verified") {
        row.append(el("p", "ai-provenance", "该偏差已按实测结论关闭；改图或新提交不会自动重开。"));
      }
      if (actions.children.length) row.append(actions);
      area.append(row);
    }
  }

  document.getElementById("arch-fixtasks-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      await refreshFixTasks();
      setStatus("arch-review-status", "已读取当前项目的任务。按状态接手、实施、回挂提交，最后实测并人工确认。");
    } catch (error) {
      setStatus("arch-review-status", `读取任务失败（${error.code}）：${error.message}`, true);
    }
  });

// ---------- review / publish (real B version service, three steps) ----------

  const reviewFlow = { actor: null, previewDigest: null, accepted:false };
  function clearReview() {
    reviewFlow.actor=null;reviewFlow.previewDigest=null;reviewFlow.accepted=false;
    for(const id of ['arch-review-confirm-button','arch-review-reject-button','arch-publish-button']){
      const b=document.getElementById(id);b.hidden=true;b.disabled=true;
    }
  }

  document.getElementById("arch-sync-button").addEventListener("click", async () => {
    if (!state.envelope || !graph() || state.busy || !requireSavedEditors()) return;
    state.busy = true; renderWorkspace();
    setStatus("arch-review-status", "正在把草稿写入真实版本服务…");
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/sync`, {});
      const area = document.getElementById("arch-review-result");
      area.replaceChildren();
      area.append(el("p", "ai-item", "草稿已保存到真实版本服务（尚未人审，未产生版本）"));
      area.append(el("p", "ai-provenance", `服务端草稿修订：${result.bDraftRevision} · 本次操作 ${(result.operations || []).length} 条`));
      setStatus("arch-review-status", "已保存。下一步：人审预览。");
      state.syncedRevision=state.envelope.identity.draftRevision;
      openEnvelope(await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}`));
    } catch (error) {
      setStatus("arch-review-status", `保存失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false; renderWorkspace();
    }
  });

  document.getElementById("arch-review-preview-button").addEventListener("click", async () => {
    if (!state.envelope || !graph() || state.busy || !requireSavedEditors()) return;
    const review = await workspaceDialog("人审预览",
      [["actor", "本机操作者（声明，绑定本机会话）"], ["reason", "审阅理由（随预览与版本记录）", "textarea"]],
      "生成预览");
    if (!review) return;
    const actor = window.projectmindSession?.actor || review.actor;
    const { reason } = review;
    clearReview();
    state.busy = true; renderWorkspace();
    setStatus("arch-review-status", "正在生成人审预览…");
    try {
      // the declared operator is bound to the server-side write session, so
      // fix tasks created later are attributed to the same declaration
      await ensureSession(actor);
      const verifyCode = state.envelope.workspace.context !== "planning"
        && (document.getElementById('arch-review-mode')?.value || 'code') !== 'design';
      const preview = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/review-preview`,
        { actor, reason, verifyCode });
      reviewFlow.actor = actor;
      reviewFlow.previewDigest = preview.previewDigest;
      reviewFlow.accepted=false;
      const area = document.getElementById("arch-review-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", preview.labeled || "人审预览"));
      const coverage = preview.reviewCoverage;
      area.append(el("p", "ai-item",
        `覆盖范围：节点 ${coverage.nodes.length} · 关系 ${coverage.edges.length} · 过程 ${coverage.processes.length} · 依据/证据 ${coverage.evidence.length}（${coverage.scope}）`));
      area.append(el("p", "ai-item", preview.verifyCode
        ? "本次核查代码证据；期望过程不在确认范围内。若要创建实施任务，请改为确认设计与期望过程。"
        : "本次确认设计与期望过程；不代表代码已按设计实现或通过实测。"));
      const contents=el('details','ux-review-contents');contents.open=true;
      contents.append(el('summary',null,'查看本次待确认内容'));
      const after=preview.afterGraph;
      for(const node of after?.nodes||[]){
        const card=el('article','ux-review-node');card.append(el('h4',null,node.title),el('p',null,node.summary));
        for(const step of node.process||[])card.append(el('p',null,`${preview.verifyCode?'未确认的期望步骤':'期望步骤'}：${step.title} · ${step.detail||'未填写说明'}`));
        for(const item of node.evidence||[])card.append(el('p','ux-review-evidence',`依据：${item.path} · ${item.reason||''}`));
        contents.append(card);
      }
      for(const edge of after?.edges||[])contents.append(el('p',null,`${after.nodes.find(n=>n.id===edge.from)?.title||edge.from} → ${after.nodes.find(n=>n.id===edge.to)?.title||edge.to}：${edge.label}`));
      area.append(contents,el('p','ai-provenance',`此预览约 ${Math.ceil(preview.expiresInSeconds/60)} 分钟后失效。改动草稿后需重新预览。`));
      for (const limit of preview.limits || []) area.append(el("p", "ai-provenance", limit));
      area.append(el("p", "ai-provenance", `预览摘要：${preview.previewDigest}`));
      const confirmButton = document.getElementById("arch-review-confirm-button");
      const rejectButton = document.getElementById("arch-review-reject-button");
      confirmButton.hidden = false; confirmButton.disabled = false;
      rejectButton.hidden = false; rejectButton.disabled = false;
      setStatus("arch-review-status", "预览已生成。请核对范围后确认或拒绝。");
    } catch (error) {
      setStatus("arch-review-status", `预览失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false; renderWorkspace();
    }
  });

  async function confirmReview(decision) {
    if (!state.envelope || !reviewFlow.previewDigest || state.busy || !requireSavedEditors()) return;
    state.busy = true; renderWorkspace();
    try {
      const result = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/review-confirm`,
        { previewDigest: reviewFlow.previewDigest, decision });
      const area = document.getElementById("arch-review-result");
      if (decision === "accept") {
        reviewFlow.accepted=true;
        const publishButton = document.getElementById("arch-publish-button");
        publishButton.hidden = false; publishButton.disabled = false;
        area.append(el("p", "ai-item", "已确认：发布授权保存在服务端；点击发布产生不可变版本"));
        setStatus("arch-review-status", "已确认。发布授权保存在服务端，点击“发布不可变版本”产生版本。");
      } else {
        clearReview();
        area.append(el("p", "ai-item", "已拒绝：没有产生版本。"));
        setStatus("arch-review-status", "已拒绝，未产生版本。返回工作台修改，再重新预览。");
        document.dispatchEvent(new CustomEvent("projectmind:review-rejected"));
      }
      return result;
    } catch (error) {
      if(['REVIEW_EXPIRED','REVISION_CONFLICT','HUMAN_REVIEW_REQUIRED','REQUEST_FORBIDDEN'].includes(error.code))clearReview();
      setStatus("arch-review-status", `确认未完成：${error.message}。请重新预览当前内容。`, true);
    } finally {
      state.busy = false; renderWorkspace();
    }
  }

  document.getElementById("arch-review-confirm-button").addEventListener("click", () => confirmReview("accept"));
  document.getElementById("arch-review-reject-button").addEventListener("click", () => confirmReview("reject"));

  document.getElementById("arch-publish-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy || !requireSavedEditors()) return;
    state.busy = true; renderWorkspace();
    try {
      const published = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/publish`, {});
      const area = document.getElementById("arch-version-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", published.labeled || "B 版本服务产生并经 Git 提交的不可变认知版本"));
      area.append(el("p", "ai-item", `图版本 ${published.version.mapRevision}`));
      area.append(el("p", "ai-item", `代码提交 ${published.version.codeRevision || "无（规划/设计确认）"}（核查覆盖 ${published.version.verifiedCodeRevision ? short(published.version.verifiedCodeRevision) : "无"}）`));
      area.append(el("p", "ai-provenance", `架构 Git 来源提交 ${published.provenance.mapSourceRevision || "—"} · 图性质：${projectmindUiLabel(published.version.status)} · 覆盖范围 ${published.reviewCoverage ? projectmindUiLabel(published.reviewCoverage.scope) : "—"}`));
      const publishButton = document.getElementById("arch-publish-button");
      publishButton.hidden = true; publishButton.disabled = true;
      setStatus("arch-review-status", "版本已发布（不可变）。");
      openEnvelope(await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}`));
    } catch (error) {
      if(['REVIEW_EXPIRED','REVISION_CONFLICT','HUMAN_REVIEW_REQUIRED','REQUEST_FORBIDDEN'].includes(error.code))clearReview();
      setStatus("arch-review-status", `发布未完成：${error.message}。请核对状态后重新预览。`, true);
    } finally {
      state.busy = false; renderWorkspace();
    }
  });

  document.getElementById("arch-versions-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      const listing = await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/versions`);
      const area = document.getElementById("arch-version-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", "不可变版本历史（B 版本服务）"));
      for (const version of listing.versions || []) {
        area.append(el("p", "ai-item",
          `${version.mapRevision} · ${projectmindUiLabel(version.status)} · 代码 ${short(version.codeRevision)} · 发布 ${version.publishedAt || "—"}`));
      }
      if (!(listing.versions || []).length) area.append(el("p", "ai-item", "还没有已发布版本。"));
    } catch (error) {
      setStatus("arch-review-status", `读取版本历史失败（${error.code}）：${error.message}`, true);
    }
  });

  document.getElementById("arch-handover-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      const packageData = await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/handover`);
      const version = packageData.versionEnvelope?.version || packageData;
      const provenance = packageData.versionEnvelope?.provenance || packageData;
      const link = document.createElement("a");
      const downloadQuery=new URLSearchParams({download:'1',mapRevision:version.mapRevision,mapSourceRevision:provenance.mapSourceRevision});
      link.href=`/api/archloop/workspaces/${encodeURIComponent(state.envelope.workspace.workspaceId)}/handover?${downloadQuery}`;
      link.download = `handover-${version.mapId}-${String(version.mapRevision).slice(7, 19)}.json`;
      link.textContent='下载同版交接包 JSON';link.className='button primary';
      const area = document.getElementById("arch-version-result");
      area.replaceChildren();
      const readingOnly = packageData.sources && packageData.sources.architecture === null;
      area.append(el("div", "ai-candidate-label", readingOnly ? "同版交接包（已发布版本内容）" : "同版交接包（可交给下一位副本）"));
      area.append(el("p", "ai-item", `图标识 ${version.mapId} · 图版本 ${version.mapRevision}`));
      area.append(el("p", "ai-item", `架构来源 ${provenance.mapSourceRevision} · 未解决偏差 ${(packageData.unresolvedDeviations || []).length} · 未关闭任务 ${(packageData.openFixTasks || []).length}`));
      area.append(el("p", "ai-provenance", packageData.importHint ? packageData.importHint.note : ""));
      if (readingOnly) area.append(el("p", "ai-provenance", "可下载用于阅读交接；跨电脑来源核验尚未完成。"));
      area.append(link);
      setStatus("arch-review-status", `同版交接包已生成，请点击下载保存：图标识 ${version.mapId} · 图版本 ${version.mapRevision} · 架构来源 ${provenance.mapSourceRevision}`);
    } catch (error) {
      setStatus("arch-review-status", `导出失败（${error.code}）：${error.message}`, true);
    }
  });

  // ---------- fix task ----------

  document.getElementById("arch-fixtask-button").addEventListener("click", async () => {
    if (!state.envelope || !graph() || state.busy || !requireSavedEditors()) return;
    if(!state.envelope.identity.mapSourceRevision){setStatus("arch-review-status","当前草稿尚未发布。请先确认设计与期望过程并发布这一版，再创建任务。",true);return;}
    const current = graph();
    const node = state.selectedNodeId
      ? (current.nodes || []).find((item) => item.id === state.selectedNodeId) : null;
    if (!node) {
      setStatus("arch-review-status", "请先在图上选中要修正的功能节点（任务需要固定的期望过程与证据）。", true);
      return;
    }
    const steps = node.process || node.steps || [];
    if (!steps.length) {
      setStatus("arch-review-status", "该节点还没有期望过程步骤，无法固定修正范围。", true);
      return;
    }
    const evidenceItems = (node.evidence || []).filter((item) => item.path && item.kind !== "requirement");
    if (!evidenceItems.length) {
      setStatus("arch-review-status", "该节点没有代码证据路径，无法创建可核查的修正任务。", true);
      return;
    }
    const taskContext=JSON.stringify([state.envelope.workspace.workspaceId,state.envelope.identity.mapRevision,state.envelope.identity.draftRevision]);
    try {
      const version=await api('GET',`/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/versions/${encodeURIComponent(state.envelope.identity.mapRevision)}`);
      if(taskContext!==JSON.stringify([state.envelope?.workspace.workspaceId,state.envelope?.identity.mapRevision,state.envelope?.identity.draftRevision]))return;
      if(!version.reviewCoverage?.processes?.includes(`process-${node.id}`)){
        const area=document.getElementById('arch-task-result');area.replaceChildren(el('p','ai-item','这些期望步骤还没有经过设计确认。代码证据核查不能代替确认期望过程。'));
        const next=el('button','button primary','确认这些期望步骤');next.type='button';
        next.onclick=()=>{document.dispatchEvent(new CustomEvent('projectmind:prepare-task-review'));document.getElementById('arch-review-preview-button').click();};
        area.append(next);area.scrollIntoView({block:'center'});return;
      }
    } catch(error){setStatus('arch-review-status',`无法核对任务所需版本：${error.message}`,true);return;}
    const paths=[...new Set(evidenceItems.map(item=>item.path))];
    const review = await workspaceDialog(`创建任务 · ${node.title}`,
      [["operator", "本机操作者（声明，绑定本机会话）"],
       ["processRef", "本次要修改的期望步骤", [{value:"",label:"请选择实际涉及的步骤"},...steps.map(step=>({value:`${node.id}/${step.stepId||step.id}`,label:step.title}))]],
       ["evidencePaths", "允许改动的代码证据（可多选）", {multiple:true,options:paths.map(path=>({value:path,label:path,selected:true}))}],
       ["deviation", "实际行为与期望的差异、复现方法", "textarea"], ["acceptance", "验收标准", "textarea"]],
      "创建实施任务");
    if (!review) return;
    const operator = window.projectmindSession?.actor || review.operator;
    const { deviation, acceptance, processRef, evidencePaths } = review;
    state.busy = true;
    renderWorkspace();
    try {
      await ensureSession(operator);
      const task = await api("POST", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/fix-tasks`, {
        deviation,
        acceptance,
        expectedProcessRef: processRef,
        evidence: evidencePaths.map(path=>({path,reason:evidenceItems.find(item=>item.path===path)?.reason||"选中节点的代码证据"})),
        scope: evidencePaths,
      });
      const area = document.getElementById("arch-task-result");
      area.replaceChildren();
      area.append(el("div", "ai-candidate-label", "实施任务已创建"));
      const taskId = task.id || task.taskId;
      area.append(el("p", "ai-item", `任务 ${taskId} · 状态 ${projectmindUiLabel(task.status)} · 目标提交 ${short(task.codeRevision || task.targetCodeRevision)}`));
      area.append(el("p", "ai-item", task.deviation || task.observation));
      area.append(el("p", "ai-provenance", `验收条件：${task.acceptance}`));
      setStatus("arch-review-status", "任务已保存。下一步：查看任务进度，接手并实施；回挂提交后仍需实测和人工确认关闭。");
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
          const review=await workspaceDialog('复核后回挂',[['actor','复核人（本机操作者声明）']], '确认回挂');
          if(!review)return;
          const actor=window.projectmindSession?.actor||review.actor;
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
      setGenStatus(`复核失败（${error.code}）：${error.message}`, true);
    } finally {
      state.busy = false;
      renderWorkspace();
    }
  });

  document.getElementById("arch-diff-button").addEventListener("click", async () => {
    if (!state.envelope || state.busy) return;
    try {
      const diff = await api("GET", `/api/archloop/workspaces/${state.envelope.workspace.workspaceId}/diff`);
      const area = document.getElementById("arch-diff-result");
      area.replaceChildren();
      area.append(el("h3", "section-title", "候选前后对照（基准候选 → 当前草稿）"));
      const changedNodes = diff.nodes || [];
      if (!changedNodes.length && !(diff.edges?.added || []).length && !(diff.edges?.removed || []).length) {
        area.append(el("p", "ai-item", "与基准候选没有语义差异（仅布局或无变化）。"));
      }
      for (const node of changedNodes) {
        area.append(el("p", "ai-item", `节点 ${node.id}（${node.title || ""}）：${projectmindUiLabel(node.change)}${node.fields ? ` · ${node.fields.map(projectmindUiLabel).join("、")}` : ""}`));
      }
      for (const edge of diff.edges?.added || []) area.append(el("p", "ai-item", `新增关系 ${edge.from} → ${edge.to}（${projectmindUiLabel(edge.type)}）`));
      for (const edge of diff.edges?.removed || []) area.append(el("p", "ai-item", `移除关系 ${edge.from} → ${edge.to}（${projectmindUiLabel(edge.type)}）`));
    } catch (error) {
      setStatus("arch-draft-status", `差异读取失败（${error.code}）：${error.message}`, true);
    }
  });

  // ---------- boot ----------
  (async()=>{
    await loadHistory();
    let last=null;try{last=localStorage.getItem('projectmind:last-workspace');}catch(_){}
    if(location.hash!=='#arch'||!last||state.envelope)return;
    try{openEnvelope(await api('GET',`/api/archloop/workspaces/${encodeURIComponent(last)}`));}
    catch(error){setStatus('arch-create-status','无法恢复上次项目，请在历史工作区中重新打开或导入。',true);}
  })();
})();
