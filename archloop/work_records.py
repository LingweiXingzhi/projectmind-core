"""Private shared work records with immutable workspace/version context.

These are contributor records or AI candidates, never confirmed model decisions.
The public deployment boundary supplies account identity; text does not approve itself.
"""
from copy import deepcopy
from functools import wraps
import json
from pathlib import Path
import re

from extension_host import ExtensionError
from extensions.worklog.store import Store, CATEGORIES
from .contract import ContractError


def controlled(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ExtensionError as exc:
            code = {404: 'NOT_FOUND', 409: 'STALE_CONTEXT', 429: 'BACKEND_UNAVAILABLE'}.get(int(exc.status), 'VALIDATION_FAILED')
            raise ContractError(code, str(exc)) from exc
    return call


class WorkspaceRecords:
    MAX_ENTRIES = 1000
    MAX_HISTORY = 5000
    PAGE_SIZE = 200

    def __init__(self, workbench, data_root, origin):
        from deployment.access import _outside_git
        self.workbench, self.origin = workbench, origin
        root = _outside_git(Path(data_root) / 'work-records')
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.stat().st_mode & 0o077:
            raise ContractError('STORAGE_FAILED', '工作记录目录必须为私有目录')
        self.store = Store(_outside_git(root / 'records.sqlite3'))
        self.store.path.chmod(0o600)

    def status(self):
        return {'available': True, 'kind': 'shared_workspace_records', 'storage': 'private_server_sqlite',
                'actorIdentity': 'authenticated_account', 'attachments': False,
                'maxEntries': self.MAX_ENTRIES, 'maxHistoryVersions': self.MAX_HISTORY,
                'note': '参与者记录或 AI 候选；分类不代表正式认知或团队批准。'}

    def _actor(self, meta):
        from urllib.parse import urlsplit
        from ipaddress import ip_address
        try:
            valid = isinstance(meta, dict) and ip_address(meta.get('peer', '')).is_loopback \
                and meta.get('host') == urlsplit(self.origin).netloc and meta.get('origin') == self.origin \
                and isinstance(meta.get('actor'), str) and bool(meta['actor'].strip()) \
                and isinstance(meta.get('browserSession'), str) and re.fullmatch(r'[0-9a-f]{64}', meta['browserSession'])
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ContractError('REQUEST_FORBIDDEN', '工作记录需要真实登录请求上下文')
        return meta['actor']

    def binding(self, record):
        envelope = self.workbench._envelope(record)
        draft = record.get('draft') or {}
        stage = 'sample' if draft.get('origin') == 'dev_sample' or 'dev_sample' in draft.get('lineage', []) \
            else ('published' if envelope['identity'].get('mapSourceRevision') else ('draft' if draft else 'workspace'))
        return {'workspaceId': record['workspaceId'], 'context': record['context'],
                **deepcopy(envelope['identity']), 'stage': stage}

    @controlled
    def listing(self, workspace_id=None):
        if workspace_id is not None:
            self.workbench.store.load_workspace(workspace_id)
        entries = [item for item in self.store.listing()
                   if workspace_id is None or item.get('workspaceId') == workspace_id]
        return {'entries': entries[:self.PAGE_SIZE], 'total': len(entries), 'truncated': len(entries) > self.PAGE_SIZE,
                'categories': CATEGORIES, 'backend': self.status()}

    def _entry(self, workspace_id, entry_id, db=None):
        item = self.store.get(entry_id, db)
        if item.get('workspaceId') != workspace_id:
            raise ContractError('NOT_FOUND', '记录不属于当前工作区')
        return item

    @controlled
    def history(self, workspace_id, entry_id):
        self.workbench.store.load_workspace(workspace_id)
        with self.store.connect() as db:
            self._entry(workspace_id, entry_id, db)
            rows = db.execute('SELECT document FROM history WHERE id=? ORDER BY version DESC LIMIT 100', (entry_id,))
            history = [json.loads(row['document']) for row in rows]
            total = db.execute('SELECT count(*) FROM history WHERE id=?', (entry_id,)).fetchone()[0]
        return {'history': history, 'total': total, 'truncated': total > 100, 'backend': self.status()}

    @controlled
    def save(self, record, request, meta):
        actor = self._actor(meta)
        required = {'category', 'date', 'title', 'body', 'origin', 'expectedMapRevision', 'expectedDraftRevision'}
        optional = {'id', 'expectedVersion', 'author', 'actor'}
        if not isinstance(request, dict) or not required <= set(request) or set(request) - required - optional:
            raise ContractError('VALIDATION_FAILED', '记录请求缺少必要字段或包含未支持字段')
        if ('id' in request) != ('expectedVersion' in request) or ('id' in request and (
                not isinstance(request['id'], str) or not re.fullmatch(r'[a-f0-9]{32}', request['id']))):
            raise ContractError('VALIDATION_FAILED', '编辑记录须提供 id 与 expectedVersion')
        binding = self.binding(record)
        if request['expectedMapRevision'] != binding['mapRevision'] or request['expectedDraftRevision'] != binding['draftRevision']:
            raise ContractError('STALE_CONTEXT', '草稿或图版本已变化，请保留文本并重新读取工作区')
        data = {key: request[key] for key in ('category', 'date', 'title', 'body', 'origin')}
        data['author'] = actor
        if request.get('id'):
            data.update(id=request['id'], expectedVersion=request['expectedVersion'])
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = self._entry(record['workspaceId'], data['id'], db) if data.get('id') else None
            if (previous is None and db.execute('SELECT count(*) FROM entries').fetchone()[0] >= self.MAX_ENTRIES) \
                    or db.execute('SELECT count(*) FROM history').fetchone()[0] >= self.MAX_HISTORY:
                raise ContractError('BACKEND_UNAVAILABLE', '工作记录容量已满，先导出并由运维整理')
            item = self.store.save(data, binding['codeRevision'], db=db, server_fields={
                'workspaceId': record['workspaceId'], 'binding': binding, 'authorIdentity': 'authenticated_account',
                'recordAuthority': 'participant_claim' if data['origin'] == 'human' else 'ai_candidate',
                'createdBy': previous['createdBy'] if previous else actor})
        return {'entry': item, 'backend': self.status()}

    @controlled
    def export(self, workspace_id):
        self.workbench.store.load_workspace(workspace_id)
        entries = [v for v in self.store.listing() if v.get('workspaceId') == workspace_id]
        packet = {'schemaVersion': 'workspace_records_v1', 'workspaceId': workspace_id,
                  'authority': 'participant_records_and_ai_candidates', 'entries': entries}
        if len(json.dumps(packet, ensure_ascii=False).encode()) > 2 * 1024 * 1024:
            raise ContractError('BACKEND_UNAVAILABLE', '导出超过 2 MiB；请使用私有数据库冷备')
        return packet
