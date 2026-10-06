"""Additional linking, log editing and local evidence inspection endpoints."""
from pathlib import Path
from contextlib import closing
import sqlite3
import json
import uuid
from extensions.worklog.store import CATEGORIES, fail
from extensions.continuity_github.logs import repository_store as logs_store, common_dir
from extensions.continuity_github.store import repository_store
from extensions.continuity_github.references import references, all_references
from extensions.continuity.inspection import git, remotes


def verify(context, values):
    refs = references(values)
    addresses = {r['address'].lower() for r in remotes(context.repo)}
    result = []
    for ref in refs:
        item = {**ref, 'localState': 'link_only', 'note': '远端内容和状态未联网读取。'}
        if ref['revision']:
            if ('github.com/' + ref['repository']).lower() not in addresses:
                item.update(localState='repository_unconfirmed', note='本机 remote 未能对应此链接仓库；不以同名 SHA 证明来源。')
            else:
                try:
                    actual = git(context.repo, 'rev-parse', '--verify', ref['revision'] + '^{commit}').decode().strip()
                    if actual != ref['revision']:
                        raise ValueError()
                    item.update(localState='commit_present', note='本机存在该完整提交；不证明 Issue/PR 已完成。')
                    if ref['path']:
                        raw = git(context.repo, 'show', ref['revision'] + ':' + ref['path'])
                        if len(raw) > 1024 * 1024 or b'\x00' in raw:
                            item.update(localState='preview_unavailable', note='二进制或文件超过预览限制，仍可打开固定版本链接。')
                        else:
                            item.update(localState='code_present', content=raw[:12000].decode('utf-8', errors='replace'), truncated=len(raw) > 12000)
                except (Exception,) as exc:
                    from extension_host import ExtensionError
                    if not isinstance(exc, (ExtensionError, ValueError)):
                        raise
                    item.update(localState='missing', note='本机缺少此提交或文件；请先同步正确仓库再核查。')
        result.append(item)
    return {'references': result}


def extra(context, method, data):
    action = data.get('action', 'list')
    if action in ('original_logs', 'copy_original_log'):
        source = common_dir(context.repo) / 'projectmind-worklog' / 'records.sqlite3'
        if not source.is_file():
            if action == 'original_logs': return {'entries': []}
            fail('本机没有原工作日志', 404)
        try:
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as db:
                if method == 'GET' and action == 'original_logs':
                    return {'entries': [json.loads(r[0]) for r in db.execute('SELECT document FROM entries ORDER BY rowid DESC LIMIT 1000')], 'note': '只读原日志；复制后才可在实验版编辑。'}
                if method != 'POST' or action != 'copy_original_log': fail('请使用对应的只读或复制操作')
                row = db.execute('SELECT document FROM entries WHERE id=?', (data.get('id'),)).fetchone()
                if row is None: fail('原日志不存在', 404)
                entry = json.loads(row[0]); attachment = entry.get('attachment'); file = None
                if attachment:
                    file = db.execute('SELECT name,kind,raw,preview,note FROM files WHERE id=?', (attachment['id'],)).fetchone()
                    if file is None: fail('原日志附件缺失，请先确认来源', 404)
        except sqlite3.Error:
            fail('原日志暂时不可读；没有修改它', 503)
        store = logs_store(context.repo)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if file:
                file_id = uuid.uuid4().hex
                db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)', (file_id, *file))
                attachment = {**attachment, 'id': file_id}
            clean = {k: entry[k] for k in ('title', 'body', 'category', 'date', 'author', 'origin')}
            clean['references'] = data.get('references', [])
            item = store.save(clean, entry['codeRevision'], attachment, db)
            item['sourceRecord'] = {'store': 'original_worklog', 'id': entry['id'], 'version': entry['version'], 'status': 'copied_unverified'}
            document = json.dumps(item, ensure_ascii=False)
            db.execute('UPDATE entries SET document=? WHERE id=?', (document, item['id']))
            db.execute('UPDATE history SET document=? WHERE id=? AND version=1', (document, item['id']))
        return {'entry': item, 'note': '已复制到独立实验日志；原记录及附件未改。'}
    if method == 'GET' and action == 'log_page':
        return {'html': Path(__file__).with_name('worklog.html').read_text()}
    if action.startswith('log_'):
        store = logs_store(context.repo); key = action[4:]
        if method == 'GET':
            if key == 'list':
                addresses = remotes(context.repo)
                github = next((r['address'] for r in addresses if r['address'].startswith('github.com/')), None)
                return {'entries': store.listing(), 'categories': CATEGORIES,
                        'currentCodeUrl': 'https://' + github + '/commit/' + context.snapshot()['revision'] if github else None,
                        'note': '独立实验日志，不覆盖原工作日志。'}
            if key == 'get': return {'entry': store.get(data.get('id'))}
            if key == 'history': return {'history': store.history(data.get('id'))}
            if key == 'file': return {'file': store.file(data.get('id'))}
            if key == 'backup': return store.backup()
        if method == 'POST':
            if key == 'save': return {'entry': store.save(data, context.snapshot()['revision'])}
            if key == 'import_start': return store.start(data)
            if key == 'import_chunk': return store.chunk(data)
            if key == 'import_finish': return {'entry': store.finish(data, context.snapshot()['revision'])}
            if key == 'import_cancel': return store.cancel(data.get('uploadId'))
        fail('不支持的实验日志操作')
    if method == 'POST' and action == 'verify_references':
        return verify(context, data.get('references', []))
    if method == 'GET' and action == 'reference_index':
        groups = {}
        for entry in logs_store(context.repo).listing():
            for ref in references(entry.get('references', [])):
                group = groups.setdefault(ref['id'], {'reference': ref, 'logs': [], 'tasks': []})
                group['logs'].append({'id': entry['id'], 'title': entry['title'], 'version': entry['version']})
        tasks = repository_store(context.repo)
        for brief in tasks.listing():
            record = tasks.get(brief['id'])
            for ref in all_references(record):
                group = groups.setdefault(ref['id'], {'reference': ref, 'logs': [], 'tasks': []})
                group['tasks'].append({'id': record['id'], 'title': record['task']['title'], 'state': record['state']})
        return {'items': list(groups.values()), 'note': '关联关系来自参与者填写，不是 GitHub 在线状态。'}
    return None
