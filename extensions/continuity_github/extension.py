"""HTTP API for the continuity service; old extension APIs stay unchanged."""
from extensions.continuity_github.inspection import capture, inspect, read_evidence, remotes
from extensions.continuity_github.store import repository_store
from extensions.continuity_github.model import STATES, ready_missing, ai_context, render_resume, export_packet, fail
from extensions.continuity_github.logs import repository_store as logs_store

EXTENSION = {'title': '协同交接（GitHub 实验版）', 'description': '关联 GitHub 工作项、日志与代码依据；独立实验数据。'}


def handle(context, method, data):
    store = repository_store(context.repo)
    action = data.get('action', 'list')
    from extensions.continuity_github.service import extra
    result = extra(context, method, data)
    if result is not None:
        return result
    if method == 'GET':
        if action == 'list':
            return {'records': store.listing(), 'states': STATES}
        if action == 'config':
            addresses = remotes(context.repo)
            snap = context.snapshot()
            return {'revision': snap['revision'], 'nodes': snap['nodes'], 'states': STATES,
                    'defaultSource': {'kind': 'git_remote', 'value': 'https://' + addresses[0]['address']} if addresses else {'kind': 'local_path', 'value': str(context.repo)},
                    'note': '本机接续记录与文件交换，不是在线聊天或身份认证。'}
        if action == 'logs':
            return {'entries': logs_store(context.repo).listing()}
        if action == 'get':
            r = store.get(data.get('id'))
            return {'record': r, 'missing': ready_missing(r)}
        if action == 'inspect':
            return inspect(context, store.get(data.get('id')))
        if action == 'evidence':
            return read_evidence(context, store.get(data.get('id')), data.get('path'))
        if action == 'history':
            return {'history': store.history(data.get('id'))}
        if action == 'export':
            r = store.get(data.get('id'))
            return {'packet': export_packet(r), 'markdown': render_resume(r), 'aiContext': ai_context(r),
                    'legacyHandoff': r['handoff']}
    if method == 'POST':
        if action == 'create':
            return {'record': store.create(data, capture(context, data))}
        if action == 'update':
            return {'record': store.update(data)}
        if action == 'refresh_checkpoint':
            # Re-capture is explicit, preserving previous revisions.
            return {'record': store.update(data, capture(context, data))}
        if action == 'event':
            return {'record': store.event(data)}
        if action == 'followup':
            previous = store.get(data.get('id'))
            if data.get('expectedVersion') != previous['version']:
                fail('原记录已变化，请重新打开后创建下一次接续点', 409)
            payload = {**data, 'task': data.get('task', previous['task']),
                       'checklist': [{'id': c['id'], 'text': c['text'], 'state': 'pending', 'note': '', 'evidence': ''} for c in previous['checklist']],
                       'scope': previous['scope'], 'logIds': data.get('logIds', []), 'references': previous.get('references', []), 'sourceLocator': previous['handoff']['sourceLocator']}
            return {'record': store.create(payload, capture(context, payload), parent=previous['id'])}
        if action == 'import_start':
            return store.begin_import(data)
        if action == 'import_chunk':
            return store.import_chunk(data)
        if action == 'import_finish':
            return {'record': store.finish_import(data.get('uploadId'))}
        if action == 'import_cancel':
            return store.cancel_import(data.get('uploadId'))
        if action == 'import_packet':
            return {'record': store.import_record(data.get('packet'))}
    fail('不支持的接续操作')
