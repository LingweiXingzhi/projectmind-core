// Smoke-test scoped provenance rendering and untrusted claim text handling.
import fs from 'node:fs';
import vm from 'node:vm';
const html = fs.readFileSync(new URL('../../extensions/context_authority/index.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
class Node {
  constructor(tag) { this.tag=tag; this.children=[]; this.textContent=''; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; }
  set innerHTML(_) { throw new Error('Untrusted data must never enter innerHTML'); }
}
const nodes = {out:new Node('div'),hash:new Node('span')};
const attack='<img src=x onerror="globalThis.compromised=true">';
const state={registry_hash:'sha256:test',current:{},current_by_scope:[{key:attack,scope:'one',value:attack,type:'CONTRACT',claim_ids:['claim-a'],source:{kind:'doc',ref:attack}},{key:'contract.x',scope:'two',value:'second',type:'CONTRACT',claim_ids:['claim-b'],source:{kind:'doc',ref:'second'}}],conflicts:[],registry_problems:[{kind:'BROKEN_SUPERSEDES',resolution:'HUMAN_REQUIRED',detail:attack}],stale:[],proposals:[],research:[],historical:[],verification_unavailable:[]};
const context = vm.createContext({document:{getElementById:id=>nodes[id],createElement:tag=>new Node(tag)},fetch:async()=>({ok:true,json:async()=>state})});
vm.runInContext(script,context);
await vm.runInContext("load('state')",context);
function text(node) { return node.textContent+node.children.map(text).join('\n'); }
if (!text(nodes.out).includes(attack) || !text(nodes.out).includes('contract.x / two')) throw new Error('Scoped rows/evidence were lost');
if (context.compromised) throw new Error('Claim text executed');
await vm.runInContext("load('claims')",context);
await vm.runInContext("load('conflicts')",context);
console.log('PASS: scoped/evidence/registry diagnostics render as text; no innerHTML or claim execution');
