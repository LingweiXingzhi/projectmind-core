// Deterministic DOM regressions; native browser and real-provider results are separate.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
async function settle(){for(let i=0;i<6;i++)await new Promise(r=>setImmediate(r));}
async function scenario(demo,configure=false){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'web/index.html'),'utf8'),{url:`http://127.0.0.1:8899/${demo?'?demo=1':configure?'?configure-ai=shared':''}#arch`,runScripts:'outside-only'});
 const w=dom.window,d=w.document;w.Request=Request;w.Headers=Headers;w.activateView=()=>{};
 w.HTMLElement.prototype.scrollIntoView=function(){};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 let approve=false;w.confirm=()=>approve;let checkFails=false;
 const requests=[],network=[];let mode='shared';
 const budget={tokenLimit:50000,outputLimit:2048,remainingTokens:50000,chargedTokens:0,reportedTokens:0,estimatedTokens:0};
 const profiles={shared:{canEdit:true,configured:true,hasKey:true,baseUrl:'https://shared.invalid/v1',model:'shared-fixture',protocol:'chat_completions',budget},personal:{canEdit:true,configured:false,hasKey:false,baseUrl:'https://api.openai.com/v1',model:'',protocol:'responses',budget}};
 w.fetch=async(input,init)=>{network.push({url:typeof input==='string'?input:input.url,headers:init?.headers||input.headers});return {ok:true,json:async()=>({workspaces:[{}]})};};
 w.projectmindAISettingsRequest=async(url,body,method='POST')=>{
   requests.push({url,body,method});
   if(url.endsWith('/select'))mode=body.mode;
   if(url==='/api/ai-settings'&&method==='POST'){
     assert.equal(body.mode,mode);assert.equal(body.apiKey,'SYNTHETIC-DOM-NOT-A-REAL-KEY');
     profiles[mode]={...profiles[mode],configured:true,hasKey:true,baseUrl:body.baseUrl,model:body.model,protocol:body.protocol};
   }
   if(url.endsWith('/test'))return {connected:true,note:'fixture connected',budget:{...budget,chargedTokens:15,reportedTokens:15,remainingTokens:49985}};
   if(url.endsWith('/check')){if(checkFails)throw Error('fixture provider unavailable');return {connected:true,note:'API 当前可用：本次连接检查成功。',budget};}
   return {...profiles[mode],mode,personalLifetime:'account'};
 };
 w.eval(fs.readFileSync(path.join(root,'web/user-guide.js'),'utf8'));
 if(!configure)d.getElementById('ux-check-ai').click();await settle();
 if(configure)assert.equal(requests[0].url,'/api/ai-settings?mode=shared','configuration link opens shared settings directly');
 const dialog=d.querySelector('dialog.ux-dialog'),form=dialog.querySelector('form');
 const button=text=>[...dialog.querySelectorAll('button')].find(b=>b.textContent===text);
 const field=name=>form.elements.namedItem(name);
 const input=(name,value)=>{field(name).value=value;field(name).dispatchEvent(new w.Event('input',{bubbles:true}));};
 assert.equal(dialog.querySelector('.ux-ai-budget').hidden,true);assert.equal(dialog.querySelector('.ux-ai-budget').textContent,'');
 assert.equal(requests.some(r=>r.url.endsWith('/check')),false,'opening never charges for a model check');
 button('检查 API 是否可用').click();await settle();
 assert.ok(requests.some(r=>r.url.endsWith('/check')&&r.body.mode==='shared'));
 assert.ok(dialog.querySelector('.ux-connection-status').textContent.includes('本次连接检查成功'));
 checkFails=true;button('检查 API 是否可用').click();await settle();
 assert.ok(dialog.querySelector('.ux-connection-status').textContent.includes('API 检查未通过'));
 assert.equal(dialog.querySelector('.ux-ai-budget').hidden,true);checkFails=false;
 if(demo){
   assert.equal(form.hidden,true);assert.equal(button('使用自己的 API（可选）').parentElement.hidden,true);
   assert.equal(dialog.querySelector('a[href="/?configure-ai=shared#arch"]'),null,'teacher is not sent to enter a shared key');
   assert.equal(dialog.querySelector('.ux-ai-server-help').hidden,true);
   assert.ok(dialog.textContent.includes('老师无需填写或获取 Key'));
   await w.fetch('http://127.0.0.1:8899/api/archloop/workspaces/ws/generate',{method:'POST'});
   assert.equal(network.at(-1).headers.get('X-ProjectMind-AI-Mode'),'shared');
 }else{
   assert.equal(dialog.querySelector('h2').textContent,'AI 服务');
   assert.equal(form.hidden,true,'shared API never shows a key entry even when the legacy backend reports canEdit');
   assert.equal(dialog.querySelector('.ux-ai-server-help').hidden,false);
   assert.equal(dialog.querySelector('.ux-ai-server-help').open,false);
   assert.equal(field('apiKey').value,'');assert.equal(form.querySelector('details').open,false);
   button('使用自己的 API（可选）').click();await settle();
   assert.equal(form.hidden,false);assert.equal(dialog.querySelector('.ux-ai-server-help').hidden,true);
   assert.equal(dialog.querySelector('.ux-ai-budget').hidden,false);
   assert.equal(field('protocol').value,'auto','unconfigured defaults to auto, not the resolved OpenAI protocol');
   button('填入千问平台兼容地址').click();
   assert.equal(field('baseUrl').value,'https://maas.qianwenapi.com/compatible-mode/v1');
   input('apiKey','SYNTHETIC-DOM-NOT-A-REAL-KEY');input('model','fixture-model');
   assert.equal(button('测试已保存的连接').disabled,true);
   const before=requests.length;button('使用平台 AI').click();await settle();
   assert.equal(requests.length,before,'cancelled mode switch retains unsaved fields');
   button('检查 API 是否可用').click();await settle();assert.equal(requests.length,before,'unsaved personal fields cannot trigger a check');
   assert.equal(field('apiKey').value,'SYNTHETIC-DOM-NOT-A-REAL-KEY');
   form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await settle();
   assert.equal(field('apiKey').value,'','saved credential is cleared, never returned');
   assert.equal(button('测试已保存的连接').disabled,false);
   await w.fetch('/api/archloop/workspaces/ws/generate',{method:'POST'});
   assert.equal(network.at(-1).headers.get('X-ProjectMind-AI-Mode'),'personal','expired session must never route to shared key');
   await w.fetch('/api/archloop/session');assert.equal(network.at(-1).headers,undefined,'renewal remains available');
   assert.equal(w.sessionStorage.getItem('projectmind:ai-mode'),'personal');
   button('测试已保存的连接').click();await settle();assert.ok(dialog.textContent.includes('49,985'));
   approve=true;button('使用平台 AI').click();await settle();
   assert.equal(form.hidden,true);assert.equal(field('apiKey').value,'');
   assert.equal(dialog.querySelector('.ux-ai-budget').hidden,true);assert.equal(dialog.querySelector('.ux-ai-budget').textContent,'');
   assert.ok(dialog.querySelector('.ux-connection-status').textContent.includes('平台 AI 已配置'));
   assert.equal(d.querySelector('a[href="/?demo=1#home"]').target,'_blank');
 }
 dom.window.close();
}
(async()=>{await scenario(false);await scenario(true);await scenario(false,true);console.log('PASS: platform AI state without shared key form, server setup help, personal API option, save/test/cleared key, dirty input retention, teacher shared routing and legacy configuration link opens status only.');})().catch(error=>{console.error(error);process.exitCode=1;});
