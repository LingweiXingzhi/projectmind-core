// Shared participant records. No record category or AI text grants model approval.
(() => {
  const panels = [...document.querySelectorAll('[data-shared-records]')];
  if (!panels.length) return;
  const make = (tag, text) => {const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
  async function api(path, body) {
    const response=await fetch(path, body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
    const result=await response.json();
    if(!response.ok)throw Error(`${result.error?.code||response.status}：${result.error?.message||'读取失败'}`);
    return result;
  }
  const controllers=[];
  function controller(panel) {
    let envelope=null, entries=[], editing=null, formContext=null, sequence=0, busy=false, initialValues=null, fingerprint='';
    const identityKey=e=>JSON.stringify([e?.workspace?.workspaceId,e?.identity?.mapRevision,e?.identity?.draftRevision]);
    const choice=make('select');choice.setAttribute('aria-label','工作记录所属工作区');
    const status=make('p','读取共享工作记录…');status.setAttribute('role','status');
    const list=make('div'),formBox=make('div');
    const base=()=>'/api/archloop/workspaces/'+encodeURIComponent(envelope.workspace.workspaceId);
    function button(label, action) {const b=make('button',label);b.type='button';b.className='button ghost';b.onclick=action;return b;}
    const controls=make('div');controls.className='compare-controls';
    controls.append(choice,button('刷新记录',()=>load().catch(error=>status.textContent=error.message)),
      button('新建记录',()=>drawForm()),button('下载本工作区记录',async()=>{
        if(!envelope)return;
        try {const packet=await api(base()+'/records/export');
          const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json'}));
          const link=make('a');link.href=url;link.download='workspace-records.json';link.click();URL.revokeObjectURL(url);
        }catch(error){status.textContent=error.message;}
      }));
    panel.append(make('p','参与者记录 / AI 候选，尚未独立核实；决策分类不代表团队批准。附件导入尚未接通。'),controls,status,list,formBox);
    async function load(id, entry) {
      const current=++sequence;
      const spaces=await api('/api/archloop/workspaces');
      if(current!==sequence)return;
      const selected=id||envelope?.workspace.workspaceId||spaces.workspaces[0]?.workspaceId;
      choice.replaceChildren();
      for(const row of spaces.workspaces){const option=make('option',row.title||row.workspaceId);option.value=row.workspaceId;choice.append(option);}
      if(!selected){envelope=null;formBox.replaceChildren();list.replaceChildren();status.textContent='先创建架构工作区，再开始工作记录。';return;}
      choice.value=selected;
      const opened=await api('/api/archloop/workspaces/'+encodeURIComponent(selected));
      const data=await api('/api/archloop/workspaces/'+encodeURIComponent(selected)+'/records');
      if(current!==sequence)return;
      const changed=envelope?.workspace.workspaceId!==selected;
      envelope=opened;entries=data.entries;
      fingerprint=identityKey(opened);
      status.textContent=`${data.total} 条记录${data.truncated?'，当前仅展示前 200 条':''} · 登录账户 ${window.projectmindSession.actor}`;
      drawList();
      if(changed||entry)drawForm(entry||null);
      else if(!formBox.children.length)drawForm();
    }
    function drawList(){
      list.replaceChildren();const shown=panel.dataset.sharedRecords==='decision'?entries.filter(e=>e.category==='decision'):entries;
      if(!shown.length)list.append(make('p','此分类还没有记录。'));
      for(const entry of shown){const card=make('article');
        card.append(button(entry.title,()=>drawForm(entry)),make('p',`${entry.date} · ${entry.author} · ${entry.status==='ai_candidate'?'AI 候选':'参与者记录'} · v${entry.version}`),make('p',entry.body));
        card.append(button('查看历史',async()=>{try{const result=await api(base()+'/records/'+encodeURIComponent(entry.id)+'/history');
          const previous=card.querySelector('pre');if(previous)previous.remove();
          card.append(make('pre',JSON.stringify({history:result.history,total:result.total,truncated:result.truncated},null,2)));
        }catch(error){status.textContent=error.message;}}));list.append(card);
      }
    }
    function drawForm(entry=null){
      if(!envelope)return;
      editing=entry;formContext={...envelope.identity};formBox.replaceChildren();
      const form=make('form');form.dataset.recordForm='';
      form.append(make('h3',entry?'编辑记录':'新建记录'));
      const values={category:entry?.category||(panel.dataset.sharedRecords==='decision'?'decision':'daily'),
        origin:entry?.origin||'human',date:entry?.date||new Date().toISOString().slice(0,10),title:entry?.title||'',body:entry?.body||''};
      initialValues={...values};
      for(const [name,label] of [['category','分类'],['origin','内容来源'],['date','日期'],['title','标题'],['body','正文']]){
        const field=make(['category','origin'].includes(name)?'select':name==='body'?'textarea':'input');field.name=name;field.required=true;
        if(name==='category')for(const [value,text] of Object.entries({daily:'每日日志',decision:'决策记录（未批准）',goal:'当前目标',issue:'待解决事项'})){const option=make('option',text);option.value=value;field.append(option);}
        if(name==='origin')for(const [value,text] of [['human','参与者记录'],['ai','AI 候选']]){const option=make('option',text);option.value=value;field.append(option);}
        if(name==='date')field.type='date';if(name==='title')field.maxLength=200;if(name==='body')field.maxLength=15000;
        field.value=values[name];const wrapper=make('label',label);wrapper.append(field);form.append(wrapper);
      }
      form.append(make('p',`作者：${window.projectmindSession.actor}（登录账户）；图版本 ${formContext.mapRevision||'未生成'}；代码 ${formContext.codeRevision||'未关联'}`));
      const submit=make('button','保存记录');submit.type='submit';submit.className='button primary';form.append(submit);
      form.onsubmit=async event=>{
        event.preventDefault();if(busy||!form.reportValidity())return;busy=true;submit.disabled=true;choice.disabled=true;
        const data=Object.fromEntries(new FormData(form));
        Object.assign(data,{expectedMapRevision:formContext.mapRevision,expectedDraftRevision:formContext.draftRevision});
        if(editing)Object.assign(data,{id:editing.id,expectedVersion:editing.version});
        try {const result=await api(base()+'/records',data);await load();drawForm(result.entry);
          status.textContent='记录已保存；仍为参与者记录或 AI 候选，尚未独立核实。';window.refreshOverview?.(true);
        }catch(error){status.textContent=error.message+'。输入已保留；刷新后点击记录标题载入最新版，新建记录可复制文本后重新打开。';}
        finally{busy=false;choice.disabled=false;if(submit.isConnected)submit.disabled=false;}
      };formBox.append(form);
    }
    choice.onchange=()=>load(choice.value).catch(error=>status.textContent=error.message);
    function workspaceEvent(opened){
      if(identityKey(opened)===fingerprint)return;
      if(busy&&envelope?.workspace.workspaceId!==opened.workspace.workspaceId){status.textContent='正在保存当前工作区记录，请稍后切换。';return;}
      const form=formBox.querySelector('form');
      if(envelope?.workspace.workspaceId!==opened.workspace.workspaceId&&form&&initialValues&&
          Object.entries(initialValues).some(([name,value])=>form.elements[name].value!==value)){
        status.textContent='当前未保存输入已保留。请先保存或复制，再选择其他工作区。';return;
      }
      load(opened.workspace.workspaceId).catch(error=>status.textContent=error.message);
    }
    return {load,panel,workspaceEvent};
  }
  async function start(){
    try{await api('/api/archloop/records');if(!window.projectmindSession)return;
      document.body.dataset.sharedRecords='true';
      for(const panel of panels){panel.hidden=false;const view=panel.closest('.view');view.querySelector('iframe').hidden=true;view.querySelector('.mode-note').hidden=true;controllers.push(controller(panel));}
      await Promise.all(controllers.map(c=>c.load()));window.refreshOverview?.(true);
    }catch(error){if(window.projectmindSession)for(const panel of panels){panel.hidden=false;panel.append(make('p','共享记录不可用：'+error.message));}}
  }
  document.addEventListener('projectmind:workspace',event=>{if(event.detail?.workspace?.workspaceId)for(const c of controllers)c.workspaceEvent(event.detail);});
  document.addEventListener('projectmind:open-record',event=>{for(const c of controllers)c.load(event.detail.workspaceId,event.detail).catch(error=>{c.panel.querySelector('[role=status]').textContent=error.message;});});
  start();
})();
