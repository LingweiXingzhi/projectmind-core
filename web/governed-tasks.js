// Shared-server task controls. Identity comes from the server session; approvals stay in memory.
(() => {
  const panel = document.getElementById('governed-task-panel');
  if (!panel) return;
  let workspace = null, fingerprint = '', pending = false, generation = 0;
  const previews = new Map();
  const element = (tag, text, cls) => {
    const value = document.createElement(tag);
    if (text !== undefined) value.textContent = text;
    if (cls) value.className = cls;
    return value;
  };
  const base = () => `/api/archloop/workspaces/${encodeURIComponent(workspace.workspace.workspaceId)}`;
  const label = value => typeof projectmindUiLabel === 'function' ? projectmindUiLabel(value) : value;
  async function api(method, path, body) {
    const response = await fetch(path, {method, headers: {'Content-Type': 'application/json'},
      body: method === 'POST' ? JSON.stringify(body) : undefined});
    const result = await response.json();
    if (!response.ok) throw Error(`${result.error?.code || response.status}：${result.error?.message || '请求未完成'}`);
    return result;
  }
  function message(text) {
    const status = panel.querySelector('[data-task-status]');
    if (status) status.textContent = text;
  }
  function button(text, action) {
    const value = element('button', text, 'button ghost'); value.type = 'button';
    value.onclick = async () => {
      if (pending) return;
      pending = true; value.disabled = true;
      try { await action(); } catch (error) { message(error.message); }
      finally { pending = false; if (value.isConnected) value.disabled = false; }
    };
    return value;
  }
  function dialog(title, fields, action) {
    return new Promise(resolve => {
      const modal = element('dialog', undefined, 'workspace-dialog');
      const form = element('form'); form.method = 'dialog'; form.append(element('h2', title));
      const controls = new Map();
      for (const field of fields) {
        const label = element('label', field.label);
        const input = element(field.type === 'textarea' ? 'textarea' : 'input');
        input.name = field.name; input.required = true;
        if (field.type === 'textarea') input.rows = 3;
        if (field.pattern) input.pattern = field.pattern;
        if (field.placeholder) input.placeholder = field.placeholder;
        input.setAttribute('aria-label', field.label); controls.set(field.name, input);
        label.append(input); form.append(label);
      }
      const cancel = element('button', '取消', 'button ghost'); cancel.type = 'button';
      cancel.onclick = () => modal.close('cancel');
      const submit = element('button', action, 'button primary'); submit.type = 'submit';
      form.append(cancel, submit); modal.append(form); document.body.append(modal);
      form.onsubmit = event => { event.preventDefault(); if (form.reportValidity()) modal.close('submit'); };
      modal.addEventListener('close', () => {
        resolve(modal.returnValue === 'submit'
          ? Object.fromEntries([...controls].map(([name, control]) => [name, control.value.trim()])) : null);
        modal.remove();
      }, {once: true});
      modal.showModal(); controls.values().next().value?.focus();
    });
  }
  async function action(task, name, values = {}) {
    const payload = {action: name, ...values};
    if (name !== 'verification_preview') Object.assign(payload,
      {expectedRevision: task.revision, expectedMapRevision: task.mapRevision});
    return api('POST', `${base()}/fix-tasks/${encodeURIComponent(task.id)}/governance`, payload);
  }
  function taskCard(task, capability) {
    const card = element('article', undefined, 'detail-section');
    card.dataset.taskState = task.status;
    card.append(element('h4', `${task.id} · ${label(task.status)}`), element('p', task.deviation),
      element('p', `基线 ${task.codeRevision} · 图 ${task.mapRevision}`),
      element('p', `允许路径：${task.scope.join('、')}`), element('p', `验收：${task.acceptance}`));
    if (task.submittedRevision) card.append(element('p', `回挂提交：${task.submittedRevision}`));
    const controls = element('div', undefined, 'compare-controls');
    const transition = status => async () => {
      const values = await dialog('记录任务反馈', [{name: 'description', label: '实际进展或阻塞原因', type: 'textarea'}], '保存反馈');
      if (!values) return;
      await action(task, 'transition', {status, ...values}); await refresh();
    };
    if (task.status === 'queued') controls.append(button('接手', transition('received')));
    if (task.status === 'received' || task.status === 'rejected') controls.append(button('开始实施', transition('in_progress')));
    if (['queued', 'received', 'in_progress', 'verification_pending'].includes(task.status)) controls.append(button('记录阻塞 / 拒绝', transition('rejected')));
    if (task.status === 'in_progress') controls.append(button('回挂实现提交', async () => {
      const values = await dialog('回挂独立分支的实现', [
        {name: 'revision', label: '完整 40 位 Git 提交 SHA', pattern: '[0-9a-f]{40}'},
        {name: 'evidence', label: '实施说明与验证依据（不会代替真实验证）', type: 'textarea'}], '校验并回挂');
      if (!values) return;
      await action(task, 'submit', values); await refresh();
    }));
    if (task.status === 'verification_pending') {
      if (!capability.verificationConfigured) card.append(element('p', '真实验证器尚未配置；任务保持待验证，偏差不会关闭。'));
      const preview = button('请求真实验证预览', async () => {
        const result = await action(task, 'verification_preview');
        previews.set(task.id, {token: result.confirmationToken, revision: task.revision,
                              map: task.mapRevision, result: result.verification});
        await refresh();
      });
      preview.disabled = !capability.verificationConfigured; controls.append(preview);
      const authorization = previews.get(task.id);
      if (authorization?.revision === task.revision && authorization.map === task.mapRevision)
        card.append(element('pre', JSON.stringify(authorization.result, null, 2)));
      if (authorization?.revision === task.revision && authorization.map === task.mapRevision) controls.append(button('核对结果后确认', async () => {
        const values = await dialog('人工确认本次真实验证', [{name: 'reason', label: '你核查的结果与确认理由', type: 'textarea'}], '确认结果');
        if (!values) return;
        await action(task, 'confirm_verification', {confirmationToken: authorization.token, ...values});
        previews.delete(task.id); await refresh();
      }));
    }
    if (task.verification) card.append(element('p', task.verification.fixtureOnly
      ? '仅测试夹具验证；不代表真实团队项目通过。' : '已记录本次服务器验证及人工确认；以证据范围为限。'));
    controls.append(button('下载任务说明', async () => {
      const result = await api('GET', `${base()}/fix-tasks/${encodeURIComponent(task.id)}/markdown`);
      const url = URL.createObjectURL(new Blob([result.markdown], {type: 'text/markdown;charset=utf-8'}));
      const link = element('a'); link.href = url; link.download = result.filename; link.click(); URL.revokeObjectURL(url);
    }));
    card.append(controls); return card;
  }
  async function refresh() {
    if (!workspace || !window.projectmindSession) return;
    const current = ++generation, path = base();
    panel.hidden = false;
    panel.replaceChildren(element('h3', '实施任务', 'section-title'));
    panel.querySelector('h3').id = 'governed-task-title';
    const status = element('p', '读取任务与已确认期望过程…', 'compare-status'); status.dataset.taskStatus = '';
    panel.append(status);
    const [tasks, hint] = await Promise.allSettled([api('GET', path+'/fix-tasks'), api('GET', path+'/fix-task-hints')]);
    if (current !== generation) return;
    if (tasks.status !== 'fulfilled') { message(tasks.reason.message); return; }
    if (tasks.value.backend?.kind !== 'd_governed_tasks') { panel.hidden = true; return; }
    const capability = tasks.value.backend;
    const controls = element('div', undefined, 'compare-controls');
    controls.append(button('刷新任务', refresh)); panel.append(controls);
    if (hint.status !== 'fulfilled') message(hint.reason.message);
    else if (!hint.value.canCreate) message(hint.value.disabledReason === 'CODE_REQUIRED'
      ? '规划版本没有代码；关联真实代码并发布版本后才能创建实施任务。'
      : '期望过程尚未纳入复核范围。请选择「设计与期望过程」进行预览、确认和发布。');
    else {
      const hints = hint.value;
      message('选择已确认过程，记录实际观察与允许路径。观察记录需真实验证后才能关闭偏差。');
      const form = element('form');
      const process = element('select'); process.name = 'process'; process.setAttribute('aria-label', '已确认的期望过程');
      for (const item of hints.processes) { const option = element('option', item.title || item.id); option.value = item.id; process.append(option); }
      const steps = element('select'); steps.name = 'steps'; steps.multiple = true; steps.required = true;
      steps.setAttribute('aria-label', '本任务涉及的步骤');
      function chooseProcess() { steps.replaceChildren(); const chosen = hints.processes.find(p => p.id === process.value);
        for (const [index, step] of chosen.steps.entries()) { const option = element('option', step.title || step.id); option.value = step.id; option.selected = index === 0; steps.append(option); } }
      process.onchange = chooseProcess; chooseProcess();
      form.append(element('p', `操作者：${window.projectmindSession.actor}（登录账户）`));
      for (const [label, input] of [['已确认的期望过程', process], ['本任务涉及的步骤', steps]]) {
        const wrapper = element('label', label); wrapper.append(input); form.append(wrapper);
      }
      const kind = element('select'); kind.name = 'kind'; kind.required = true;
      kind.setAttribute('aria-label', '实际观察来源');
      const empty = element('option', '选择实际观察来源'); empty.value = ''; empty.disabled = true; empty.selected = true;
      kind.append(empty);
      for (const [value, label] of [['test_observation', '测试观察（参与者记录）'], ['trace_observation', '运行跟踪观察（参与者记录）']]) {
        const option = element('option', label); option.value = value; kind.append(option);
      }
      const kindLabel = element('label', '实际观察来源'); kindLabel.append(kind); form.append(kindLabel);
      for (const [name, label] of [['deviation', '实际观察与期望的差异'], ['scope', '允许改动的仓库相对路径，每行一个'],
                                  ['observation', '观察证据与复现说明'], ['acceptance', '验收要求']]) {
        const input = element('textarea'); input.name = name; input.rows = 3; input.required = true;
        const wrapper = element('label', label); wrapper.append(input); form.append(wrapper);
      }
      const submit = element('button', '创建实施任务', 'button primary'); submit.type = 'submit'; form.append(submit);
      form.onsubmit = async event => {
        event.preventDefault(); if (pending || !form.reportValidity()) return;
        pending = true; submit.disabled = true;
        const value = new FormData(form);
        try {
          await api('POST', path+'/fix-tasks', {expectedMapRevision: hints.mapRevision, expectedDraftRevision: hints.draftRevision,
            expectedProcessRef: {processId: process.value, stepIds: [...steps.selectedOptions].map(o => o.value)},
            deviation: value.get('deviation').trim(), scope: value.get('scope').split(/\r?\n/).map(s => s.trim()).filter(Boolean),
            evidence: [{kind: value.get('kind'), codeRepoId: hints.codeRepoId, codeRevision: hints.codeRevision, detail: value.get('observation').trim()}],
            acceptance: value.get('acceptance').trim()}); await refresh();
        } catch (error) { message(error.message); }
        finally { pending = false; if (submit.isConnected) submit.disabled = false; }
      };
      panel.append(form);
    }
    if (!tasks.value.tasks.length) panel.append(element('p', '该工作区还没有实施任务。'));
    for (const task of tasks.value.tasks) panel.append(taskCard(task, capability));
  }
  document.addEventListener('projectmind:workspace', event => {
    const next = event.detail;
    if (!next || !window.projectmindSession) return;
    const key = `${next.workspace.workspaceId}|${next.identity.mapRevision}|${next.identity.draftRevision}`;
    if (key === fingerprint) return;
    if (workspace?.workspace.workspaceId !== next.workspace.workspaceId) previews.clear();
    workspace = next; fingerprint = key;
    refresh().catch(error => message(error.message));
  });
  document.getElementById('arch-fixtask-button')?.addEventListener('click', event => {
    if (!window.projectmindSession || !workspace) return;
    event.stopImmediatePropagation(); refresh().catch(error => message(error.message));
    panel.scrollIntoView({block: 'nearest'});
  }, true);
})();
