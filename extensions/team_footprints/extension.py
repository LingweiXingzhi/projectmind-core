"""Public read-only extension API; collect/summarize also usable by a homepage."""
from datetime import datetime
from zoneinfo import ZoneInfo
from extensions.team_footprints.activity import collect_activity, summarize, fail
EXTENSION={'title':'团队足迹','description':'个人与团队的工作日历、趋势和接力；基于本机真实记录。'}


def handle(context, method, data):
    if method!='GET': fail('团队足迹只读，不修改日志或交接',405)
    action=data.get('action','summary'); zone=data.get('timezone','Asia/Shanghai')
    dataset=collect_activity(context.repo,zone)
    try: year=int(data.get('year',datetime.now(ZoneInfo(zone)).year))
    except (ValueError,TypeError): fail('年份无效')
    include=data.get('includeAi','false')
    if include not in ('true','false',True,False): fail('includeAi 须为 true 或 false')
    result=summarize(dataset,year,data.get('memberId') or None,include in ('true',True),details=action=='day')
    if action=='summary': return result
    if action=='relay':
        items=[e for e in dataset['events'] if e['recordId']==data.get('recordId') and e['source']==data.get('source') and (include in ('true',True) or e['member']['origin']!='ai')]
        return {'schemaVersion':1,'events':items[:300],'truncated':len(items)>300,'note':'本机这份任务的接力记录；导入历史未核实且不计入统计。'}
    if action=='day':
        day=next((d for d in result['days'] if d['date']==data.get('date')),None)
        if day is None: fail('日期不在所选年份内')
        total = len(day['events'])
        day = {**day, 'events': day['events'][-200:]}
        return {'schemaVersion':1,'day':day,'timezone':zone,'truncated':total>200,
                'totalEvents':total,'note':result['note']}
    fail('不支持的足迹操作')
