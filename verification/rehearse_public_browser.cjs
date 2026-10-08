// Native Chromium against an isolated Waitress + Caddy fixture. No live team approval.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.argv[2]);

async function main(config) {
  const origin = new URL(config.origin);
  assert.equal(origin.protocol, 'https:');
  assert.equal(origin.hostname, 'projectmind.example.invalid');
  const browser = await chromium.launch({headless:true, args:[
    '--host-resolver-rules=MAP projectmind.example.invalid 127.0.0.1'
  ]});
  const errors = [], calls = [], contexts = [];
  async function login() {
    // Only this disposable local CA fixture gets a browser certificate exception.
    // The Python driver separately validates its CA, certificate and hostname.
    const context = await browser.newContext({ignoreHTTPSErrors:true, viewport:{width:1440,height:1100},
      proxy:{server:'http://127.0.0.1:9',bypass:origin.hostname}});
    contexts.push(context);
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', error=>errors.push(error.message));
    page.on('response', response=>{
      const url = new URL(response.url());
      if (url.pathname.startsWith('/api/')) calls.push({method:response.request().method(),
        route:url.pathname.split('/workspaces/')[0], status:response.status()});
    });
    await page.goto(origin.href, {waitUntil:'networkidle'});
    await page.locator('[name=username]').fill('browser-fixture');
    await page.locator('[name=password]').fill(config.password);
    await page.locator('#login button').click();
    await page.waitForURL(origin.href);
    await page.waitForFunction(()=>Boolean(window.projectmindSession));
    return {context,page};
  }
  async function post(page, endpoint, body) {
    return page.evaluate(async ({endpoint,body})=>{
      const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      return {status:response.status, body:await response.json()};
    },{endpoint,body});
  }
  async function dialog(page, reason) {
    const dialog=page.locator('dialog.workspace-dialog[open]');
    await dialog.waitFor();
    const actor=dialog.locator('[name=actor]');
    if(await actor.count()) {
      assert.equal(await actor.inputValue(),'browser-fixture');
      assert.equal(await actor.evaluate(field=>field.readOnly),true);
    }
    for(const name of ['reason','description']) {
      const field=dialog.locator(`[name=${name}]`);
      if(await field.count()) await field.fill(reason);
    }
    await dialog.locator('button[type=submit]').click();
  }
  async function actionResponse(page, suffix, action) {
    const pending=page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname.endsWith(suffix));
    await action();
    const response=await pending;
    assert.equal(response.status(),200,await response.text());
    return response.json();
  }
  try {
    const primary=await login(), page=primary.page;
    await page.locator('[data-view=arch]').click();
    await page.locator('#arch-existing-title').fill('Native browser fixture');
    await page.locator('#arch-existing-desc').fill('Isolated fixture, not real team acceptance');
    const created=await actionResponse(page,'/workspaces',()=>page.locator('#arch-create-existing button[type=submit]').click());
    const workspaceId=created.workspace.workspaceId, base='/api/archloop/workspaces/'+encodeURIComponent(workspaceId);
    await page.locator('#arch-rulegen-button').click();
    await page.getByRole('button',{name:'应用到草稿',exact:true}).click();
    await page.locator('#arch-map-stage .map-node').first().click();
    await page.getByRole('button',{name:'编辑',exact:true}).click();
    await page.getByRole('button',{name:'添加步骤',exact:true}).click();
    await page.getByRole('button',{name:'保存过程',exact:true}).click();
    await page.waitForFunction(()=>document.getElementById('arch-draft-status').textContent.includes('过程已保存'));
    await page.locator('#arch-review-mode').selectOption('design');
    const preview=await actionResponse(page,'/review-preview',async()=>{
      await page.locator('#arch-review-preview-button').click();
      await dialog(page,'FIXTURE ONLY confirm expected design, no claim of code behavior');
    });
    const secondary=await login();
    const rejectedConfirm=await post(secondary.page,base+'/review-confirm',{previewDigest:preview.previewDigest,decision:'accept'});
    assert.equal(rejectedConfirm.status,403);
    await actionResponse(page,'/review-confirm',()=>page.locator('#arch-review-confirm-button').click());
    const rejectedPublish=await post(secondary.page,base+'/publish',{});
    assert.equal(rejectedPublish.status,403);
    const published=await actionResponse(page,'/publish',()=>page.locator('#arch-publish-button').click());
    const form=page.locator('#governed-task-panel form');
    await form.waitFor();
    assert.equal(await form.evaluate(el=>getComputedStyle(el).display),'grid');
    await form.locator('[name=kind]').selectOption('test_observation');
    for(const [name,value] of Object.entries({deviation:'Synthetic return gap',scope:'service.py',
      observation:'Fixture participant observation',acceptance:'Fixture verification after implementation'})) {
      await form.locator(`[name=${name}]`).fill(value);
    }
    await actionResponse(page,'/fix-tasks',()=>form.locator('button[type=submit]').click());
    await page.locator('#governed-task-panel').getByRole('button',{name:'接手',exact:true}).click();
    await dialog(page,'FIXTURE ONLY received');
    await page.locator('#governed-task-panel').getByRole('button',{name:'开始实施',exact:true}).click();
    await dialog(page,'FIXTURE ONLY implementation started');
    await page.locator('#governed-task-panel article[data-task-state=in_progress]').waitFor();
    assert.equal(await page.locator('#arch-fixtask-button').evaluate(el=>el.hidden),true);
    assert.equal(await page.locator('#arch-fixtasks-button').evaluate(el=>el.hidden),true);
    const downloaded=page.waitForEvent('download');
    await page.locator('#arch-handover-button').click();
    const download=await downloaded;
    await download.saveAs(path.join(config.output,'handoff.json'));
    const handoff=JSON.parse(fs.readFileSync(path.join(config.output,'handoff.json'),'utf8'));
    assert.equal(handoff.schemaVersion,'architecture_handoff_v1');
    assert.equal(handoff.versionEnvelope.version.mapRevision,published.version.mapRevision);
    const reads=await page.evaluate(async({base,revision})=>{
      const packet=await (await fetch(base+'/handover')).json();
      const response=await fetch(base+'/versions/'+encodeURIComponent(revision));
      return {packet,status:response.status,version:await response.json()};
    },{base,revision:published.version.mapRevision});
    assert.deepEqual(handoff,reads.packet);
    assert.equal(reads.status,200);
    assert.equal(reads.version.version.mapRevision,published.version.mapRevision);
    const otherVersion=await secondary.page.evaluate(async({base,revision})=>{
      const response=await fetch(base+'/versions/'+encodeURIComponent(revision));
      return {status:response.status,body:await response.json()};
    },{base,revision:published.version.mapRevision});
    assert.equal(otherVersion.status,200);
    assert.equal(otherVersion.body.version.mapRevision,published.version.mapRevision);
    const cookies=await primary.context.cookies();
    const cookie=cookies.find(item=>item.name==='__Host-projectmind');
    assert.ok(cookie && cookie.secure && cookie.httpOnly && cookie.sameSite==='Strict');
    await page.screenshot({path:path.join(config.output,'desktop.png'),fullPage:true});
    await page.setViewportSize({width:430,height:900});
    const layout=await page.evaluate(()=>({width:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth}));
    assert.ok(layout.scrollWidth<=layout.width+1,JSON.stringify(layout));
    const accountControlsFit=await page.locator('.authenticated-controls').evaluate(el=>{
      const header=el.closest('.topbar').getBoundingClientRect();
      return [...el.children].every(child=>{const r=child.getBoundingClientRect();
        return r.top>=header.top-1 && r.bottom<=header.bottom+1 && r.right<=header.right+1;});
    });
    assert.equal(accountControlsFit,true,'Account controls must fit the mobile header');
    await form.scrollIntoViewIfNeeded();
    const fieldsFit=await form.evaluate(el=>[...el.querySelectorAll('select,textarea')].every(field=>{
      const rect=field.getBoundingClientRect(),bounds=el.getBoundingClientRect();
      return rect.left>=bounds.left-1 && rect.right<=bounds.right+1;
    }));
    assert.equal(fieldsFit,true,'Task fields must fit the narrow form');
    await page.screenshot({path:path.join(config.output,'mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    const report={schemaVersion:'projectmind_native_browser_rehearsal_v1',status:'PASS',fixtureOnly:true,
      engine:'actual Chromium',requests:calls.length,pageErrors:errors,actorFromActualSession:true,
      nativeDialogs:true,registeredRepositorySelector:true,ruleCandidateApplied:true,
      expectedProcessSaved:true,fixtureDesignReviewPublished:true,
      crossBrowserConfirmRejected:rejectedConfirm.status,crossBrowserPublishRejected:rejectedPublish.status,
      secureHttpOnlySameSiteCookie:true,governedTaskCreatedReceivedStarted:true,
      nativeHandoffDownloadUnchanged:true,encodedVersionRoute:true,secondBrowserReadsSameVersion:true,
      mobileViewport:layout,taskFormFieldsFit:true,mobileAccountControlsFit:true,browserLocalCertificateException:true,
      realSecondDevice:'NOT_RUN',publicNetwork:'NOT_RUN',realAI:'NOT_RUN',realTeamApproval:'NOT_RUN'};
    fs.writeFileSync(path.join(config.output,'BROWSER_REPORT.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report));
  } finally {
    for(const context of contexts) await context.close();
    await browser.close();
  }
}
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',part=>input+=part);
process.stdin.on('end',()=>main(JSON.parse(input)).catch(error=>{console.error(error);process.exitCode=1;}));
