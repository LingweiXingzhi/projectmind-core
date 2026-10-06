// Actual calendar/chart rendering under a minimal DOM; not visual acceptance.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.value='';this._text='';this.classes=new Set();this.classList={add:c=>this.classes.add(c),remove:c=>this.classes.delete(c),toggle:(c,on)=>on?this.classes.add(c):this.classes.delete(c)};}set textContent(v){this._text=String(v);this.children=[];}get textContent(){return this._text+this.children.map(x=>x.textContent).join('');}append(...v){this.children.push(...v);}replaceChildren(...v){this._text='';this.children=[...v];}setAttribute(k,v){this.attributes[k]=v;}all(){return this.children.flatMap(x=>[x,...x.all()]);}}
const elements=new Map(['member','year','timezone','ai','cards','calendar-title','calendar-note','months','calendar','trend','people','coverage'].map(id=>[id,new Element('div')]));
const document={createElement:t=>new Element(t),createElementNS:(ns,t)=>new Element(t),getElementById:id=>elements.get(id)};
const ctx=vm.createContext({document,console,Date,Intl,Map,setTimeout,clearTimeout});
const html=fs.readFileSync('extensions/team_footprints/index.html','utf8');const script=html.split('<script>')[1].split('</script>')[0];vm.runInContext(script.slice(0,script.indexOf("$('calendar-view').onclick=")),ctx);
assert.deepEqual([0,1,2,4,7].map(x=>vm.runInContext('intensity('+x+')',ctx)),[0,1,2,3,4]);
const start=new Date('2024-01-01T00:00:00Z');const days=Array.from({length:366},(_,i)=>({date:new Date(+start+i*86400000).toISOString().slice(0,10),count:i===0?2:0}));
ctx.input={year:2024,members:[{id:'p',name:'<script>alert(1)</script>',origin:'human'}],memberId:null,total:2,activeDays:1,metrics:{log:1,session:1,complete:0},days,timezone:'Asia/Shanghai',trend:Array.from({length:12},(_,i)=>({month:'2024-'+String(i+1).padStart(2,'0'),count:i===0?2:0,activeDays:i===0?1:0})),coverage:[{available:false,partial:false}],ignoredCount:0,invalidTimestampCount:0};
vm.runInContext('dataset=input;render()',ctx);
const buttons=elements.get('calendar').all().filter(e=>e.tagName==='button');assert.equal(buttons.length,366);assert.equal(buttons[0].dataset.level,2);assert.equal(buttons[0].attributes['aria-label'],'2024-01-01 · 2 项活动');assert.ok(elements.get('people').textContent.includes('<script>'));
const svg=elements.get('trend').children[0];assert.equal(svg.tagName,'svg');assert.equal(svg.all().filter(e=>e.tagName==='circle').length,12);assert.ok(!svg.all().some(e=>Object.values(e.attributes).some(v=>String(v).includes('NaN'))));
ctx.input.trend.forEach(t=>t.count=0);vm.runInContext('renderTrend(input)',ctx);assert.ok(!elements.get('trend').children[0].all().some(e=>Object.values(e.attributes).some(v=>String(v).includes('NaN'))));
console.log('PASS: intensity levels, leap-year calendar, accessible day labels, untrusted names as text, 12-point trend and zero-safe chart.');
