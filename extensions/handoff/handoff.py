"""Assemble existing evidence without generating architecture conclusions."""
from copy import deepcopy
import re

SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class HandoffError(ValueError):
    pass


def build_handoff(snapshot, source_locator, comparison=None, ai_candidates=None):
    if not isinstance(snapshot, dict) or not SHA.fullmatch(str(snapshot.get('revision', ''))):
        raise HandoffError('快照必须包含完整代码提交 SHA')
    revision = snapshot['revision']
    if not isinstance(source_locator, dict) or source_locator.get('kind') not in ('git_remote', 'local_path') or not isinstance(source_locator.get('value'), str) or not source_locator['value'].strip():
        raise HandoffError('请明确提供仓库地址或本地路径，不能仅用目录名代替')
    nodes = []
    known = {}
    unknowns = ['地图尚未标记核查适用版本；代码 SHA 只固定代码证据']
    for node in snapshot.get('nodes', []):
        paths = [e['path'] for e in node['evidence']]
        known[node['id']] = set(paths)
        nodes.append({'id': node['id'], 'title': node['title'], 'summary': node['summary'],
                      'entryPoint': node['entryPoint'], 'evidencePaths': paths,
                      'evidence': deepcopy(node['evidence'])})
        for e in node['evidence']:
            if not e.get('existsAtCommit'):
                unknowns.append(f"证据在此提交缺失或未核查：{e['path']}")
    if source_locator['kind'] == 'local_path':
        unknowns.append('本地路径在接收者电脑上可能不可用，请确认取得仓库的方法')
    changes, reviews = [], []
    if comparison is not None:
        if not isinstance(comparison, dict) or comparison.get('targetRevision') != revision or not SHA.fullmatch(str(comparison.get('baseRevision', ''))):
            raise HandoffError('比较结果的目标提交必须与快照一致，基准必须为完整 SHA')
        changes = deepcopy(comparison['changes'])
        reviews = deepcopy(comparison['reviewCandidates'])
        for item in reviews:
            if item.get('nodeId') not in known or not set(item.get('changedEvidencePaths', [])).issubset(known[item['nodeId']]):
                raise HandoffError('待复核节点或证据路径不属于此快照')
    else:
        unknowns.append('未提供提交比较，空变化列表不表示代码没有变化')
    candidates = [] if ai_candidates is None else ai_candidates
    if not isinstance(candidates, list):
        raise HandoffError('AI 候选必须是原样成功响应的列表')
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get('status') != 'ai_candidate' or candidate.get('targetRevision') != revision or candidate.get('nodeId') not in known:
            raise HandoffError('AI 候选状态、节点或目标提交不匹配')
        if comparison is None or candidate.get('baseRevision') != comparison['baseRevision']:
            raise HandoffError('AI 候选需要同一次提交比较')
        explanation = candidate.get('explanation')
        if not isinstance(explanation, dict) or not isinstance(explanation.get('unknowns'), list):
            raise HandoffError('AI 候选缺少解释或未知项')
        changed = candidate.get('changedEvidencePaths')
        cited = explanation.get('evidencePaths')
        matching = next((r['changedEvidencePaths'] for r in reviews if r['nodeId'] == candidate['nodeId']), [])
        if not isinstance(changed, list) or not isinstance(cited, list) or not set(changed).issubset(set(matching)) or not set(cited).issubset(set(changed)):
            raise HandoffError('AI 候选引用了此次比较之外的证据')
    result = {'status': 'handoff_draft', 'repository': snapshot['repository'],
              'sourceLocator': deepcopy(source_locator), 'codeRevision': revision,
              'mapRevision': 'UNKNOWN', 'mapOrigin': snapshot['mapOrigin'],
              'mapNote': snapshot.get('mapNote', ''), 'nodes': nodes,
              'edges': deepcopy(snapshot.get('edges', [])), 'changes': changes,
              'reviewCandidates': reviews, 'aiCandidates': deepcopy(candidates),
              'unknowns': unknowns, 'nextCheck': '取得指定仓库并检出代码 SHA；按待复核节点的证据路径检查变化，向团队核查地图适用版本'}
    if comparison is not None:
        result['baseRevision'] = comparison['baseRevision']
        result['comparisonNote'] = comparison.get('note', '')
    return result


def render_markdown(handoff):
    # JSON blocks preserve multiline/untrusted source text without upgrading it.
    import json
    lines = ['# ProjectMind 交接草稿', '', '未确认草稿；AI 候选不是团队决定。', '',
             '仓库来源类型：' + handoff['sourceLocator']['kind'],
             '代码提交：`' + handoff['codeRevision'] + '`', '地图核查状态：UNKNOWN', '']
    for title, value in [('仓库来源', handoff['sourceLocator']), ('功能与证据', handoff['nodes']),
                         ('关系（来自人工地图）', handoff['edges']), ('变化文件', handoff['changes']),
                         ('待复核节点', handoff['reviewCandidates']), ('AI 候选（保留原响应）', handoff['aiCandidates']),
                         ('未知项', handoff['unknowns']), ('下一步', handoff['nextCheck'])]:
        encoded = json.dumps(value, ensure_ascii=False, indent=2)
        fence = '`' * max(3, max((len(m.group()) + 1 for m in re.finditer(r'`+', encoded)), default=3))
        lines.extend(['## ' + title, '', fence + 'json', encoded, fence, ''])
    if 'baseRevision' in handoff:
        lines.extend(['比较基准：`' + handoff['baseRevision'] + '`', handoff.get('comparisonNote', '')])
    return '\n'.join(lines)
