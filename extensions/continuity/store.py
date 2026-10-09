"""Immutable revisions and explicit participant events, persisted locally."""
import base64
from contextlib import contextmanager
from copy import deepcopy
import json
import sqlite3
import uuid
from extensions.worklog.store import now, identifier, repository_storage_folder, text, fail
from extensions.continuity.model import MAX_PACKAGE, STATES, REVIEW_FIELDS, task, checklist, scope, ready_missing, validate_packet

EVENT_STATES = {'ready': 'ready', 'receive': 'receiving', 'start': 'active', 'block': 'blocked',
                'resume': 'active', 'claim': 'active', 'finish_session': 'ready', 'complete': 'completed'}
# Keep legacy events valid; the UI exposes four user actions instead of these transitions.
ALLOWED = {'draft': {'ready', 'claim', 'block', 'finish_session', 'complete', 'question', 'note'},
           'ready': {'receive', 'claim', 'block', 'finish_session', 'complete', 'question', 'note'},
           'receiving': {'start', 'claim', 'block', 'finish_session', 'complete', 'question', 'note'},
           'active': {'block', 'finish_session', 'complete', 'question', 'note'},
           'blocked': {'resume', 'claim', 'finish_session', 'complete', 'question', 'note'}, 'completed': {'note'}}


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, document TEXT);
            CREATE TABLE IF NOT EXISTS revisions(id TEXT, version INTEGER, document TEXT, PRIMARY KEY(id,version));
            CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY, name TEXT, size INTEGER, raw BLOB, created TEXT);
            ''')
            db.execute("DELETE FROM imports WHERE julianday(created)<julianday('now','-1 day')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, value, db=None):
        identifier(value)
        if db is None:
            with self.connect() as conn:
                return self.get(value, conn)
        row = db.execute('SELECT document FROM records WHERE id=?', (value,)).fetchone()
        if row is None:
            fail('接续记录不存在', 404)
        return json.loads(row['document'])

    def commit(self, record, db):
        record['updatedAt'] = now()
        document = json.dumps(record, ensure_ascii=False)
        if len(document.encode()) > MAX_PACKAGE:
            fail('接续资料超过 12 MB，请减少原件或拆分交接范围')
        db.execute('INSERT OR REPLACE INTO records VALUES(?,?)', (record['id'], document))
        db.execute('INSERT INTO revisions VALUES(?,?,?)', (record['id'], record['version'], document))
        return deepcopy(record)

    def create(self, data, captured, parent=None):
        record = {'id': uuid.uuid4().hex, 'version': 1, 'createdAt': now(), 'state': 'draft',
                  'task': task(data.get('task')), 'checklist': checklist(data.get('checklist', [])),
                  'scope': scope(data.get('scope', []), captured['handoff']), 'events': [], 'importedHistory': [],
                  'review': {}, 'parentId': parent, **deepcopy(captured)}
        with self.connect() as db:
            return self.commit(record, db)

    def match(self, data, db):
        record = self.get(data.get('id'), db)
        if type(data.get('expectedVersion')) is not int or data['expectedVersion'] != record['version']:
            fail('记录已更新；保留草稿，重新打开最新版后继续', 409)
        return record

    def update(self, data, captured=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = self.match(data, db)
            if record['state'] == 'completed':
                fail('已完成记录保留为历史；请创建下一次接续点', 409)
            record['task'] = task(data.get('task', record['task']))
            record['checklist'] = checklist(data.get('checklist', record['checklist']))
            if captured:
                record.update(deepcopy(captured))
                record['state'] = 'draft'
                record['review'] = {}
            record['scope'] = scope(data.get('scope', record['scope']), record['handoff'])
            record['version'] += 1
            if record['state'] in ('ready', 'receiving'):
                record['state'] = 'draft'
                record['review'] = {}
            return self.commit(record, db)

    def event(self, data):
        kind = data.get('kind')
        actor = text(data.get('actor', ''), 100, '操作者名称', True).strip()
        origin = data.get('origin', 'human')
        if origin not in ('human', 'ai'):
            fail('反馈来源须为 human 或 ai')
        note = text(data.get('note', ''), 4000, '反馈说明')
        evidence = text(data.get('evidence', ''), 2000, '反馈依据')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = self.match(data, db)
            if kind not in ALLOWED[record['state']]:
                fail('当前状态不能执行此操作', 409)
            if len(record['events']) >= 300:
                fail('记录历史过长，请建立新的接续点')
            if kind == 'ready' and ready_missing(record):
                fail('准备交接前请补充：' + '、'.join(ready_missing(record)))
            if kind in ('start', 'resume'):
                review = data.get('review')
                if not isinstance(review, dict) or set(review) != REVIEW_FIELDS or any(type(v) is not bool for v in review.values()) or not all(review.values()):
                    fail('请完成四项接手检查，再标记继续工作')
                record['review'] = {'checks': review, 'actor': actor, 'at': now(), 'status': 'participant_report'}
            if kind == 'claim':
                review = data.get('review', {})
                if not isinstance(review, dict) or not set(review).issubset(REVIEW_FIELDS) or any(type(v) is not bool for v in review.values()):
                    fail('接手检查记录须为勾选项；未检查的内容不能自动算通过')
                record['review'] = {'checks': review, 'actor': actor, 'at': now(), 'status': 'participant_report'}
                if record['state'] == 'blocked' and not note.strip():
                    fail('请说明问题如何处理，或为何现在可以继续')
            if kind in ('block', 'question', 'complete', 'finish_session') and not note.strip():
                fail('请写清问题、阻塞或完成结果')
            if kind == 'complete':
                pending = [c['text'] for c in record['checklist'] if c['state'] != 'done']
                if pending:
                    fail('任务尚有未完成项：' + '、'.join(pending) + '。可返回清单处理，或选择“结束本次接手”保留这些事项。')
                if not evidence.strip():
                    fail('请填写任务完成的验证依据；若只是暂时结束，请选择“结束本次接手”。')
            # A session ending leaves the task open. Save the next person's entry point
            # atomically with the event; existing materials and unfinished items stay intact.
            continuation = {}
            for key, limit, label in [('stopPoint', 4000, '停止位置'), ('nextAction', 2000, '下一步')]:
                if key in data or kind == 'finish_session':
                    continuation[key] = text(data.get(key, ''), limit, label, True).strip()
                    if not continuation[key]:
                        fail('结束本次接手前请填写' + label)
            if continuation:
                if record['state'] == 'completed':
                    fail('已完成任务只能补充历史说明，不能改写停止位置', 409)
                record['task'] = task({**record['task'], **continuation})
            event = {'kind': kind, 'actor': actor, 'origin': origin, 'note': note, 'evidence': evidence,
                     'at': now(), 'status': 'ai_candidate' if origin == 'ai' else 'participant_report'}
            event.update(continuation)
            record['events'].append(event)
            if kind in EVENT_STATES:
                record['state'] = EVENT_STATES[kind]
            record['version'] += 1
            return self.commit(record, db)

    def listing(self):
        with self.connect() as db:
            values = [json.loads(r['document']) for r in db.execute('SELECT document FROM records')]
        return [{'id': v['id'], 'version': v['version'], 'title': v['task']['title'], 'goal': v['task']['goal'],
                 'state': v['state'], 'owner': v['task']['owner'], 'updatedAt': v['updatedAt'],
                 'revision': v['handoff']['codeRevision'], 'logCount': len(v['logs']),
                 'doneCount': sum(c['state'] == 'done' for c in v['checklist']), 'checkCount': len(v['checklist'])}
                for v in sorted(values, key=lambda r: r['updatedAt'], reverse=True)]

    def history(self, value):
        self.get(value)
        with self.connect() as db:
            return [json.loads(r['document']) for r in db.execute('SELECT document FROM revisions WHERE id=? ORDER BY version DESC', (value,))]

    def import_record(self, packet):
        values = validate_packet(packet)
        transfer = values.pop('transferId')
        rec = {'id': uuid.uuid4().hex, 'version': 1, 'state': 'receiving', 'createdAt': now(),
               'events': [], 'review': {}, 'parentId': None, 'importedFrom': transfer, **values}
        # Incoming states are history, never proof of readiness on this machine.
        with self.connect() as db:
            return self.commit(rec, db)

    def begin_import(self, data):
        name = text(data.get('filename'), 200, '文件名', True)
        size = data.get('size')
        if not name.lower().endswith('.json') or type(size) is not int or not 0 < size <= MAX_PACKAGE:
            fail('请选 1 字节至 12 MB 的交接 JSON')
        value = uuid.uuid4().hex
        with self.connect() as db:
            if db.execute('SELECT count(*) FROM imports').fetchone()[0] >= 8:
                fail('未完成导入过多', 429)
            db.execute('INSERT INTO imports VALUES(?,?,?,?,?)', (value, name, size, b'', now()))
        return {'uploadId': value, 'chunkBytes': 24576}

    def import_chunk(self, data):
        identifier(data.get('uploadId'))
        encoded = text(data.get('base64'), 32768, '文件分片')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError:
            fail('分片编码无效')
        if not raw:
            fail('空分片无效')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM imports WHERE id=?', (data['uploadId'],)).fetchone()
            if row is None:
                fail('导入会话不存在或过期', 404)
            if type(data.get('offset')) is not int or data['offset'] != len(row['raw']):
                fail('分片位置不一致', 409)
            if len(raw) + len(row['raw']) > row['size']:
                fail('文件超过声明大小')
            db.execute('UPDATE imports SET raw=? WHERE id=?', (row['raw'] + raw, row['id']))
            return {'received': len(row['raw']) + len(raw)}

    def finish_import(self, value):
        identifier(value)
        with self.connect() as db:
            row = db.execute('SELECT * FROM imports WHERE id=?', (value,)).fetchone()
        if row is None or len(row['raw']) != row['size']:
            fail('文件尚未传完或导入会话不存在')
        try:
            packet = json.loads(row['raw'].decode('utf-8-sig'))
        except (ValueError, UnicodeDecodeError, RecursionError):
            fail('文件不是有效的 UTF-8 JSON')
        values = validate_packet(packet)
        transfer = values.pop('transferId')
        rec = {'id': uuid.uuid4().hex, 'version': 1, 'state': 'receiving', 'createdAt': now(),
               'events': [], 'review': {}, 'parentId': None, 'importedFrom': transfer, **values}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM imports WHERE id=?', (value,)).fetchone():
                fail('文件已经导入', 409)
            result = self.commit(rec, db)
            db.execute('DELETE FROM imports WHERE id=?', (value,))
            return result

    def cancel_import(self, value):
        identifier(value)
        with self.connect() as db:
            db.execute('DELETE FROM imports WHERE id=?', (value,))
        return {'cancelled': True}


def repository_store(repo):
    # Same common Git directory, separate DB; original worklog records untouched.
    # D-02: the path derives from the shared side-effect-free storage context.
    # Continuity no longer constructs the Worklog Store (mkdir + SQLite schema
    # side effects) just to read a path, so a corrupted Worklog database can
    # no longer break Continuity functionality that never needed Worklog data.
    return Store(repository_storage_folder(repo) / 'projectmind-continuity' / 'records.sqlite3')
