// Full source scripts + real local WSGI HTTP. Proxy HTTPS headers are simulated.
// Dialog/pointer/scroll are DOM polyfills; this is not native browser/layout/TLS acceptance.
const fs = require('node:fs');
const http = require('node:http');
const assert = require('node:assert/strict');
const {JSDOM, CookieJar, VirtualConsole} = require(process.argv[2] || 'jsdom');
async function main(config) {
  const origin = 'https://projectmind.example.invalid';
  const jar = new CookieJar(), observations = [], errors = [];
  class BrowserRequest extends Request {
    constructor(input, options) { super(typeof input === 'string' ? new URL(input, origin) : input, options); }
  }
  async function fetchLocal(input, options) {
    const request = new BrowserRequest(input, options), url = new URL(request.url);
    assert.equal(url.origin, origin, 'Fixture may only contact its local app');
    const body = ['GET','HEAD'].includes(request.method) ? null : Buffer.from(await request.arrayBuffer());
    const headers = Object.fromEntries(request.headers);
    headers.Host = url.host;
    const cookie = jar.getCookieStringSync(url.href); if (cookie) headers.Cookie = cookie;
    if (!['GET','HEAD'].includes(request.method)) headers.Origin = origin;
    if (body) headers['Content-Length'] = String(body.length);
    return new Promise((resolve, reject) => {
      const req = http.request({host: '127.0.0.1', port: config.port, path: url.pathname+url.search,
        method: request.method, headers}, response => {
        const buffers = [];
        for (const cookie of response.headers['set-cookie'] || []) jar.setCookieSync(cookie, url.href);
        response.on('data', part => buffers.push(part));
        response.on('end', () => {
          observations.push({method: request.method, route: url.pathname.split('/workspaces/')[0], status: response.statusCode});
          resolve(new Response(Buffer.concat(buffers), {status: response.statusCode, headers: response.headers}));
        });
      });
      req.on('error', reject); req.end(body);
    });
  }
  const login = await fetchLocal('/api/auth/login', {method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({username: config.username, password: config.password})});
  assert.equal(login.status, 200); await login.arrayBuffer();
  const page = await fetchLocal('/'); assert.equal(page.status, 200);
  const console = new VirtualConsole(); console.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(await page.text(), {url: origin+'/', runScripts:'outside-only', cookieJar:jar, virtualConsole:console});
  const w = dom.window, blobs=new Map(), downloads=[];
  w.Blob=Blob;
  w.URL.createObjectURL=blob=>{const url='blob:fixture/'+blobs.size;blobs.set(url,blob);return url;};
  w.URL.revokeObjectURL=()=>{};
  w.HTMLAnchorElement.prototype.click=function(){if(this.download)downloads.push({name:this.download,blob:blobs.get(this.href)});};
  w.fetch = fetchLocal; w.Request = BrowserRequest; w.Headers = Headers;
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.HTMLElement.prototype.setPointerCapture = () => {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function (value) { this.returnValue = value; this.open = false; this.dispatchEvent(new w.Event('close')); };
  w.addEventListener('error', event => errors.push(event.message));
  const scripts = [...w.document.querySelectorAll('script[src]')].map(s => s.getAttribute('src'));
  for (const source of scripts) {
    const response = await fetchLocal(source); assert.equal(response.status,200,source);
    w.eval(await response.text());
  }
  async function wait(predicate, description) {
    for (let i=0;i<400;i++) { if (predicate()) return; await new Promise(r=>setTimeout(r,25)); }
    throw Error('DOM condition not reached: '+description+'; script errors '+errors.join('; '));
  }
  const find = text => [...w.document.querySelectorAll('button')].find(b => b.textContent===text);
  function submit(form) { form.dispatchEvent(new w.Event('submit',{cancelable:true,bubbles:true})); }
  async function dialog(reason) {
    await wait(()=>w.document.querySelector('dialog.workspace-dialog[open]'),'active dialog');
    const dialog=w.document.querySelector('dialog.workspace-dialog[open]');
    const actor=dialog.querySelector('[name=actor]');
    if(actor){assert.equal(actor.value,config.username);assert.equal(actor.readOnly,true);}
    for(const name of ['reason','description']) {const field=dialog.querySelector(`[name=${name}]`);if(field)field.value=reason;}
    submit(dialog.querySelector('form'));
  }
  await wait(()=>w.projectmindSession,'server session');
  assert.equal(w.document.getElementById('view-worklog').querySelector('h1').textContent,'工作日志 项目记忆');
  assert.equal(w.projectmindUiLabel('verification_pending'),'待核验');
  assert.equal(w.projectmindUiLabel('unknown_identifier'),'unknown_identifier');
  assert.equal(w.document.getElementById('arch-repo-path').tagName,'SELECT');
  w.activateView('arch');
  w.document.getElementById('arch-existing-title').value='Synthetic DOM + HTTP fixture';
  w.document.getElementById('arch-existing-desc').value='Fixture only; no real team model approval';
  submit(w.document.getElementById('arch-create-existing'));
  await wait(()=>!w.document.getElementById('arch-workspace').hidden,'created workspace');
  w.document.getElementById('arch-rulegen-button').click();
  await wait(()=>find('应用到草稿'),'rule candidate'); find('应用到草稿').click();
  await wait(()=>w.document.querySelector('#arch-map-stage .map-node'),'candidate draft');
  w.document.querySelector('#arch-map-stage .map-node').click(); find('编辑').click();
  find('添加步骤').click(); find('保存过程').click();
  await wait(()=>w.document.getElementById('arch-draft-status').textContent.includes('过程已保存'),'expected process saved');
  w.document.getElementById('arch-review-mode').value='design';
  w.document.getElementById('arch-review-preview-button').click();
  await dialog('FIXTURE ONLY confirm expected design; no claim of real code behavior');
  await wait(()=>!w.document.getElementById('arch-review-confirm-button').hidden,'human review preview');
  w.document.getElementById('arch-review-confirm-button').click();
  await wait(()=>!w.document.getElementById('arch-publish-button').hidden,'confirmed fixture preview');
  w.document.getElementById('arch-publish-button').click();
  await wait(()=>w.document.querySelector('#governed-task-panel form'),'published task hints');
  const form=w.document.querySelector('#governed-task-panel form');form.elements.kind.value='test_observation';
  for(const [name,value] of Object.entries({deviation:'Synthetic observed return gap',scope:'service.py',
      observation:'Participant fixture observation, not real runtime acceptance',acceptance:'Synthetic check after implementation'})) form.elements[name].value=value;
  submit(form);await wait(()=>w.document.querySelector('#governed-task-panel article h4'),'created governed task');
  find('接手').click();await dialog('FIXTURE ONLY received');
  await wait(()=>find('开始实施'),'task received');find('开始实施').click();await dialog('FIXTURE ONLY started');
  await wait(()=>find('回挂实现提交'),'task in progress');
  assert.equal(w.document.querySelector('#governed-task-panel article').dataset.taskState,'in_progress');
  assert.match(w.document.querySelector('#governed-task-panel article h4').textContent,/实施中/);
  w.document.getElementById('arch-handover-button').click();
  await wait(()=>downloads.length>0,'native handoff download capture');
  const handoff=JSON.parse(await downloads[0].blob.text());
  assert.equal(handoff.schemaVersion,'architecture_handoff_v1');
  // Existing-project publication is confirmed_cognition; verifyCode=false
  // does not relabel that machine status as a planning/design workspace.
  assert.equal(handoff.versionEnvelope.version.status,'confirmed_cognition','Machine status remains unchanged');
  const original=await (await w.fetch('/api/archloop/workspaces/'+encodeURIComponent(handoff.workspaceId)+'/handover')).json();
  assert.deepEqual(handoff,original,'Downloaded JSON is the unchanged native handoff');
  assert.ok(downloads[0].name.includes(handoff.versionEnvelope.version.mapId));
  assert.match(w.document.getElementById('arch-version-result').textContent,/同版交接包/);
  assert.equal(w.document.getElementById('arch-fixtask-button').hidden,true);
  assert.equal(w.document.getElementById('arch-fixtasks-button').hidden,true);
  assert.ok(!w.document.getElementById('arch-version-result').textContent.includes('undefined'));
  w.activateView('worklog');
  const recordPanel=w.document.querySelector('[data-shared-records=all]');
  await wait(()=>recordPanel.querySelector('form'),'shared record form');
  const within=(panel,text)=>[...panel.querySelectorAll('button')].find(b=>b.textContent===text);
  within(recordPanel,'新建记录').click();
  let recordForm=recordPanel.querySelector('form');
  recordForm.elements.title.value='Synthetic DOM shared log';recordForm.elements.body.value='Fixture only participant progress';
  submit(recordForm);
  await wait(()=>within(recordPanel,'Synthetic DOM shared log'),'shared record saved');
  within(recordPanel,'Synthetic DOM shared log').click();recordForm=recordPanel.querySelector('form');
  recordForm.elements.body.value='Synthetic edited log';submit(recordForm);
  await wait(()=>recordPanel.querySelector('article')?.textContent.includes('v2'),'edited record CAS');
  within(recordPanel,'查看历史').click();await wait(()=>recordPanel.querySelector('article pre'),'record history');
  assert.match(recordPanel.querySelector('article pre').textContent,/"version": 1/);
  // Race a real second request against the editor; conflict must retain entered text.
  const id=recordPanel.querySelector('select').value;
  const endpoint='/api/archloop/workspaces/'+encodeURIComponent(id);
  const current=await (await w.fetch(endpoint)).json();
  const listing=await (await w.fetch(endpoint+'/records')).json();const item=listing.entries[0];
  const external=await w.fetch(endpoint+'/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    category:item.category,date:item.date,title:item.title,body:'Synthetic other request edit',origin:'human',id:item.id,
    expectedVersion:item.version,expectedMapRevision:current.identity.mapRevision,expectedDraftRevision:current.identity.draftRevision})});
  assert.equal(external.status,200);recordForm=recordPanel.querySelector('form');
  recordForm.elements.body.value='Synthetic retained unsaved input';submit(recordForm);
  await wait(()=>recordPanel.querySelector('[role=status]').textContent.includes('输入已保留'),'conflict message');
  assert.equal(recordForm.elements.body.value,'Synthetic retained unsaved input');
  w.activateView('decisions');const decisions=w.document.querySelector('[data-shared-records=decision]');
  within(decisions,'新建记录').click();const decisionForm=decisions.querySelector('form');
  decisionForm.elements.title.value='Synthetic AI decision alternative';decisionForm.elements.body.value='Not approved';decisionForm.elements.origin.value='ai';
  submit(decisionForm);await wait(()=>within(decisions,'Synthetic AI decision alternative'),'AI candidate decision');
  assert.match(decisions.querySelector('article').textContent,/AI 候选/);
  assert.match(decisions.textContent,/不代表团队批准/);
  const next=await (await w.fetch('/api/archloop/workspaces',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({context:'planning',title:'Synthetic other workspace',goals:'Fixture only',constraints:'No fake code',description:'Fixture'})})).json();
  w.document.dispatchEvent(new w.CustomEvent('projectmind:workspace',{detail:next}));
  await wait(()=>recordPanel.querySelector('[role=status]').textContent.includes('未保存输入已保留'),'workspace switch keeps unsaved text');
  assert.equal(recordForm.elements.body.value,'Synthetic retained unsaved input');
  assert.equal(errors.length,0,errors.join('; '));
  const result={result:'PASS_FULL_DOM_REAL_HTTP',scriptsLoaded:scripts.length,requests:observations.length,
    scriptErrors:errors,actorFromActualSession:true,registeredRepositorySelector:true,
    ruleCandidateApplied:true,expectedProcessSaved:true,fixtureDesignReviewPublished:true,
    governedTaskCreatedReceivedStarted:true,sharedRecordSavedEditedHistory:true,recordConflictRetainsInput:true,
    aiDecisionRemainsCandidate:true,nativeBrowser:'NOT_RUN',TLS:'SIMULATED_PROXY_HEADERS_ONLY',
    workspaceSwitchRetainsUnsavedInput:true,
    chineseLabels:true,unknownIdentifiersPreserved:true,nativeHandoffJsonCapturedUnchanged:true,
    layout:'NOT_RUN',realAI:'NOT_RUN',realTeamApproval:'NOT_RUN',polyfills:['dialog','pointer capture','scroll','Blob URL/download capture']};
  dom.window.close();return result;
}
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',part=>input+=part);
process.stdin.on('end',()=>main(JSON.parse(input)).then(result=>console.log(JSON.stringify(result,null,2)))
  .catch(error=>{console.error(error);process.exitCode=1;}));
