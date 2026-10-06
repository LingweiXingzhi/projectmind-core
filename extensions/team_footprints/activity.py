"""Read existing SQLite snapshots without creating or modifying business stores."""
import hashlib
import json
import os
import sqlite3
import subprocess
from contextlib import closing
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from extension_host import ExtensionError

SOURCES = [('worklog','projectmind-worklog','history','log'),
           ('continuity','projectmind-continuity','records','task'),
           ('github_worklog','projectmind-worklog-github','history','log'),
           ('github_continuity','projectmind-continuity-github','records','task')]
LABELS = {'log':'工作记录','checkpoint':'交出资料','progress':'工作进展','problem':'问题记录','resolved':'问题处理','session':'本次结束','complete':'任务完成记录'}
MAX_ROWS = 20000


def fail(message, status=400):
    raise ExtensionError(status, message)


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def member(name, origin):
    name = unicodedata.normalize('NFKC', str(name or '')).strip()[:100]
    key = ' '.join(name.split()).casefold()
    return {'id':'local:'+digest([origin,key])[:24], 'name':name or '未署名',
            'origin':origin, 'identityStatus':'self_declared_local_name'}


def timestamp(value, zone):
    try:
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(zone)
    except (ValueError,TypeError,AttributeError,OverflowError):
        return None


def documents(path, table):
    if not path.is_file():
        return [], False
    # Known fixed table names only. URI ro prohibits writes and creation.
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
            rows=[]; size=0; truncated=False
            for row in db.execute('SELECT document FROM '+table+' LIMIT ?', (MAX_ROWS+1,)):
                size+=len(row[0])
                if size>32*1024*1024:
                    truncated=True;break
                rows.append(row)
        out=[]
        for row in rows[:MAX_ROWS]:
            try:
                value=json.loads(row[0])
                if isinstance(value,dict): out.append(value)
            except (ValueError,TypeError):
                fail('已有记录包含无效数据，请检查来源库；没有修改它',503)
        return out,len(rows)>MAX_ROWS or truncated
    except sqlite3.Error:
        fail('记录库暂时不可读，请稍后刷新；没有修改它',503)


def common_dir(repo):
    # R35-D1: the explicit repo argument always wins. Inherited GIT_*
    # environment (GIT_DIR, GIT_WORK_TREE, GIT_COMMON_DIR, ...) is stripped
    # from the subprocess, so it can never silently redirect the record
    # lookup into another repository's stores — the same rule the worklog and
    # continuity stores already apply.
    env={key:value for key,value in os.environ.items() if not key.startswith('GIT_')}
    result=subprocess.run(['git','-C',str(repo),'rev-parse','--git-common-dir'],capture_output=True,text=True,timeout=5,env=env)
    if result.returncode: fail('无法定位当前项目记录目录')
    p=Path(result.stdout.strip())
    return (p if p.is_absolute() else Path(repo)/p).resolve()


