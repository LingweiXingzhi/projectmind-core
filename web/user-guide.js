// User guidance routes to the existing workbench actions. It never accepts a
// candidate, confirms a review or publishes a version on the user's behalf.
(() => {
  const $ = id => document.getElementById(id);
  const make = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  let current = null;
  let nextAction = () => {};
  let connection = null;
  let activeDialog = null;
  let intent = "understand", workspaceId = null, preparingTask = false;

  function button(text, action, primary = false) {
    const b = make('button', text, `button ${primary ? 'primary' : 'ghost'}`);
    b.type = 'button'; b.onclick = action; return b;
  }
  function dialog(title, description) {
    if (activeDialog) activeDialog.close();
    const d = make('dialog', undefined, 'ux-dialog');
    const head = make('div', undefined, 'ux-dialog-head');
    const heading = make('h2', title); heading.id = 'ux-dialog-title';
    const close = button('关闭', () => d.close());
    head.append(heading, close); d.append(head, make('p', description));
    d.setAttribute('aria-labelledby', heading.id);
    d.addEventListener('close', () => { if (activeDialog === d) activeDialog = null; d.remove(); }, {once: true});
    document.body.append(d); activeDialog = d;
    d.showModal(); return d;
  }
  function reveal(id) {
    const target = $(id);
    if (!target) return;
    const closed = target.closest('details:not([open])');
    if (closed) closed.open = true;
    target.scrollIntoView({block: 'center', behavior: 'smooth'});
    if (target.matches('button,input,textarea,select')) target.focus({preventScroll: true});
  }
  function invoke(id) {
    const target = $(id); reveal(id);
    if (target && !target.disabled) target.click();
  }
  function startRoute(context) {
    activateView('arch');
    document.dispatchEvent(new CustomEvent('projectmind:begin-entry', {detail: context}));
    reveal(context === 'planning' ? 'arch-planning-title' : 'arch-repo-path');
  }
  function choices() {
    const d = dialog('你已经有项目了吗？', '选一个起点。之后都在同一个功能图里查看、修改、确认和交接。');
    const rows = make('div', undefined, 'ux-route-choices');
    const existing = button('我有项目 · 导入已有代码', () => { d.close(); startRoute('existing'); }, true);
    existing.append(make('small', '选择本机 Git 仓库，固定代码版本后起草功能图。'));
    const planning = button('还没有项目 · 从想法开始', () => { d.close(); showConnection(true); });
    planning.append(make('small', '先检查 AI 接入，再输入目标和约束，生成架构候选。'));
    rows.append(existing, planning); d.append(rows);
  }
  async function readConnection() {
    const response = await fetch('/api/ai-status');
    if (!response.ok) throw Error(`无法读取 AI 状态（HTTP ${response.status}）`);
    const result = await response.json(); connection = result; return result;
  }
  function showConnection(planning = false) {
    const d = dialog('AI 接入', '接入状态由正在运行的服务提供。先检查配置，再开始生成。');
    const status = make('p', '正在检查…', 'ux-connection-status'); status.setAttribute('role', 'status');
    const help = make('div');
    help.append(make('p', '当前版本需要由运行服务的人配置 API 密钥、模型和服务地址，然后重启服务。页面还不能保存 API 配置。'));
    const details = make('details'); details.append(make('summary', '本机运行者：查看配置方法'));
    details.append(make('p', '在启动 Python 的终端设置 PROJECTMIND_AI_API_KEY、PROJECTMIND_AI_MODEL；使用兼容服务时还需设置 PROJECTMIND_AI_BASE_URL。配置后重启同一个实例。支持的协议与具体示例见仓库 README。不要把密钥放到项目描述里。'));
    help.append(details);
    const actions = make('div', undefined, 'ux-actions');
    const continueButton = button(planning ? '先记录项目想法' : '返回工作台', () => { d.close(); if (planning) startRoute('planning'); });
    const check = async () => {
      status.textContent = '正在检查…';
      try {
        const ai = await readConnection();
        status.textContent = ai.configured ? `服务已配置：${ai.model || '已选择模型'}。实际生成是否成功，以生成结果为准。` : 'AI 尚未配置：现在可以记录想法，真实 AI 生成尚不可用。';
        help.hidden = Boolean(ai.configured);
        continueButton.textContent = planning ? (ai.configured ? '继续 · 输入项目想法' : '先记录项目想法') : '返回工作台';
        renderNext();
      } catch (error) { status.textContent = error.message; }
    };
    actions.append(button('重新检查接入', check), continueButton);
    d.append(status, help, actions); check();
  }
  function help() {
    const d = dialog('按这条流程使用', '普通操作都围绕当前项目的功能图展开。需要时再打开代码、日志和任务。');
    const routes = make('div', undefined, 'ux-help-routes');
    routes.append(make('p', '已有项目：导入 Git 仓库 → 生成候选 → 查看代码证据 → 修正节点和关系。'));
    routes.append(make('p', '新项目：检查 AI 接入 → 填写想法和约束 → 生成候选 → 调整设计。没有代码版本是正常状态。'));
    const steps = make('ol');
    ['起草后先预览候选，再由你点击“应用到草稿”。',
      '点击节点看详情；“编辑节点”修改职责、接口、证据和过程；“编辑关系”修改连线，点击画布连线也可进入。编辑需点击对应的保存按钮。',
      '要留下团队共识：保存版本草稿 → 预览待确认内容 → 确认接受或拒绝 → 发布确认版本。仅在你核对后确认。',
      '发布后可交接理解，或选“落实代码修改”。补充步骤/证据会形成新草稿，需重新确认设计与期望过程、发布，再选择实际涉及的步骤创建任务。',
      '实施后回挂实际分支和提交，实测并由人确认关闭。代码有新提交时，检查代码变化，再复核图和证据。'].forEach(text => steps.append(make('li', text)));
    routes.append(steps, make('p', '草稿、规则候选和 AI 候选都有来源标记；确认设计不等于代码已经实现。'));
    d.append(routes, button('开始 / 添加项目', () => { d.close(); choices(); }, true));
  }
  function chooseIntent(value) {
    intent=value;renderNext();
    if(value==='correct' && current?.selectedNodeId)edit();
    if(value==='deliver')document.dispatchEvent(new CustomEvent('projectmind:close-inspector'));
    if(value==='deliver')reveal(current?.envelope?.identity.mapSourceRevision?'ux-delivery-panel':'ux-review-panel');
  }
  function prepareTask() {
    intent='deliver';preparingTask=true;document.dispatchEvent(new CustomEvent('projectmind:close-inspector'));
    if(!current?.review?.previewDigest && !current?.review?.accepted)$('arch-review-mode').value='design';
    $('ux-task-panel').open=true;renderNext();reveal('ux-task-panel');
  }
  function edit(section = 'basics') {
    document.dispatchEvent(new CustomEvent('projectmind:edit-node', {detail: {section}}));
  }
  function returnToUnsaved(item) {
    document.dispatchEvent(new CustomEvent('projectmind:select-node',{detail:item.nodeId}));
    const section=item.group==='process'?'process':item.group.startsWith('evidence:')?'evidence':/^(relation:|newrelation:)/.test(item.group)?'relations':'basics';
    edit(section);
  }
  function renderNext() {
    if (!current?.envelope) return;
    const {envelope, selectedNodeId, busy, pendingCandidate, syncedRevision, review} = current;
    const graph = envelope.draft?.graph;
    const node = graph?.nodes.find(n => n.id === selectedNodeId);
    $('ux-project-title').textContent = `${envelope.workspace.title || '当前项目'} · ${envelope.workspace.context==='planning'?'新项目规划 · 尚无代码':`代码 ${String(envelope.identity.codeRevision||'未知').slice(0,12)}`}`;
    $('ux-selected').textContent = node ? `已选中：${node.title}` : '先选中一个功能节点';
    for (const id of ['ux-edit-node', 'ux-edit-relations', 'ux-correct-node']) $(id).disabled = !node || busy;
    for(const id of ['ux-task-process','ux-task-evidence'])$(id).disabled=!node||busy;
    const hasCodeEvidence=node?.evidence?.some(item=>item.kind!=='requirement'&&item.path);
    const published=Boolean(envelope.identity.mapSourceRevision);
    const unsaved=current.unsaved||[];
    const graphReady=Boolean(graph) && !pendingCandidate;
    $('ux-intents').hidden=!graphReady;
    for(const b of document.querySelectorAll('[data-ux-intent]')){b.disabled=busy;b.setAttribute('aria-pressed',String(b.dataset.uxIntent===intent));}
    $('ux-intent-copy').hidden=!graphReady;
    $('ux-intent-copy').textContent=intent==='understand'
      ? '点击功能节点看职责与证据。代码来自当前项目的固定提交；候选解释仍待核对。'
      : intent==='correct' ? '先选中节点，再编辑职责、关系或用文字纠正。保存后仍是草稿。'
      : '先核对并发布确认版本，再选择交接理解或落实代码修改。';
    $('ux-review-panel').hidden=!graph || (intent!=='deliver' && !review?.previewDigest);
    $('ux-delivery-panel').hidden=!graph || intent!=='deliver';
    $('ux-prepare-task').disabled=!graph||busy;
    $('ux-generation-panel').hidden=Boolean(graph)&&intent==='deliver';
    if(!graph || pendingCandidate)$('ux-generation-panel').open=true;
    $('ux-delivery-status').textContent=published
      ? '当前图已发布，可生成同版交接包。要修改代码，请先补齐并确认任务范围。'
      : envelope.lastPublish ? '当前草稿已改变。上次版本仍保留，但不包含新编辑；请先重新确认并发布当前草稿。'
      : '当前图还没有确认版本。可以先准备步骤与证据，发布后再交接或创建任务。';
    const publishHint=published?'':'当前草稿尚未发布：补齐内容后，选择“设计与期望过程”预览、确认并发布，再创建任务。';
    $('ux-task-prereqs').textContent=publishHint+(!node?'先在图中选中要交给队友修改的节点。':`当前节点：${node.title}。${node.process?.length?'已有期望步骤（创建前核对设计确认范围）':'还需填写期望步骤'}；${hasCodeEvidence?'已有代码证据，创建时由服务核对':'还需补充代码证据'}。`);
    const notice=$('ux-editor-notice');notice.replaceChildren();notice.hidden=!unsaved.length;
    if(unsaved.length){
      const ids=[...new Set(unsaved.map(item=>item.nodeId))];
      notice.append(make('span',`${ids.length} 个节点有未保存输入，本窗口内切换会保留。请保存或放弃后再确认版本。`));
      notice.append(button('返回未保存编辑',()=>returnToUnsaved(unsaved[0])));
      if(ids.includes(selectedNodeId))notice.append(button('放弃此节点的未保存输入',()=>{
        if(window.confirm('放弃此节点尚未保存的输入？已保存的草稿不变。'))document.dispatchEvent(new CustomEvent('projectmind:discard-edits',{detail:selectedNodeId}));
      }));
    }
    let title, copy, label, step = 2;
    const aiConfigured = connection ? connection.configured : envelope.generation?.configured;
    if (pendingCandidate) {
      title = '查看候选，决定是否采用'; copy = '候选尚未写入草稿。采用后进入功能图工作台；不合适可放弃或重新调整。';
      label = '查看待采用候选'; nextAction = () => reveal('arch-candidate-preview');
    } else if (!graph) {
      title = '起草项目功能图';
      const planning=envelope.workspace.context==='planning';
      copy = aiConfigured ? '生成后查看职责、关系与未知项，再自行决定是否采用。' : planning ? 'AI 尚未配置。可按目标起草规则候选，或检查接入；规则候选仍需你调整与确认。' : 'AI 尚未配置。可根据固定版本的代码符号起草规则候选，职责和关系需人工核对。';
      label = aiConfigured ? '生成 AI 候选' : planning ? '根据目标起草候选' : '根据代码起草候选';
      nextAction = aiConfigured ? () => invoke('arch-generate-button') : () => invoke('arch-rulegen-button');
    } else if(unsaved.length){
      step=3;title='先保存正在编辑的内容';copy='输入还没有写入草稿。切换节点不会丢失，但确认与任务只使用保存后的内容。';
      label='返回未保存编辑';nextAction=()=>returnToUnsaved(unsaved[0]);
    } else if (review?.accepted) {
      step = 4; title = '已接受预览，下一步发布'; copy = '点击发布后才产生可交接的版本；继续改图会取消这次待发布的确认。';
      label = '查看发布操作'; nextAction = () => {intent='deliver';renderNext();reveal('arch-publish-button');};
    } else if (review?.previewDigest) {
      step = 4; title = '本人确认这次内容吗？'; copy = '阅读下面的职责、关系、步骤与证据。接受后可发布；拒绝则回到工作台修改。';
      label = '核对内容并决定'; nextAction = () => reveal('arch-review-result');
    } else if (published) {
      step = 5; title = '确认版本已发布，选择下一步'; copy = '交接理解：生成同版交接包。落实代码修改：补齐步骤、证据与验收标准；改动后需要重新确认发布。';
      label = preparingTask ? '继续准备实施任务' : '交接或落实代码修改';nextAction=()=>{intent='deliver';renderNext();reveal(preparingTask?'ux-task-panel':'ux-delivery-panel');};
    } else if (syncedRevision === envelope.identity.draftRevision) {
      step = 4; title = '草稿已保存，请预览确认范围'; copy = preparingTask?'选择“设计与期望过程”，核对任务所需的步骤；它不代表代码已实现。':'预览、接受和发布均由你主动操作。';
      label = '预览待确认内容'; nextAction = () => {intent='deliver';renderNext();invoke('arch-review-preview-button');};
    } else {
      step = 3; title = intent==='deliver' ? '核对当前草稿，再确认一个版本' : '在功能图里理解和调整项目';
      copy = intent==='deliver' ? '保存版本草稿后预览。要落实代码修改，可先展开下方任务准备，补齐步骤与证据。' : node ? '查看职责和固定版本代码；理解不对可编辑。准备交接时选择“交给队友”。' : '先点击一个功能节点。你可以查看证据、纠正理解，或准备交给队友。';
      label = intent==='deliver'?'保存版本草稿':'交给队友：确认版本';
      nextAction = intent==='deliver'?()=>invoke('arch-sync-button'):()=>chooseIntent('deliver');
    }
    $('ux-next-title').textContent = title; $('ux-next-copy').textContent = copy;
    $('ux-next-action').textContent = busy ? '正在处理，请稍候…' : label; $('ux-next-action').disabled = busy;
    [...document.querySelectorAll('.ux-steps li')].forEach((li, index) => {
      li.classList.toggle('current', index + 1 === step);
      if (index + 1 === step) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
  }

  for(const b of document.querySelectorAll('[data-ux-intent]'))b.onclick=()=>chooseIntent(b.dataset.uxIntent);
  $('ux-prepare-task').onclick=prepareTask;
  document.addEventListener('projectmind:prepare-task-review',()=>{prepareTask();reveal('ux-review-panel');});
  document.addEventListener('projectmind:review-rejected',()=>{intent='correct';renderNext();if(current?.selectedNodeId)edit();});
  $('ux-check-ai').onclick=()=>showConnection();
  $('ux-start').onclick = choices;
  $('ux-help').onclick = $('ux-workflow-help').onclick = help;
  $('ux-next-action').onclick = () => nextAction();
  $('ux-edit-node').onclick = () => edit();
  $('ux-edit-relations').onclick = () => edit('relations');
  $('ux-correct-node').onclick = () => { edit();reveal('arch-correction-input'); };
  $('ux-task-process').onclick=()=>edit('process');
  $('ux-task-evidence').onclick=()=>edit('evidence');
  $('ux-open-workbench').onclick = () => { activateView('arch'); if (!current?.envelope) choices(); };
  document.addEventListener('projectmind:choose-entry', choices);
  document.addEventListener('projectmind:guide-state', event => { current = event.detail;
    const id=current?.envelope?.workspace.workspaceId;
    if(id!==workspaceId){workspaceId=id;intent='understand';preparingTask=false;$('ux-generation-panel').open=!current?.envelope?.draft;
      $('arch-diff-result').replaceChildren();$('arch-task-result').replaceChildren();$('arch-version-result').replaceChildren();}
    renderNext(); });
  // A failed read is never treated as an empty project list. Existing projects
  // remain on the overview and aren't hidden by a first-use modal.
  (async () => {
    try {
      const response = await fetch('/api/archloop/workspaces');
      if (!response.ok) return;
      const result = await response.json();
      if (!Array.isArray(result.workspaces) || result.workspaces.length || document.body.dataset.view !== 'home') return;
      let seen = false;
      try { seen = sessionStorage.getItem('projectmind:onboarding-seen') === 'yes'; } catch (_) {}
      if (!seen && !activeDialog) {
        try { sessionStorage.setItem('projectmind:onboarding-seen', 'yes'); } catch (_) {}
        choices();
      }
    } catch (_) { /* Overview keeps the actual unavailable state. */ }
  })();
})();
