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
  const w = dom.window;
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
  assert.match(w.document.querySelector('#governed-task-panel article h4').textContent,/in_progress/);
  assert.equal(errors.length,0,errors.join('; '));
  const result={result:'PASS_FULL_DOM_REAL_HTTP',scriptsLoaded:scripts.length,requests:observations.length,
    scriptErrors:errors,actorFromActualSession:true,registeredRepositorySelector:true,
    ruleCandidateApplied:true,expectedProcessSaved:true,fixtureDesignReviewPublished:true,
    governedTaskCreatedReceivedStarted:true,nativeBrowser:'NOT_RUN',TLS:'SIMULATED_PROXY_HEADERS_ONLY',
    layout:'NOT_RUN',realAI:'NOT_RUN',realTeamApproval:'NOT_RUN',polyfills:['dialog','pointer capture','scroll']};
  dom.window.close();return result;
}
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',part=>input+=part);
process.stdin.on('end',()=>main(JSON.parse(input)).then(result=>console.log(JSON.stringify(result,null,2)))
  .catch(error=>{console.error(error);process.exitCode=1;}));
