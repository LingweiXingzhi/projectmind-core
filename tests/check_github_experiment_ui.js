// Execute actual link UI helpers in a minimal DOM. Not a visual browser test.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.value='';this._text='';}append(...v){this.children.push(...v);}set textContent(v){this._text=String(v);this.children=[];}get textContent(){return this._text+this.children.map(x=>x.textContent).join('');}setAttribute(k,v){this.attributes[k]=v;}all(){return this.children.flatMap(e=>[e,...e.all()]);}}
const root=new Element('main'),document={createElement:t=>new Element(t),getElementById:id=>root.all().find(e=>e.id===id)};
const ctx=vm.createContext({document,console,Map,API:'/api/extensions/continuity_github',dirty:false,fetch:async()=>({ok:true,json:async()=>({references:[{url:'https://github.com/a/b/commit/'+'a'.repeat(40),note:'本机存在',content:'def real(): pass'}]})}),n:(tag,text,cls)=>{const e=new Element(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;},msg:()=>{}});
const html=fs.readFileSync('extensions/continuity_github/index.html','utf8');
const script=html.split('<script>')[1].split('</script>')[0];
vm.runInContext(script.slice(script.indexOf('function parseRefs('),script.indexOf('let pendingLogId=')),ctx);
ctx.root=root;
assert.deepEqual(JSON.parse(JSON.stringify(vm.runInContext("parseRefs('https://github.com/a/b/issues/1 | 依据\\n\\nhttps://github.com/a/b/pull/2')",ctx))),[{url:'https://github.com/a/b/issues/1',reason:'依据'},{url:'https://github.com/a/b/pull/2',reason:''}]);
vm.runInContext("refsEditor(root,[{url:'https://github.com/a/b/issues/1',reason:'先核查'}]);",ctx);
ctx.currentCodeUrl='https://github.com/a/b/commit/'+'b'.repeat(40);const quick=root.all().find(e=>e.tagName==='button'&&e.textContent==='关联当前代码提交');quick.onclick();quick.onclick();assert.equal((document.getElementById('github-references').value.match(/bbbbbbbb/g)||[]).length,5);const field=document.getElementById('github-references');assert.ok(field.value.includes('| 先核查'));field.oninput();assert.equal(ctx.dirty,true);
vm.runInContext("refPanel(root,[{url:'https://github.com/a/b/issues/1',reason:'<img src=x onerror=alert(1)>'},{url:'https://github.com/a/b/issues/1'}]);",ctx);
const anchors=root.all().filter(e=>e.tagName==='a');assert.equal(anchors.length,1);assert.equal(anchors[0].rel,'noopener noreferrer');assert.ok(root.textContent.includes('<img src=x'));
(async()=>{const box=await vm.runInContext("verifyRefs([{url:'https://github.com/a/b/commit/'+'a'.repeat(40)}])",ctx);assert.ok(box.textContent.includes('def real'));console.log('PASS: link parsing, editor roundtrip, dirty tracking, deduped safe text/anchors and local-evidence rendering.');})().catch(e=>{console.error(e);process.exitCode=1;});