def collect_activity(repo, timezone='Asia/Shanghai'):
    try: zone=ZoneInfo(timezone)
    except (ZoneInfoNotFoundError,ValueError,TypeError):
        # R48-06: ZoneInfo raises the same error for an unknown key AND for an
        # interpreter without any IANA database (Windows without the `tzdata`
        # package). Probe a key that must always exist to tell the deployment
        # gap apart from an invalid user choice — a missing database is not
        # "please pick a valid timezone".
        try: ZoneInfo('UTC')
        except (ZoneInfoNotFoundError,ValueError,TypeError):
            fail('本机缺少 IANA 时区数据库（部署缺口）：请安装 tzdata 后重试，'
                 '例如 python -m pip install tzdata',503)
        fail('请选择有效的 IANA 时区')
    root=common_dir(repo); events=[]; coverage=[]; ignored=0; skipped=0
    def add(source,document,kind,actor,origin,at,note='',evidence='',event_id=None):
        nonlocal skipped
        stamp=timestamp(at,zone)
        if not stamp: skipped+=1;return
        who=member(actor,origin)
        identity=event_id or digest([source,document.get('id'),kind,at,actor,note,evidence])
        events.append({'id':identity,'date':stamp.date().isoformat(),'at':stamp.isoformat(),
                       'member':who,'kind':kind,'label':LABELS[kind],
                       'source':source,'recordId':document.get('id',''),
                       'title':document.get('title') or document.get('task',{}).get('title','未命名任务'),
                       'note':str(note)[:4000],'evidence':str(evidence)[:2000],
                       'status':'ai_candidate' if origin=='ai' else 'participant_record_unverified',
                       'pageAvailable':not source.startswith('github_') or (Path(__file__).resolve().parent.parent/'continuity_github'/'extension.py').is_file(),
                       'pageUrl':'/ext/continuity_github' if source.startswith('github_') else '/ext/worklog' if source=='worklog' else '/ext/continuity'})
    for source,folder,table,kind in SOURCES:
        path=root/folder/'records.sqlite3'; rows,partial=documents(path,table)
        coverage.append({'source':source,'available':path.is_file(),'rowsRead':len(rows),'partial':partial})
        if kind=='log':
            previous={}
            for doc in sorted(rows,key=lambda r:(str(r.get('id','')),r.get('version',0))):
                content=digest([doc.get('title'),doc.get('body'),doc.get('category'),doc.get('attachment'),doc.get('references')])
                key=doc.get('id'); old=previous.get(key); previous[key]=content
                if old==content or (doc.get('sourceRecord') and doc.get('version')==1): ignored+=1;continue
                if not (str(doc.get('body','')).strip() or doc.get('attachment') or str(doc.get('title','')).strip()): ignored+=1;continue
                add(source,doc,'log',doc.get('author'),doc.get('origin','human'),doc.get('updatedAt'),doc.get('body',''),doc.get('codeRevision',''),digest([source,key,doc.get('version')]))
        else:
            for doc in rows:
                if 'importedFrom' not in doc and (doc.get('task',{}).get('stopPoint') or doc.get('task',{}).get('nextAction')):
                    add(source,doc,'checkpoint',doc.get('task',{}).get('owner'),'human',doc.get('createdAt'),doc.get('task',{}).get('stopPoint',''))
                # Imported history is deliberately separate and not counted as new local work.
                ignored+=len(doc.get('importedHistory',[])); blocked=False
                for e in doc.get('events',[]):
                    k=e.get('kind'); note=str(e.get('note','')).strip(); evidence=str(e.get('evidence','')).strip()
                    category=None
                    if k in ('block','question') and note: category='problem'
                    elif k in ('resume','claim') and blocked and note: category='resolved'
                    elif k=='note' and (note or evidence): category='progress'
                    elif k=='finish_session' and note and e.get('stopPoint') and e.get('nextAction'): category='session'
                    elif k=='complete' and note and evidence: category='complete'
                    if k=='block': blocked=True
                    elif k in ('resume','claim','complete'): blocked=False
                    if category:
                        add(source,doc,category,e.get('actor'),e.get('origin','human'),e.get('at'),note,evidence,digest(['event',source,doc.get('id'),e.get('kind'),e.get('actor'),e.get('origin','human'),e.get('at'),e.get('note'),e.get('evidence'),e.get('stopPoint'),e.get('nextAction')]))
                    else: ignored+=1
    unique={e['id']:e for e in events}
    return {'events':sorted(unique.values(),key=lambda e:e['at']),'coverage':coverage,
            'ignoredCount':ignored,'invalidTimestampCount':skipped,'timezone':timezone,
            'note':'只统计本机已有业务记录；名称自行声明，AI 内容仍为候选。导入历史不算新贡献；无变化保存和空状态点击不计。'}


def summarize(dataset, year, member_id=None, include_ai=False, details=False):
    if type(year) is not int or not 1970<=year<=2100: fail('年份须在 1970 至 2100 之间')
    events=dataset['events']; people={e['member']['id']:e['member'] for e in events}
    if member_id and member_id not in people: fail('记录中没有这位参与者',404)
    # One item/kind/person/day contributes one unit; no save-click multiplication.
    selected=[e for e in events if e['date'].startswith(str(year)+'-') and (not member_id or e['member']['id']==member_id) and (include_ai or e['member']['origin']!='ai')]
    groups={}; credited=set(); metrics={k:0 for k in LABELS}
    for e in selected:
        day=groups.setdefault(e['date'],{'date':e['date'],'count':0,'eventCount':0,'members':set(),'metrics':{k:0 for k in LABELS},'events':[]})
        key=(e['date'],e['source'],e['recordId'],e['kind'],e['member']['id'])
        e={**e,'counted':key not in credited};day['events'].append(e);day['eventCount']+=1;day['members'].add(e['member']['id'])
        if key not in credited:
            credited.add(key);day['count']+=1;day['metrics'][e['kind']]+=1;metrics[e['kind']]+=1
    days=[]; current=date(year,1,1)
    while current.year==year:
        value=groups.get(current.isoformat(),{'date':current.isoformat(),'count':0,'eventCount':0,'members':set(),'metrics':{k:0 for k in LABELS},'events':[]})
        days.append({**value,'events':value['events'] if details else [],'members':sorted(value['members'])});current+=timedelta(days=1)
    trend=[]
    for month in range(1,13):
        matching=[d for d in days if int(d['date'][5:7])==month]
        trend.append({'month':f'{year}-{month:02}','count':sum(d['count'] for d in matching),'activeDays':sum(d['count']>0 for d in matching)})
    return {'schemaVersion':1,'scope':'local_available_records','timezone':dataset['timezone'],'year':year,
            'memberId':member_id,'includeAi':include_ai,'members':sorted(people.values(),key=lambda p:(p['origin'],p['name'])),
            'days':days,'trend':trend,'metrics':metrics,'metricLabels':LABELS,
            'total':sum(metrics.values()),'activeDays':sum(d['count']>0 for d in days),
            'coverage':dataset['coverage'],'ignoredCount':dataset['ignoredCount'],'invalidTimestampCount':dataset['invalidTimestampCount'],
            'identityStatus':'self_declared_local_names','note':dataset['note'],
            'policy':{'format':'projectmind-footprints-policy-v1','dailyUnit':'record/kind/member/day','calendarTime':'actual saved/event timestamp converted to selected timezone','ranking':False,'importedHistoryCounted':False}}
