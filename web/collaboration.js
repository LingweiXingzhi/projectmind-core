// Shared-server collaboration uses the existing workspace/version/record/task APIs.
// It does not load map-only extensions or grant approval to participant records.
(async () => {
  // auth-client.js resolves the session asynchronously and gates fetch on it.
  // Wait for that gate before deciding whether this is the shared server UI.
  if (!window.projectmindSession) {
    if (!document.querySelector('script[src="/auth-client.js"]')) return;
    try { const response=await fetch('/api/auth/session');if(!response.ok||!window.projectmindSession)return; }
    catch { return; }
  }
  const $=id=>document.getElementById(id), root=$('collab-shared');
  if (!root) return;
  root.hidden=false;document.body.dataset.sharedCollab='true';const frame=$('collab-frame');if(frame)frame.hidden=true;
  const note=document.querySelector('#view-collab .needs-map-note');if(note)note.hidden=true;
  let envelope=null, sequence=0, contextSequence=0, exporting=false, preparing=false;
  const make=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
  const base=()=>'/api/archloop/workspaces/'+encodeURIComponent(envelope.workspace.workspaceId);
  function status(text){$('collab-status').textContent=text;}
  async function read(path){const response=await fetch(path),data=await response.json();if(!response.ok)throw Error(`${data.error?.code||response.status}：${data.error?.message||'读取失败'}`);return data;}
  function showTab(page){
    for(const tab of document.querySelectorAll('.collab-tab')){const selected=tab.dataset.page===page;tab.classList.toggle('active',selected);tab.setAttribute('aria-selected',String(selected));}
    for(const [id,url] of [['collab-package-panel','/ext/handoff'],['collab-context-panel','/ext/continuity'],['collab-records-panel','/ext/worklog']])$(id).hidden=page!==url;
  }
  for(const tab of document.querySelectorAll('.collab-tab'))tab.addEventListener('click',()=>showTab(tab.dataset.page));
  function invalidateContext(){++contextSequence;$('collab-context-text').value='';$('collab-context-copy').disabled=$('collab-context-download').disabled=true;}
  function opened(value){
    const old=envelope;envelope=value;const choice=$('collab-workspace'),id=value.workspace.workspaceId;
    if(![...choice.options].some(option=>option.value===id)){const option=make('option',value.workspace.title||id);option.value=id;choice.append(option);}choice.value=id;
    if(!old||old.workspace.workspaceId!==id||old.identity.draftRevision!==value.identity.draftRevision||old.lastPublish?.mapRevision!==value.lastPublish?.mapRevision||old.lastPublish?.mapSourceRevision!==value.lastPublish?.mapSourceRevision){invalidateContext();$('collab-package-result').replaceChildren();}
    $('collab-export').disabled=exporting||!value.lastPublish;
    $('collab-context-refresh').disabled=preparing;
    status(value.lastPublish?`当前项目：${value.workspace.title}。先生成交接包，或补充工作记录与下一步。`:`当前项目：${value.workspace.title}。尚未发布确认版本；可先记录进展、整理草稿上下文，发布后再导出版本。`);
  }
  async function load(id){
    const current=++sequence;const spaces=await read('/api/archloop/workspaces');if(current!==sequence)return;
    const selected=id||envelope?.workspace.workspaceId||spaces.workspaces[0]?.workspaceId;
    const choice=$('collab-workspace');choice.replaceChildren();for(const item of spaces.workspaces){const option=make('option',item.title||item.workspaceId);option.value=item.workspaceId;choice.append(option);}
    if(!selected){envelope=null;$('collab-export').disabled=$('collab-context-refresh').disabled=true;invalidateContext();status('先在架构工作台创建或打开项目，再开始交接。');return;}
    const value=await read('/api/archloop/workspaces/'+encodeURIComponent(selected));if(current!==sequence)return;opened(value);
  }
  $('collab-workspace').onchange=()=>{const id=$('collab-workspace').value;invalidateContext();$('collab-export').disabled=true;load(id).then(()=>document.dispatchEvent(new CustomEvent('projectmind:open-workspace',{detail:id}))).catch(error=>status(error.message));};
  $('collab-refresh').onclick=()=>load().catch(error=>status(error.message));
  $('collab-open-workspace').onclick=()=>{activateView('arch');if(envelope)document.dispatchEvent(new CustomEvent('projectmind:open-workspace',{detail:envelope.workspace.workspaceId}));};
  document.addEventListener('projectmind:workspace',event=>{if(event.detail?.workspace?.workspaceId){++sequence;opened(event.detail);}});
  document.addEventListener('projectmind:begin-entry',()=>{++sequence;envelope=null;invalidateContext();$('collab-export').disabled=$('collab-context-refresh').disabled=true;status('请先创建或打开要交接的项目。');});
  $('collab-export').onclick=async()=>{
    if(!envelope||!envelope.lastPublish||exporting)return;
    const id=envelope.workspace.workspaceId,revision=envelope.identity.draftRevision;exporting=true;$('collab-export').disabled=true;
    try{const packet=await read(base()+'/handover');if(envelope?.workspace.workspaceId!==id||envelope.identity.draftRevision!==revision)return;
      const version=packet.versionEnvelope?.version||packet,provenance=packet.versionEnvelope?.provenance||packet;
      const link=make('a','下载同版交接包 JSON');link.className='button primary';link.download=`handover-${version.mapId}-${String(version.mapRevision).slice(7,19)}.json`;
      link.href=`/api/archloop/workspaces/${encodeURIComponent(id)}/handover?`+new URLSearchParams({download:'1',mapRevision:version.mapRevision,mapSourceRevision:provenance.mapSourceRevision});
      const box=$('collab-package-result');box.replaceChildren(make('p',`已发布图版本：${version.mapRevision}`));
      if(packet.sources?.architecture===null)box.append(make('p','可下载用于阅读交接；跨电脑来源核验尚未完成。'));
      box.append(link);status('交接包已生成，点击“下载同版交接包 JSON”保存，再交给队友。');
    }catch(error){status('导出失败：'+error.message);}finally{exporting=false;$('collab-export').disabled=!envelope?.lastPublish;}
  };
  const states={queued:'待接手',received:'已接手',in_progress:'实施中',verification_pending:'待核验',verified:'已核验',rejected:'已拒绝'};
  $('collab-context-refresh').onclick=async()=>{
    if(!envelope||preparing)return;
    const id=envelope.workspace.workspaceId,current=++contextSequence,path=base();preparing=true;$('collab-context-refresh').disabled=true;
    $('collab-context-copy').disabled=$('collab-context-download').disabled=true;
    try{
      const latest=await read(path);if(envelope?.workspace.workspaceId!==id||current!==contextSequence)return;
      const published=latest.lastPublish;const results=await Promise.allSettled([
        published?read(path+'/versions/'+encodeURIComponent(published.mapRevision)):Promise.resolve(null),
        read(path+'/records'),read(path+'/fix-tasks')]);
      if(envelope?.workspace.workspaceId!==id||current!==contextSequence)return;
      const [version,records,tasks]=results,confirmed=version.status==='fulfilled'?version.value:null;
      const graph=confirmed?.graph||(!published?latest.draft?.graph:null);
      const lines=[`# ${latest.workspace.title} · 工作交接`,'',`工作区：${id}`,`项目入口：${location.origin}/#collab`,
        `项目类型：${latest.workspace.context==='planning'?'规划项目，尚无代码':'已有项目'}`,
        `已发布图版本：${published?.mapRevision||'未发布'}`,`架构来源提交：${confirmed?.provenance?.mapSourceRevision||'未核对'}`,
        `代码版本：${published?(confirmed?confirmed.version.codeRevision||'尚未关联代码':'未核对'):latest.identity.codeRevision||'尚未关联代码'}`,
        '','## 功能理解',published?'以下内容来自已发布版本；确认范围与限制以版本记录为准。':'以下内容为当前草稿，未经发布确认。'];
      if(published&&!confirmed)lines.push('已发布版本读取失败，功能内容保持未知。');
      for(const node of (graph?.nodes||[]).slice(0,50))lines.push(`- ${node.title}：${node.summary||''}`);
      if(confirmed?.limits?.length)lines.push('','版本限制：',...confirmed.limits.map(value=>'- '+value));
      lines.push('','## 未关闭任务');
      if(tasks.status==='fulfilled'){const open=tasks.value.tasks.filter(task=>task.status!=='verified'&&task.status!=='rejected');if(!open.length)lines.push('当前没有未关闭的治理任务；不代表实现已经验证。');
        for(const task of open.slice(0,50))lines.push(`- ${task.id||task.taskId} · ${states[task.status]||task.status}：${task.deviation||task.observation||''}；验收：${task.acceptance||'按任务内容核对'}`);
      }else lines.push('任务状态读取失败，保持未知。');
      lines.push('','## 工作记录与下一步（参与者记录 / AI 候选，未经独立核实）');
      if(records.status==='fulfilled'){if(!records.value.entries.length)lines.push('还没有工作记录；请在“工作日志”中补充进展、待办与下一步。');
        for(const entry of records.value.entries.slice().sort((a,b)=>String(b.updatedAt||b.date).localeCompare(String(a.updatedAt||a.date))).slice(0,10))lines.push(`### ${entry.title}（${entry.origin==='ai'?'AI 候选':'参与者记录'} · ${entry.author}）`,entry.body||'','');
      }else lines.push('工作记录读取失败，保持未知。');
      lines.push('','下一位：打开同一网站，选择上述项目；阅读确认版本，核对未关闭任务，再在工作日志中记录接续结果。','本文件不授予批准权，不证明运行行为，不读取服务端 API 配置。');
      $('collab-context-text').value=lines.join('\n');$('collab-context-copy').disabled=$('collab-context-download').disabled=false;
      status('上下文已整理。请检查下一步是否完整，再复制或下载交给接续者。');
    }catch(error){status('整理失败：'+error.message);}finally{preparing=false;$('collab-context-refresh').disabled=!envelope;}
  };
  $('collab-context-copy').onclick=async()=>{try{await navigator.clipboard.writeText($('collab-context-text').value);status('上下文已复制，可粘贴给接续者。');}catch(error){$('collab-context-text').focus();$('collab-context-text').select();status('浏览器未允许自动复制，文本已选中，请手动复制。');}};
  $('collab-context-download').onclick=()=>{if(!envelope||!$('collab-context-text').value)return;const url=URL.createObjectURL(new Blob([$('collab-context-text').value],{type:'text/markdown;charset=utf-8'})),link=make('a');link.href=url;link.download=`projectmind-context-${envelope.workspace.workspaceId}.md`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  showTab(document.querySelector('.collab-tab.active')?.dataset.page||'/ext/handoff');
  load().catch(error=>status('读取项目失败：'+error.message));
})();
