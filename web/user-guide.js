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
      '把已发布的同版交接包交给队友；需要改代码时，先确认并发布当前图，再为有期望过程和代码证据的节点创建开发任务。',
      '实施后回挂实际分支和提交，实测并由人确认关闭。代码有新提交时，检查代码变化，再复核图和证据。'].forEach(text => steps.append(make('li', text)));
    routes.append(steps, make('p', '草稿、规则候选和 AI 候选都有来源标记；确认设计不等于代码已经实现。'));
    d.append(routes, button('开始 / 添加项目', () => { d.close(); choices(); }, true));
  }
  function edit(section = 'basics') {
    document.dispatchEvent(new CustomEvent('projectmind:edit-node', {detail: {section}}));
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
    const publishHint=envelope.identity.mapSourceRevision?'':'先确认并发布当前图，才能创建与这一版绑定的开发任务。';
    $('ux-task-prereqs').textContent=publishHint+(!node?'先在图中选中要交给队友修改的节点。':`当前节点：${node.title}。${node.process?.length?'已有期望步骤':'还需填写期望步骤'}；${hasCodeEvidence?'已有代码证据，创建时由服务核对':'还需补充代码证据'}。`);
    let title, copy, label, step = 2;
    const aiConfigured = connection ? connection.configured : envelope.generation?.configured;
    if (pendingCandidate) {
      title = '先看候选，再决定是否应用'; copy = '候选尚未写入草稿。核对下面的候选摘要，选择应用或放弃。';
      label = '查看待应用候选'; nextAction = () => reveal('arch-candidate-preview');
    } else if (!graph) {
      title = '起草项目功能图';
      copy = aiConfigured ? 'AI 将提出候选。生成后仍需你查看并应用。' : 'AI 尚未配置。可以先接入 AI；也可以使用明确标注的规则候选继续了解项目。';
      label = aiConfigured ? '生成 AI 候选' : '检查 AI 接入';
      nextAction = aiConfigured ? () => invoke('arch-generate-button') : () => showConnection();
    } else if (review?.accepted) {
      step = 4; title = '已接受预览，尚未发布版本'; copy = '确认范围已由你接受。点击发布后才会产生可交接的版本；继续改图会取消这次待发布的预览。';
      label = '查看发布操作'; nextAction = () => reveal('arch-publish-button');
    } else if (review?.previewDigest) {
      step = 4; title = '请核对这次确认范围'; copy = '阅读预览覆盖的节点、关系、过程和证据，然后自行确认接受或拒绝。';
      label = '查看确认预览'; nextAction = () => reveal('arch-review-result');
    } else if (envelope.identity.mapSourceRevision) {
      step = 5; title = '当前图已有确认版本，可以交接'; copy = '导出同版交接包，或查看版本历史。后续继续编辑会形成新的草稿。';
      label = '导出同版交接包'; nextAction = () => invoke('arch-handover-button');
    } else if (syncedRevision === envelope.identity.draftRevision) {
      step = 4; title = '版本草稿已保存，下一步预览确认范围'; copy = '填写审阅者与理由，预览内容。预览、确认和发布均需要你主动操作。';
      label = '预览待确认内容'; nextAction = () => invoke('arch-review-preview-button');
    } else {
      step = 3; title = '查看并修改功能图';
      copy = node ? '职责不对就编辑节点；连线不对就编辑关系。改图完成后，保存版本草稿，再进入确认流程。' : '先点击一个功能节点看职责、证据和关系。可以新增节点，或点击连线修改关系。';
      label = '前往版本确认'; nextAction = () => reveal('ux-review-panel');
    }
    $('ux-next-title').textContent = title; $('ux-next-copy').textContent = copy;
    $('ux-next-action').textContent = busy ? '正在处理，请稍候…' : label; $('ux-next-action').disabled = busy;
    [...document.querySelectorAll('.ux-steps li')].forEach((li, index) => {
      li.classList.toggle('current', index + 1 === step);
      if (index + 1 === step) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
  }

  $('ux-start').onclick = choices;
  $('ux-help').onclick = $('ux-workflow-help').onclick = help;
  $('ux-next-action').onclick = () => nextAction();
  $('ux-edit-node').onclick = () => edit();
  $('ux-edit-relations').onclick = () => edit('relations');
  $('ux-correct-node').onclick = () => { document.body.classList.remove('inspector-hidden'); reveal('arch-correction-input'); };
  $('ux-task-process').onclick=()=>edit('process');
  $('ux-task-evidence').onclick=()=>edit('evidence');
  $('ux-open-workbench').onclick = () => { activateView('arch'); if (!current?.envelope) choices(); };
  document.addEventListener('projectmind:choose-entry', choices);
  document.addEventListener('projectmind:guide-state', event => { current = event.detail; renderNext(); });
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
