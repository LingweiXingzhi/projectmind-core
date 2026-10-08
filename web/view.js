// Workspace shell. Only existing read APIs are aggregated; source states are
// never promoted to confirmed architecture or fabricated collaboration data.
const VIEW_TITLES = {home:'项目总览',arch:'架构工作台',map:'项目地图',review:'变更审查',decisions:'关键决策',collab:'协同交接',worklog:'工作日志',explorer:'仓库浏览'};
let shellView='home';

const shellIcons={
 home:'<path d="m3 9 5-5 5 5v5H9v-4H7v4H3z"/>',
 arch:'<path d="m8 2 6 3.5v5L8 14l-6-3.5v-5zM2 5.5 8 9l6-3.5M8 9v5"/>',
 explorer:'<path d="M3 2h6l4 4v8H3zM9 2v4h4m-7 3-2 1 2 1m4-2 2 1-2 1"/>',
 review:'<path d="M2 5h11l-3-3m3 9H2l3 3m8-9-3 3M2 11l3-3"/>',
 decisions:'<rect x="3" y="2" width="10" height="12" rx="1"/><path d="m5 8 2 2 4-4"/>',
 collab:'<path d="M3 2h7v3M3 2v12h10v-4M7 7h7l-3-3m3 3-3 3"/>',
 worklog:'<rect x="3" y="2" width="10" height="12" rx="1"/><path d="M6 2v12m2-8h3m-3 3h3"/>',
 search:'<circle cx="6.5" cy="6.5" r="4"/><path d="m10 10 4 4"/>',
 settings:'<path d="m6 2 4 0 .5 2 2 .5 1 3-1.5 1.5.5 2-3 2-2-.8-2 .8-3-2 .5-2L1.5 8l1-3 2-.5z"/><circle cx="8" cy="8" r="2"/>',
 inspector:'<rect x="2" y="2" width="12" height="12" rx="1"/><path d="M10 2v12"/>',
 refresh:'<path d="M13 5A5.5 5.5 0 1 0 13 11M13 2v4H9"/>',
 share:'<path d="M9 2h5v5M14 2 7 9M6 3H2v11h11v-4"/>'
};
function shellIcon(name){return `<svg class="ui-icon" viewBox="0 0 16 16" aria-hidden="true">${shellIcons[name]||''}</svg>`;}
for(const nav of document.querySelectorAll('.top-nav [data-view]'))nav.querySelector('span').innerHTML=shellIcon(nav.dataset.view);
for(const [id,icon] of [['sidebar-search','search'],['settings-open','settings']])document.getElementById(id).querySelector('span').innerHTML=shellIcon(icon);
for(const [id,icon] of [['toggle-inspector','inspector'],['refresh-button','refresh'],['copy-link','share']])document.getElementById(id).innerHTML=shellIcon(icon);
document.querySelector('#command-open>span').innerHTML=shellIcon('search');

