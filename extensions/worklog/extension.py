"""Independent worklog API within the existing 64 KiB JSON seam."""
from extensions.worklog.store import CATEGORIES, fail, repository_store

EXTENSION = {'title': '工作日志', 'description': '持续记录项目进展、决策、目标和待解决事项。'}


def handle(context, method, data):
    store = repository_store(context.repo)
    action = data.get('action', 'list')
    if method == 'GET':
        if action == 'list':
            return {'entries': store.listing(), 'categories': CATEGORIES,
                    'note': '记录保存在本机项目，尚未独立核实；关键决策分类不代表团队已批准。'}
        if action == 'get':
            return {'entry': store.get(data.get('id'))}
        if action == 'history':
            return {'history': store.history(data.get('id'))}
        if action == 'file':
            return {'file': store.file(data.get('id'))}
        if action == 'backup':
            return store.backup()
    if method == 'POST':
        if action == 'save':
            return {'entry': store.save(data, context.snapshot()['revision'])}
        if action == 'import_start':
            return store.start(data)
        if action == 'import_chunk':
            return store.chunk(data)
        if action == 'import_finish':
            return {'entry': store.finish(data, context.snapshot()['revision'])}
        if action == 'import_cancel':
            return store.cancel(data.get('uploadId'))
    fail('不支持的日志操作')
