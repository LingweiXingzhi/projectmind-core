// DOM/fixture-fetch rehearsal only. It does not launch a browser or validate TLS/layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require(process.argv[2] || 'jsdom');
const source = path.resolve(__dirname, '../web');
const code = fs.readFileSync(path.join(source, 'governed-tasks.js'), 'utf8');
const html = fs.readFileSync(path.join(source, 'index.html'), 'utf8');
const tick = () => new Promise(resolve => setTimeout(resolve, 5));
const task = () => ({id: 'fix-fixture', taskId: 'fix-fixture', status: 'verification_pending', revision: 4,
  mapRevision: 'sha256:'+'a'.repeat(64), codeRevision: 'b'.repeat(40), scope: ['service.py'],
  deviation: 'Synthetic observation', acceptance: 'Synthetic acceptance', submittedRevision: 'c'.repeat(40)});
const hints = {canCreate: true, mapRevision: 'sha256:'+'a'.repeat(64), draftRevision: 'draft-fixture',
  codeRepoId: 'repo-fixture', codeRevision: 'b'.repeat(40), processes: [
    {id: 'process-fixture', title: 'Fixture process', steps: [{id: 'step-fixture', title: 'Fixture step'}]}]};
function setup(records = [], configured = false) {
  const dom = new JSDOM(html, {url: 'https://projectmind.example.invalid/', runScripts: 'outside-only'});
  const w = dom.window, calls = [];
  const ids = [...w.document.querySelectorAll('[id]')].map(n => n.id);
  assert.equal(new Set(ids).size, ids.length, 'Duplicate document IDs');
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function (value) { this.returnValue = value; this.open = false; this.dispatchEvent(new w.Event('close')); };
  w.projectmindSession = {actor: 'authenticated-fixture'};
  w.fetch = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({url, method: options.method, body});
    let result;
    if (url.endsWith('/fix-task-hints')) result = hints;
    else if (options.method === 'GET' && url.endsWith('/fix-tasks')) result = {tasks: records,
      backend: {kind: 'd_governed_tasks', verificationConfigured: configured}};
    else if (options.method === 'POST' && url.endsWith('/fix-tasks')) result = {};
    else if (body?.action === 'verification_preview') result = {confirmationToken: 'fixture-confirmation',
      verification: {exitCode: 0, outputDigest: 'sha256:'+'d'.repeat(64), fixtureOnly: true}};
    else if (body?.action === 'confirm_verification') { records[0].status = 'verified'; result = records[0]; }
    else throw Error('Unexpected fixture fetch: '+url);
    return {ok: true, status: 200, json: async () => result};
  };
  w.eval(code);
  function open(id = 'ws-fixture') {
    w.document.dispatchEvent(new w.CustomEvent('projectmind:workspace', {detail: {
      workspace: {workspaceId: id}, identity: {mapRevision: hints.mapRevision, draftRevision: hints.draftRevision}}}));
  }
  return {dom, w, calls, open};
}
async function run() {
  const checks = [];
  {
    const {dom, w, calls, open} = setup(); open(); await tick();
    const panel = w.document.getElementById('governed-task-panel');
    assert.equal(panel.hidden, false); assert.match(panel.textContent, /authenticated-fixture/);
    const form = panel.querySelector('form');
    for (const [name, value] of Object.entries({deviation: 'actual fixture deviation', scope: 'service.py\nentry.py',
                                              observation: 'fixture test output', acceptance: 'fixture check passes'})) form.elements[name].value = value;
    form.elements.kind.value = 'test_observation';
    form.dispatchEvent(new w.Event('submit', {cancelable: true})); await tick();
    const sent = calls.find(c => c.method === 'POST' && c.url.endsWith('/fix-tasks')).body;
    assert.deepEqual(sent.scope, ['service.py','entry.py']);
    assert.deepEqual(sent.expectedProcessRef, {processId: 'process-fixture', stepIds: ['step-fixture']});
    assert.equal(sent.expectedMapRevision, hints.mapRevision); assert.equal(sent.expectedDraftRevision, hints.draftRevision);
    assert.equal(sent.evidence[0].codeRevision, hints.codeRevision); assert.equal(sent.evidence[0].kind, 'test_observation');
    assert.equal('actor' in sent, false); assert.equal('command' in sent, false);
    checks.push('form sends confirmed process, exact versions, relative scope and declared observation source');
    let legacy = 0; w.document.getElementById('arch-fixtask-button').disabled = false;
    w.document.getElementById('arch-fixtask-button').addEventListener('click', () => legacy++);
    w.document.getElementById('arch-fixtask-button').click(); await tick();
    assert.equal(legacy, 0); checks.push('public task action intercepts the legacy creation flow'); dom.window.close();
  }
  {
    const {dom, w, calls, open} = setup([task()], true); open(); await tick();
    const find = text => [...w.document.querySelectorAll('#governed-task-panel button')].find(b => b.textContent === text);
    find('请求真实验证预览').click(); await tick();
    assert.match(w.document.querySelector('#governed-task-panel pre').textContent, /outputDigest/);
    assert.equal(w.localStorage.length, 0);
    find('核对结果后确认').click(); await tick();
    const dialog = w.document.querySelector('dialog.workspace-dialog[open]');
    dialog.querySelector('[name=reason]').value = 'Synthetic explicit human fixture decision';
    dialog.querySelector('form').dispatchEvent(new w.Event('submit', {cancelable: true})); await tick();
    const sent = calls.find(c => c.body?.action === 'confirm_verification').body;
    assert.equal(sent.confirmationToken, 'fixture-confirmation'); assert.equal(sent.expectedRevision, 4);
    assert.equal(sent.expectedMapRevision, hints.mapRevision);
    assert.equal(find('核对结果后确认'), undefined);
    checks.push('verification remains readable after refresh; confirmation is memory-only and consumed'); dom.window.close();
  }
  {
    const {dom, w, calls, open} = setup([task()], false); open(); await tick();
    const preview = [...w.document.querySelectorAll('#governed-task-panel button')].find(b => b.textContent === '请求真实验证预览');
    assert.equal(preview.disabled, true); preview.click(); await tick();
    assert.equal(calls.filter(c => c.body?.action === 'verification_preview').length, 0);
    assert.match(w.document.getElementById('governed-task-panel').textContent, /真实验证器尚未配置/);
    checks.push('unconfigured verifier stays unavailable without client-side closure'); dom.window.close();
  }
  console.log(JSON.stringify({result: 'PASS_DOM_REHEARSAL', checks, fixtureFetch: true,
    dialogAndScrollPolyfills: true, nativeBrowser: 'NOT_RUN', TLS: 'NOT_RUN_IN_THIS_HARNESS', layout: 'NOT_RUN'}, null, 2));
}
run().catch(error => { console.error(error); process.exitCode = 1; });