function activateView(name, push=true) {
  if (!VIEW_TITLES[name]) name='home';
  for(const section of document.querySelectorAll('.view')) section.hidden=section.id!==`view-${name}`;
  for(const item of document.querySelectorAll('.top-nav .nav-item')) {
    item.classList.toggle('active',item.dataset.view===name);
    item.setAttribute('aria-current',item.dataset.view===name?'page':'false');
  }
  document.getElementById('breadcrumb-current').textContent=VIEW_TITLES[name];
  shellView=name;document.body.dataset.view=name;
  if(push && location.hash!==`#${name}`) history.pushState({view:name},'',`#${name}`);
  if(['collab','worklog','decisions'].includes(name)) loadShellFrame(name);
  if(name==='home' && window.refreshOverview) window.refreshOverview(true);
  document.dispatchEvent(new CustomEvent('projectmind:view',{detail:name}));
}
function loadShellFrame(name) {
  if(document.body.dataset.mapMode!=='true') return;
  const frame=document.getElementById(name==='collab'?'collab-frame':`${name}-frame`);
  if(!frame || frame.getAttribute('src')) return;
  const active=document.querySelector('.collab-tab.active');
  frame.src=name==='collab' ? (active?.dataset.page||frame.dataset.src):frame.dataset.src;
}
for(const item of document.querySelectorAll('.top-nav .nav-item')) item.addEventListener('click',()=>activateView(item.dataset.view));
for(const tab of document.querySelectorAll('.collab-tab')) tab.addEventListener('click',()=>{
  for(const other of document.querySelectorAll('.collab-tab')) other.classList.toggle('active',other===tab);
  const frame=document.getElementById('collab-frame');
  if(frame && document.body.dataset.mapMode==='true') frame.src=tab.dataset.page;
});
document.addEventListener('click',event=>{const jump=event.target.closest('[data-jump]');if(jump)activateView(jump.dataset.jump);});
window.addEventListener('popstate',()=>activateView(location.hash.slice(1)||'home',false));
window.addEventListener('hashchange',()=>{const view=location.hash.slice(1);if(view!==shellView&&VIEW_TITLES[view])activateView(view,false);});
document.getElementById('nav-back').onclick=()=>history.back();
document.getElementById('nav-forward').onclick=()=>history.forward();
new MutationObserver(()=>{
  for(const name of ['collab','worklog','decisions']) {
    const frame=document.getElementById(name==='collab'?'collab-frame':`${name}-frame`);
    const note=document.querySelector(`#view-${name} .mode-note`);
    if(frame && document.body.dataset.mapMode==='false'){frame.removeAttribute('src');frame.hidden=true;}
    if(note)note.hidden=document.body.dataset.mapMode!=='false';
  }
  loadShellFrame(shellView);
}).observe(document.body,{attributes:true,attributeFilter:['data-map-mode']});
for(const copy of document.querySelectorAll('.compare-heading p,.intro-copy'))copy.parentElement.title=copy.textContent;
activateView(VIEW_TITLES[location.hash.slice(1)]?location.hash.slice(1):'home',false);

