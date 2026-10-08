// DOM interaction regressions, not native browser or real backend acceptance.
// Run with jsdom available in NODE_PATH; no production dependency is added.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'web/index.html'),'utf8'),{url:'http://127.0.0.1:8899/#arch',runScripts:'outside-only'});
const w=dom.window,d=w.document;
w.structuredClone=structuredClone;w.projectmindUiLabel=x=>x;w.activateView=()=>{};
w.HTMLElement.prototype.scrollIntoView=function(){};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
w.HTMLDialogElement.prototype.close=function(value){this.returnValue=value;this.open=false;this.dispatchEvent(new w.Event('close'));};
w.confirm=()=>true;
const graph={nodes:[{id:'n1',title:'入口',summary:'原职责',status:'candidate',provenance:'rule_based',entryPoints:[],interfaces:[],evidence:[{kind:'code_fact',path:'entry.py',reason:'入口源码'},{kind:'requirement',path:'goal.md',reason:'需求'}],process:[{stepId:'s1',title:'读取',detail:'读取输入',inputs:[],outputs:[],branches:[],next:[]},{stepId:'s2',title:'保存',detail:'保存输出',inputs:[],outputs:[],branches:[],next:[]}]},{id:'n2',title:'存储',summary:'保存',status:'candidate',provenance:'human_input',entryPoints:[],interfaces:[],evidence:[],process:[]}],edges:[]};
let revision=1;let verifyCode=true;
let envelope={workspace:{workspaceId:'ws_test',title:'测试项目',context:'existing_project'},identity:{draftRevision:'r1',codeRevision:'a'.repeat(40),mapRevision:'map1',mapSourceRevision:null},draft:{origin:'rule_based',graph},generation:{configured:false},backend:{},lastPublish:null};
const requests=[];let conflict=false;
const clone=v=>structuredClone(v);
w.fetch=async(url,options={})=>{
 const body=options.body?JSON.parse(options.body):{};requests.push({url,method:options.method||'GET',body});
 let value;
 if(url==='/api/archloop/workspaces')value={workspaces:[envelope.workspace]};
 else if(url.startsWith('/api/archloop/session'))value={csrfToken:'fixture',session:{operator:'测试者'}};
 else if(url==='/api/ai-status')value={configured:false};
 else if(url.endsWith('/apply-ops')){
   if(conflict)return{ok:false,status:409,json:async()=>({error:{code:'REVISION_CONFLICT',message:'已改变'}})};
   for(const op of body.operations){const n=graph.nodes.find(n=>n.id===op.nodeId);if(op.type==='update_node')Object.assign(n,op.fields);if(op.type==='update_process')n.process=op.process;}
   envelope.identity.draftRevision='r'+(++revision);envelope.identity.mapSourceRevision=null;value=clone(envelope);
 }else if(url.endsWith('/sync'))value={operations:[],bDraftRevision:'fixture'};
 else if(url.includes('/versions/'))value={reviewCoverage:{processes:verifyCode?[]:['process-n1']}};
 else if(url.endsWith('/review-preview')){verifyCode=body.verifyCode;value={previewDigest:'digest',reviewCoverage:{nodes:['n1','n2'],edges:[],processes:body.verifyCode?[]:['process-n1'],evidence:[],scope:body.verifyCode?'code':'design'},limits:[],afterGraph:clone(graph),verifyCode:body.verifyCode,expiresInSeconds:300};}
 else if(url.endsWith('/review-confirm'))value={decision:body.decision};
 else if(url.endsWith('/publish')){envelope.identity.mapSourceRevision='b'.repeat(40);envelope.lastPublish={mapRevision:'v1'};value={version:{mapRevision:'v1',status:'confirmed_design'},provenance:{}};}
 else if(url.endsWith('/fix-tasks')&&options.method==='POST')value={id:'task1',status:'queued',deviation:body.deviation,acceptance:body.acceptance};
 else if(url.endsWith('/diff'))value={nodes:[],edges:{added:[],removed:[]}};
 else if(url.includes('/workspaces/ws_test'))value=clone(envelope);
 else throw Error('Unexpected request '+url);
 return {ok:true,status:200,json:async()=>value};
};
const $=id=>d.getElementById(id);
function click(el){assert.ok(el,'target exists');el.click();}
function input(el,value){el.value=value;el.dispatchEvent(new w.Event('input',{bubbles:true}));}
function selectNode(id){d.dispatchEvent(new w.CustomEvent('projectmind:select-node',{detail:id}));}
function button(text,scope=d){return [...scope.querySelectorAll('button')].find(b=>b.textContent===text);}
async function settle(){for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));}
function byLabel(label){return d.querySelector(`dialog [aria-label="${label}"]`);}
async function preview(){click($('arch-review-preview-button'));await settle();input(byLabel('本机操作者（声明，绑定本机会话）'),'测试者');input(byLabel('审阅理由（随预览与版本记录）'),'仅 UI 测试');click(button('生成预览',d.querySelector('dialog.workspace-dialog')));await settle();}
(async()=>{
 w.eval(fs.readFileSync(path.join(root,'web/archworkbench.js'),'utf8'));
 w.eval(fs.readFileSync(path.join(root,'web/user-guide.js'),'utf8'));
 await settle();d.dispatchEvent(new w.CustomEvent('projectmind:open-workspace',{detail:'ws_test'}));await settle();
 assert.equal($('ux-review-panel').hidden,true);assert.equal($('ux-generation-panel').open,false);
 selectNode('n1');click($('ux-edit-node'));input($('arch-basics-editor').querySelector('textarea'),'跨节点保留');
 selectNode('n2');selectNode('n1');click($('ux-edit-node'));
 assert.equal($('arch-basics-editor').querySelector('textarea').value,'跨节点保留');
 let count=requests.length;click($('arch-review-preview-button'));await settle();assert.equal(requests.length,count,'unsaved editor cannot silently review');
 conflict=true;click(button('保存职责修改'));await settle();assert.equal($('arch-basics-editor').querySelector('textarea').value,'跨节点保留');assert.equal($('ux-editor-notice').hidden,false);
 conflict=false;click(button('保存职责修改'));await settle();assert.equal(graph.nodes[0].summary,'跨节点保留');assert.equal($('ux-editor-notice').hidden,true);
 click(button('添加步骤'));input(d.querySelector('[aria-label="第 3 步说明"]'),'待保存步骤说明');selectNode('n2');selectNode('n1');click($('ux-edit-node'));assert.equal(d.querySelector('[aria-label="第 3 步说明"]').value,'待保存步骤说明');
 click(button('保存过程'));await settle();assert.equal(graph.nodes[0].process.length,3);assert.equal($('ux-editor-notice').hidden,true);
 click(d.querySelector('[data-ux-intent="deliver"]'));assert.equal($('ux-review-panel').hidden,false);click($('arch-sync-button'));await settle();
 await preview();assert.ok($('arch-review-result').textContent.includes('跨节点保留'));assert.ok($('arch-review-result').textContent.includes('不在确认范围'));
 const previewText=$('arch-review-result').textContent;click($('arch-diff-button'));await settle();assert.equal($('arch-review-result').textContent,previewText,'diff cannot erase human preview');
 click($('arch-review-reject-button'));await settle();assert.equal($('arch-publish-button').hidden,true);assert.equal(d.querySelector('[data-ux-intent="correct"]').getAttribute('aria-pressed'),'true');assert.ok(!requests.some(r=>r.url.endsWith('/publish')));
 click(d.querySelector('[data-ux-intent="deliver"]'));
 await preview();click($('arch-review-confirm-button'));await settle();click($('arch-publish-button'));await settle();
 selectNode('n1');click($('arch-fixtask-button'));await settle();assert.ok($('arch-task-result').textContent.includes('没有经过设计确认'));assert.equal(d.querySelector('dialog.workspace-dialog'),null,'code-only review must not open task creation');
 click(button('确认这些期望步骤'));await settle();assert.equal($('arch-review-mode').value,'design');click(button('取消',d.querySelector('dialog.workspace-dialog')));await settle();
 click($('ux-prepare-task'));assert.equal($('arch-review-mode').value,'design');
 await preview();assert.ok($('arch-review-result').textContent.includes('不代表代码已'));click($('arch-review-confirm-button'));await settle();assert.equal(requests.filter(r=>r.url.endsWith('/publish')).length,1,'acceptance is separate from publication');
 click($('arch-publish-button'));await settle();assert.equal($('ux-delivery-panel').hidden,false);
 selectNode('n1');click($('arch-fixtask-button'));await settle();input(byLabel('本机操作者（声明，绑定本机会话）'),'测试者');input(byLabel('实际行为与期望的差异、复现方法'),'测试观察：第二步未保存');input(byLabel('验收标准'),'第二步确实保存');
 const process=byLabel('本次要修改的期望步骤');assert.equal(process.value,'');process.value='n1/s2';const evidence=byLabel('允许改动的代码证据（可多选）');assert.equal(evidence.options.length,1,'requirements excluded from code scope');
 click(button('创建实施任务',d.querySelector('dialog.workspace-dialog')));await settle();const task=requests.findLast(r=>r.url.endsWith('/fix-tasks')&&r.method==='POST');assert.equal(task.body.expectedProcessRef,'n1/s2');assert.deepEqual(task.body.scope,['entry.py']);
 click($('ux-task-process'));input(d.querySelector('[aria-label="第 2 步说明"]'),'新期望');click(button('保存过程'));await settle();assert.equal($('arch-fixtask-button').disabled,true);assert.ok($('ux-delivery-status').textContent.includes('不包含新编辑'));
 console.log('PASS: intent routing, saved-draft separation, unsaved basics/process buffers, conflict retention, review scope/contents, diff separation, explicit reject/accept/publish, selectable second task step, requirement exclusion, stale-published task guard.');
 dom.window.close();
})().catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});
