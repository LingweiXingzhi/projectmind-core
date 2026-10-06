// Node-only checks of the shipped UI logic; this is not a browser/visual test.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.style={};this.attributes={};this._text='';this.checked=false;this.hidden=false;this.disabled=false;this.value='';}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  setAttribute(key,value){this.attributes[key]=value;}
  all(){return this.children.flatMap(c=>[c,...c.all()]);}
  matches(selector){
    let checked=false;if(selector.endsWith(':checked')){checked=true;selector=selector.slice(0,-8);}
    if(checked&&!this.checked)return false;
    const attr=selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
    if(attr){const key=attr[1];const value=key.startsWith('data-')?this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]:this[key]??this.attributes[key];return attr[2]===undefined?value!==undefined:String(value)===attr[2];}
    return this.tagName===selector;
  }
  querySelectorAll(selector){return this.all().filter(e=>selector.split(',').some(s=>e.matches(s)));}
}
const root=new Element('body');
for(const id of ['status','actor','origin','main']){const e=new Element('div');e.id=id;e.value=id==='actor'?'UITest':'human';root.append(e);}
const document={createElement:tag=>new Element(tag),getElementById:id=>root.all().find(e=>e.id===id),querySelectorAll:s=>root.querySelectorAll(s),querySelector:s=>root.querySelectorAll(s)[0]};
let clock=0,nextId=0;const timers=new Map();
const context=vm.createContext({document,console,URL,TextEncoder,Blob,confirm:()=>true,
  setTimeout:(fn,delay)=>{const id=++nextId;timers.set(id,{fn,at:clock+delay});return id;},clearTimeout:id=>timers.delete(id)});
const html=fs.readFileSync(path.join(__dirname,'../extensions/continuity/index.html'),'utf8');
const code=html.split('<script>')[1].split('</script>')[0];
vm.runInContext(code.slice(0,code.indexOf("$('new').onclick=")),context);
const run=code=>vm.runInContext(code,context);
function advance(ms){clock+=ms;for(const [id,t] of [...timers])if(t.at<=clock){timers.delete(id);t.fn();}}
function reset(record,action){context.inputRecord=record;context.inputAction=action;run("selected=inputRecord;workAction=inputAction;dirty=false;busy=false;$('main').replaceChildren();");}
function record(state='receiving'){return {id:'a'.repeat(32),version:1,state,task:{stopPoint:'旧停止位置',nextAction:'旧第一步'},checklist:[{id:'check',text:'运行返回值验证',state:'pending'}],events:[]};}
async function main(){
  run("msg('第一条')");advance(4999);assert.equal(document.getElementById('status').textContent,'第一条');advance(1);assert.equal(document.getElementById('status').textContent,'');
  run("msg('旧提示')");advance(2500);run("msg('新提示')");advance(2500);assert.equal(document.getElementById('status').textContent,'新提示');advance(2500);assert.equal(document.getElementById('status').textContent,'');
  run("get=async()=>({sourceState:'unknown',revisionState:'missing',mapState:'unknown',workspace:{files:[]},logs:[]});refreshList=async()=>{};render=()=>{};");
  reset(record(),'claim');run("receive($('main'))");
  const labels=document.getElementById('main').all().filter(e=>e.tagName==='button').map(e=>e.textContent);
  for(const label of ['接手','记录进展','记录问题','结束'])assert.ok(labels.includes(label));
  assert.ok(!labels.includes('开始接手检查')&&!labels.includes('记录阻塞'));
  run("post=async(action,payload)=>{savedPayload=payload;return {record:{...selected,state:'active',version:2}};}");
  await run('saveEvent()');assert.equal(context.savedPayload.kind,'claim');assert.deepEqual(Object.values(context.savedPayload.review),[false,false,false,false]);
  reset(record('active'),'problem');run("receive($('main'))");document.getElementById('event-note').value='需要确认参数';await run('saveEvent()');assert.equal(context.savedPayload.kind,'question');
  reset(record('active'),'problem');run("receive($('main'))");document.getElementById('event-note').value='环境缺失';document.getElementById('problem-blocks').checked=true;await run('saveEvent()');assert.equal(context.savedPayload.kind,'block');
  reset(record('active'),'end');run("receive($('main'))");
  assert.equal(document.getElementById('completion-fields').hidden,true);
  const radios=document.querySelectorAll('[name="end-mode"]');radios[0].checked=false;radios[1].checked=true;
  const modes=document.getElementById('main').all().find(e=>e.children.some(c=>c.children.includes(radios[1])));modes.onchange();
  assert.equal(document.getElementById('session-fields').hidden,true);assert.equal(document.getElementById('completion-fields').hidden,false);
  assert.ok(document.getElementById('completion-fields').textContent.includes('运行返回值验证'));
  document.getElementById('event-note').value='已完成';document.getElementById('event-evidence').value='运行记录';
  run("post=async()=>{throw Error('任务尚有未完成项：运行返回值验证');}");await run('saveEvent()');advance(5000);
  assert.equal(document.getElementById('status').textContent,'');assert.equal(document.getElementById('work-error').hidden,false);assert.equal(document.getElementById('event-note').value,'已完成');
  reset(record('active'),'end');run("receive($('main'));post=async(action,payload)=>{savedPayload=payload;return {record:{...selected,state:'ready',version:2}};}");
  document.getElementById('event-note').value='环境检查已做，测试明天继续';document.getElementById('session-stop').value='未运行返回值验证';document.getElementById('session-next').value='先运行测试';await run('saveEvent()');
  assert.equal(context.savedPayload.kind,'finish_session');assert.equal(context.savedPayload.nextAction,'先运行测试');
  reset(record('active'),'note');run("receive($('main'))");await run('saveEvent()');assert.equal(document.getElementById('work-error').hidden,false);
  console.log('PASS: toast expiry/reset, four actions, optional checks, unified problem impact, end modes, named pending items, retained errors/drafts, session payload, empty progress rejection.');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