(() => {
  const $=id=>document.getElementById(id);
  let cache={snapshot:null,workspaces:[],entries:[],compare:null};
  let loading=null,loadedAt=0,workspaceState=null;
  const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const short=s=>s?String(s).slice(0,8):'—';
  function toast(message){$('shell-toast').textContent=message;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('shell-toast').textContent='',4200);}
  window.projectmindToast=toast;
  async function read(url){const r=await fetch(url);const d=await r.json();if(!r.ok)throw Error(typeof d.error==='string'?d.error:d.error?.message||`HTTP ${r.status}`);return d;}
  function empty(box,text){box.replaceChildren(make('p','activity-empty',text));}
  function row(title,meta,icon,click){const b=make('button','activity-row');b.append(make('span','activity-icon',icon),make('span','activity-name',title),make('span','activity-time',meta));b.onclick=click;return b;}
  function panel(count,title,lines,view){const b=make('button','attention-panel');const head=make('strong');head.append(make('b',null,count),make('span',null,title),make('span','panel-arrow','›'));b.append(head);lines.forEach(t=>b.append(make('p',null,t)));b.onclick=()=>activateView(view);return b;}
  async function overview(force=false){
    if(loading)return force?loading.then(()=>overview(true)):loading;
    if(!force&&Date.now()-loadedAt<15000)return;
    loading=(async()=>{
      const results=await Promise.allSettled([read('/api/snapshot'),read('/api/archloop/workspaces'),read('/api/extensions/worklog?action=list'),read('/api/ai-status')]);
      const [snap,spaces,logs,ai]=results;
      cache.snapshot=snap.status==='fulfilled'?snap.value:null;
      cache.workspaces=spaces.status==='fulfilled'?spaces.value.workspaces.slice().sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||''))):[];
      cache.entries=logs.status==='fulfilled'?logs.value.entries:[];
      let compare=null;
      if(cache.snapshot?.parentRevision){try{compare=await read(`/api/compare?base=${encodeURIComponent(cache.snapshot.parentRevision)}&target=${encodeURIComponent(cache.snapshot.revision)}`);}catch(e){/* Unknown remains unknown. */}}
      cache.compare=compare;
      const pending=compare?.reviewCandidates?.length;
      const open=cache.entries.filter(e=>e.category==='issue');
      const decisions=cache.entries.filter(e=>e.category==='decision');
      $('home-attention').replaceChildren(
        panel(pending===undefined?'—':pending,'架构证据待复核',pending===undefined?['尚未完成提交对比','打开变更审查选择审查范围']:pending?compare.reviewCandidates.slice(0,3).map(c=>cache.snapshot.nodes.find(n=>n.id===c.nodeId)?.title||c.nodeId):['本次比较未发现声明证据变化','这不代表架构已经过人审'],'review'),
        panel(spaces.status==='fulfilled'?cache.workspaces.length:'—','可继续的工作区',spaces.status==='fulfilled'?[cache.workspaces[0]?.title||'创建你的第一个架构工作区','草稿 · 点击继续工作']:['工作区服务暂不可用'],'arch'),
        panel(logs.status==='fulfilled'?open.length:'—','待解决的记录',logs.status==='fulfilled'?[open[0]?.title||'当前没有待解决记录',`${decisions.length} 条决策记录 · 尚未独立核实`]:['项目记录服务暂不可用'],'worklog')
      );
      $('home-recent').replaceChildren();
      cache.workspaces.slice(0,6).forEach(w=>$('home-recent').append(row(w.title||w.workspaceId,'草稿','⬡',()=>{activateView('arch');document.dispatchEvent(new CustomEvent('projectmind:open-workspace',{detail:w.workspaceId}));})));
      if(!cache.workspaces.length)empty($('home-recent'),spaces.status==='fulfilled'?'没有未完成工作区。创建后可在这里继续。':spaces.reason.message);
      $('home-activity').replaceChildren();
      cache.entries.slice().sort((a,b)=>String(b.updatedAt||b.date).localeCompare(String(a.updatedAt||a.date))).slice(0,6).forEach(e=>{
        const date=e.updatedAt||e.date;const time=date?String(date).slice(0,10):'项目记录';
        $('home-activity').append(row(e.title,time,e.category==='decision'?'◇':'▤',()=>{
          const name=e.category==='decision'?'decisions':'worklog';activateView(name);
          const frame=$(name+'-frame');if(frame&&document.body.dataset.mapMode==='true')frame.src=`/ext/worklog#${e.category}/${encodeURIComponent(e.id)}`;
        }));
      });
      if(!cache.entries.length)empty($('home-activity'),logs.status==='fulfilled'?'工作记录还没有开始。写下进展、决策和下一步。':'工作记录当前不可用。');
      const snapData=cache.snapshot;
      if(snapData){$('home-repo').textContent=snapData.repository;$('home-identity').textContent=`${snapData.branch} · ${short(snapData.revision)}`;$('shell-repo-branch').textContent=`Git · ${snapData.branch}`;$('status-branch').textContent=`Git · ${snapData.branch}`;$('status-commit').textContent=short(snapData.revision);$('status-commit').title=snapData.revision;}
      else {$('home-identity').textContent='Git 身份当前不可用';$('status-branch').textContent='Git 未读取';$('status-commit').textContent='—';}
      $('status-review').textContent=`待复核 ${pending===undefined?'—':pending}`;
      $('status-ai').textContent=ai.status==='fulfilled'?(ai.value.configured?'AI 已就绪':'AI 未配置'):'AI 状态未知';
      $('status-ai').title=ai.status==='fulfilled'?(ai.value.note||ai.value.model||''):ai.reason.message;
      $('attention-link').textContent=pending===undefined?'审查范围尚未确定':`${pending} 个节点证据待复核`;
      $('attention-link').dataset.jump='review';
      loadedAt=Date.now();
    })().catch(e=>toast(`状态读取失败：${e.message}`)).finally(()=>loading=null);
    return loading;
  }
  window.refreshOverview=overview;
  $('home-sync').onclick=()=>{$('refresh-button').click();};
  $('refresh-button').addEventListener('click',()=>{overview(true);});
  const hour=new Date().getHours();$('greeting').textContent=`${hour<12?'上午好':hour<18?'下午好':'晚上好'}，这是 ProjectMind`;
  document.addEventListener('projectmind:workspace',event=>{workspaceState=event.detail;$('status-model').textContent=`草稿 ${short(workspaceState.identity.draftRevision)}`;$('status-model').title=workspaceState.workspace.title;loadedAt=0;});
  // Search is read-only: navigation and existing nodes/workspaces only.
  const dialog=$('command-dialog');let commands=[],selection=0;
  function commandList(){
    const query=$('command-input').value.toLowerCase().trim();
    const words={home:'总览 首页',arch:'架构 工作台',map:'项目 地图 演示',review:'变化 审查 对比',decisions:'决策',collab:'协作 交接',worklog:'工作 日志 记录',explorer:'仓库 文件 代码'};
    const all=Object.entries(VIEW_TITLES).map(([id,label])=>({label,meta:words[id],run:()=>activateView(id)}));
    cache.workspaces.forEach(w=>all.push({label:w.title||w.workspaceId,meta:'工作区 · 草稿',run:()=>{activateView('arch');document.dispatchEvent(new CustomEvent('projectmind:open-workspace',{detail:w.workspaceId}));}}));
    (workspaceState?.draft?.graph?.nodes||[]).forEach(n=>all.push({label:n.title,meta:'架构节点',run:()=>{activateView('arch');document.dispatchEvent(new CustomEvent('projectmind:select-node',{detail:n.id}));}}));
    (cache.snapshot?.nodes||[]).forEach(n=>all.push({label:n.title,meta:'人工演示图节点',run:()=>{activateView('map');if(typeof showDetails==='function')showDetails(n.id);}}));
    commands=all.filter(c=>`${c.label} ${c.meta}`.toLowerCase().includes(query)).slice(0,25);selection=0;renderCommands();
  }
  function renderCommands(){const box=$('command-results');box.replaceChildren();commands.forEach((c,i)=>{const b=make('button',`command-result${i===selection?' selected':''}`);b.setAttribute('role','option');b.setAttribute('aria-selected',String(i===selection));b.append(make('span',null,c.label),make('small',null,c.meta));b.onclick=()=>{dialog.close();c.run();};box.append(b);});if(!commands.length)box.append(make('p','activity-empty','没有匹配的页面、工作区或节点。'));}
  function commandOpen(){if(!dialog.open)dialog.showModal();$('command-input').value='';commandList();$('command-input').focus();}
  $('command-open').onclick=$('sidebar-search').onclick=commandOpen;
  $('command-close').onclick=()=>dialog.close();$('command-input').oninput=commandList;
  dialog.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();selection=(selection+(e.key==='ArrowDown'?1:-1)+commands.length)%Math.max(commands.length,1);renderCommands();$('command-results').children[selection]?.scrollIntoView({block:'nearest'});}else if(e.key==='Enter'&&commands[selection]){e.preventDefault();dialog.close();commands[selection].run();}});
  $('copy-link').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);toast('页面链接已复制');}catch(e){toast('浏览器未允许复制，请复制地址栏链接');}};
  function inspectorToggle(){document.body.classList.toggle('inspector-hidden');$('inspector-toggle').checked=!document.body.classList.contains('inspector-hidden');savePrefs();}
  $('toggle-inspector').onclick=inspectorToggle;$('inspector-toggle').onchange=inspectorToggle;
  function savePrefs(){try{localStorage.setItem('projectmind:ui-prefs',JSON.stringify({compact:document.body.classList.contains('compact'),inspector:!document.body.classList.contains('inspector-hidden')}));}catch(e){toast('浏览器未允许保存布局偏好');}}
  try{const prefs=JSON.parse(localStorage.getItem('projectmind:ui-prefs')||'{}');document.body.classList.toggle('compact',!!prefs.compact);document.body.classList.toggle('inspector-hidden',prefs.inspector===false);$('compact-toggle').checked=!!prefs.compact;$('inspector-toggle').checked=prefs.inspector!==false;}catch(e){/* Default layout. */}
  $('compact-toggle').onchange=()=>{document.body.classList.toggle('compact',$('compact-toggle').checked);savePrefs();};
  $('settings-open').onclick=()=>$('settings-dialog').showModal();$('settings-close').onclick=()=>$('settings-dialog').close();
  function ask(){activateView('arch');document.body.classList.remove('inspector-hidden');const input=$('arch-correction-input');input?.focus();toast('选中架构节点后描述修改；纠正先生成预览，由你确认应用；来源以返回结果为准。');}
  $('ask-projectmind').onclick=ask;
  document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();commandOpen();}if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='j'){e.preventDefault();ask();}});
  function network(){const el=$('status-network');el.textContent=navigator.onLine?'◉ 本地':'○ 离线';el.classList.toggle('status-offline',!navigator.onLine);}
  window.addEventListener('offline',network);window.addEventListener('online',()=>{network();overview(true);});network();overview();
})();

