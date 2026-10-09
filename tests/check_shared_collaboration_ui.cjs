// DOM user-flow regression; synthetic transport, not native browser acceptance.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'web/index.html'),'utf8'),{url:'https://projectmind.example.invalid/#collab',runScripts:'outside-only'});
const w=dom.window,d=w.document,$=id=>d.getElementById(id);
// Simulate a slow public auth response: scripts execute before it resolves.
const authScript=d.createElement('script');authScript.src='/auth-client.js';d.head.prepend(authScript);
w.projectmindUiLabel=x=>x;
w.HTMLElement.prototype.scrollIntoView=function(){};w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
w.HTMLDialogElement.prototype.close=function(){this.open=false;};
w.URL.createObjectURL=()=> 'blob:fixture';w.URL.revokeObjectURL=()=>{};
w.HTMLAnchorElement.prototype.click=function(){downloads.push(this.download);};
let copied='',saved=null,resolveAuth;const downloads=[],requests=[],authReady=new Promise(resolve=>{resolveAuth=resolve;});
Object.defineProperty(w.navigator,'clipboard',{value:{writeText:async value=>{copied=value;}}});
const rev='sha256:'+'a'.repeat(64),source='b'.repeat(40);
const envelope={workspace:{workspaceId:'ws_fixture',title:'已发布项目',context:'planning'},identity:{mapRevision:rev,mapSourceRevision:source,draftRevision:'draft1',codeRevision:null},lastPublish:{mapRevision:rev,mapSourceRevision:source},draft:{graph:{nodes:[{title:'未发布草稿内容'}],edges:[]}}};
const version={mapId:'map_fixture',mapRevision:rev,codeRevision:null,status:'confirmed_design'};
const packet={schemaVersion:'architecture_handoff_v1',sources:{code:null,architecture:null},versionEnvelope:{version,provenance:{mapSourceRevision:source}},trust:'untrusted_until_local_git_check'};
w.fetch=async(url,options={})=>{
 const body=options.body?JSON.parse(options.body):null;requests.push({url,body,method:options.method||'GET'});
 let value;
 if(url==='/api/auth/session'){await new Promise(resolve=>setImmediate(resolve));w.projectmindSession={actor:'fixture'};resolveAuth();return {ok:true,status:200,json:async()=>w.projectmindSession};}
 await authReady;
 if(url==='/api/snapshot')return {ok:false,status:404,json:async()=>({error:{message:'no curated map'}})};
 if(url==='/api/ai-status')value={configured:false};
 else if(url==='/api/archloop/workspaces')value={workspaces:[envelope.workspace]};
 else if(url==='/api/archloop/records')value={entries:[]};
 else if(url.endsWith('/handover'))value=packet;
 else if(url.includes('/versions/'))value={version,provenance:{mapSourceRevision:source},graph:{nodes:[{title:'已确认的功能',summary:'已发布职责'}],edges:[]},limits:['实际运行未核实']};
 else if(url.endsWith('/fix-tasks'))value={tasks:[{id:'fix_fixture',status:'received',deviation:'需继续核对',acceptance:'检验步骤'}]};
 else if(url.endsWith('/records/export'))value={schemaVersion:'workspace_records_v1',entries:saved?[saved]:[]};
 else if(url.endsWith('/records')&&body){saved={...body,id:'fixture-record',version:1,date:'2026-10-08',author:'fixture',status:'contributor_record',workspaceId:'ws_fixture'};value={entry:saved};}
 else if(url.endsWith('/records'))value={entries:saved?[saved]:[{title:'下一步',body:'参与者记录：继续核对',author:'fixture',origin:'human',status:'contributor_record'}],total:saved?1:1};
 else if(url==='/api/archloop/workspaces/ws_fixture')value=envelope;
 else throw Error('Unexpected route '+url);
 return {ok:true,status:200,json:async()=>structuredClone(value)};
};
const click=target=>{assert.ok(target,'User action must exist');assert.equal(target.disabled,false);target.click();};
const button=(text,scope=d)=>[...scope.querySelectorAll('button')].find(node=>node.textContent===text);
async function settle(){for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
 d.body.dataset.mapMode='false';
 w.eval(fs.readFileSync(path.join(root,'web/view.js'),'utf8'));
 w.eval(fs.readFileSync(path.join(root,'web/work-records.js'),'utf8'));
 const script=path.join(root,'web/collaboration.js');if(fs.existsSync(script))w.eval(fs.readFileSync(script,'utf8'));
 await settle();d.dispatchEvent(new w.CustomEvent('projectmind:workspace',{detail:envelope}));await settle();
 assert.ok($('collab-export'),'Public collaboration must expose an export action, rather than empty legacy frames');
 assert.equal($('collab-shared').hidden,false,'Public UI must wait for asynchronous authentication');
 assert.equal($('collab-workspace').value,'ws_fixture','The active project must have a visible selection');
 click($('collab-export'));await settle();assert.ok($('collab-package-result').querySelector('a[download]'));
 assert.ok($('collab-package-result').textContent.includes('来源核验尚未完成'));
 const link=$('collab-package-result').querySelector('a[download]');assert.ok(link.href.includes('mapSourceRevision='+source));
 click(d.querySelector('.collab-tab[data-page="/ext/continuity"]'));await settle();
 click($('collab-context-refresh'));await settle();
 assert.ok($('collab-context-text').value.includes('已确认的功能'));
 assert.ok(!$('collab-context-text').value.includes('未发布草稿内容'),'Published contents must not be substituted with new draft');
 assert.ok($('collab-context-text').value.includes('参与者记录'));assert.ok($('collab-context-text').value.includes('需继续核对'));
 click($('collab-context-copy'));await settle();assert.equal(copied,$('collab-context-text').value);
 click($('collab-context-download'));assert.ok(downloads.includes('projectmind-context-ws_fixture.md'));
 click(d.querySelector('.collab-tab[data-page="/ext/worklog"]'));await settle();
 const log=$('collab-records-panel');assert.equal(log.hidden,false);const form=log.querySelector('form');assert.ok(form);
 form.elements.title.value='交接进展';form.elements.body.value='由参与者继续核对，不自动确认';
 form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await settle();
 assert.equal(saved.title,'交接进展');assert.equal(saved.expectedMapRevision,rev);assert.equal(saved.expectedDraftRevision,'draft1');
 assert.equal($('collab-frame').getAttribute('src'),null,'Public mode must not invoke map-only extensions');
 assert.ok(!requests.some(r=>r.url.startsWith('/api/extensions/')||r.url.startsWith('/ext/')));
 console.log('PASS: public collaboration tabs, exact-version download, unknown source state, published context, task/record context, copy/download, real record contract, no legacy extension calls.');
 dom.window.close();
})().catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});
