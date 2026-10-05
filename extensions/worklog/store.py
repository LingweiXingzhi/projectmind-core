"""Transactional, repository-local work records; never formal model decisions."""
import base64
from contextlib import contextmanager
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from extension_host import ExtensionError

CATEGORIES = {'daily': '每日工作日志', 'decision': '关键决策', 'goal': '当前目标', 'issue': '待解决事项'}
LIMIT = 10 * 1024 * 1024
TEXT_LIMIT = 15000
ID = re.compile(r'[a-f0-9]{32}\Z')
MIMES = {'md': 'text/markdown', 'pdf': 'application/pdf', 'doc': 'application/msword',
         'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


def fail(message, status=400):
    raise ExtensionError(status, message)


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, limit, label, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        fail(f'{label}须为文本，最多 {limit} 字符' + ('，且不能为空' if required else ''))
    return value


def metadata(data):
    if data.get('category') not in CATEGORIES:
        fail('请选择有效的日志分类')
    try:
        day = date.fromisoformat(data.get('date', ''))
    except (TypeError, ValueError):
        fail('日期须为 YYYY-MM-DD')
    origin = data.get('origin', 'human')
    if origin not in ('human', 'ai'):
        fail('来源须为 human 或 ai')
    return {'category': data['category'], 'date': day.isoformat(),
            'title': text(data.get('title'), 200, '标题', True).strip(),
            'body': text(data.get('body', ''), TEXT_LIMIT, '正文'),
            'author': text(data.get('author', ''), 100, '作者'), 'origin': origin,
            'status': 'ai_candidate' if origin == 'ai' else 'contributor_record'}


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        fail('记录标识无效')
    return value


def preview(raw, kind):
    if kind == 'md':
        try:
            return raw.decode('utf-8-sig'), ''
        except UnicodeDecodeError:
            fail('Markdown 请使用 UTF-8 编码')
    if kind == 'pdf':
        if not raw.startswith(b'%PDF-'):
            fail('文件内容不是 PDF')
        return '', 'PDF 展示原件；扫描文档未做 OCR。'
    if kind == 'docx':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo('word/document.xml')
                if info.file_size > 4 * 1024 * 1024:
                    fail('Word 正文超过解析上限')
                xml = archive.read(info)
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                    fail('Word 包含不支持的 XML 声明')
                root = ET.fromstring(xml)
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                result = '\n'.join(''.join(e.text or '' for e in p.iter(ns + 't')) for p in root.iter(ns + 'p'))
                return result, 'Word 正文视图；图片、分页及复杂排版请下载原件查看。'
        except (zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError):
            fail('无法读取 DOCX 正文，请检查文件是否损坏或加密')
    if not raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
        fail('文件内容不是旧版 DOC')
    converter = shutil.which('textutil') or shutil.which('libreoffice') or shutil.which('soffice')
    if not converter:
        fail('旧版 DOC 展示需要 macOS textutil 或 LibreOffice；可另存为 DOCX 后导入')
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / 'input.doc'
        source.write_bytes(raw)
        if Path(converter).name == 'textutil':
            command = [converter, '-convert', 'txt', '-stdout', str(source)]
        else:
            profile = (Path(folder) / 'profile').as_uri()
            command = [converter, f'-env:UserInstallation={profile}', '--headless', '--convert-to', 'txt:Text', '--outdir', folder, str(source)]
        try:
            result = subprocess.run(command, capture_output=True, timeout=25)
            output = result.stdout if Path(converter).name == 'textutil' else (Path(folder) / 'input.txt').read_bytes()
            if result.returncode or not output.strip():
                fail('DOC 转换失败，请另存为 DOCX 后导入')
            return output.decode('utf-8-sig'), 'Word 正文视图；复杂排版请下载原件查看。'
        except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError):
            fail('DOC 转换失败或超时，请另存为 DOCX 后导入')


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, version INTEGER, document TEXT);
            CREATE TABLE IF NOT EXISTS history(id TEXT, version INTEGER, document TEXT, PRIMARY KEY(id, version));
            CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, name TEXT, kind TEXT, raw BLOB, preview TEXT, note TEXT);
            CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY, meta TEXT, name TEXT, kind TEXT, size INTEGER, raw BLOB, created TEXT);
            ''')
            db.execute("DELETE FROM uploads WHERE julianday(created) < julianday('now', '-1 day')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, entry_id, db=None):
        identifier(entry_id)
        if db is None:
            with self.connect() as conn:
                return self.get(entry_id, conn)
        row = db.execute('SELECT document FROM entries WHERE id=?', (entry_id,)).fetchone()
        if not row:
            fail('记录不存在', 404)
        return json.loads(row['document'])

    def save(self, data, revision, attachment=None, db=None):
        item = metadata(data)
        if db is None:
            with self.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                return self.save(data, revision, attachment, conn)
        entry_id = data.get('id')
        previous = self.get(entry_id, db) if entry_id else None
        if previous and (type(data.get('expectedVersion')) is not int or data['expectedVersion'] != previous['version']):
            fail('记录已被更新，请保留当前草稿并重新打开最新版', 409)
        stamp = now()
        item.update(id=entry_id or uuid.uuid4().hex, version=previous['version'] + 1 if previous else 1,
                    createdAt=previous['createdAt'] if previous else stamp, updatedAt=stamp,
                    codeRevision=revision, attachment=attachment or (previous.get('attachment') if previous else None))
        document = json.dumps(item, ensure_ascii=False)
        db.execute('INSERT OR REPLACE INTO entries VALUES(?,?,?)', (item['id'], item['version'], document))
        db.execute('INSERT INTO history VALUES(?,?,?)', (item['id'], item['version'], document))
        return item

    def listing(self):
        with self.connect() as db:
            items = [json.loads(r['document']) for r in db.execute('SELECT document FROM entries')]
        return sorted(items, key=lambda e: (e['date'], e['updatedAt']), reverse=True)

    def history(self, entry_id):
        self.get(entry_id)
        with self.connect() as db:
            return [json.loads(r['document']) for r in db.execute('SELECT document FROM history WHERE id=? ORDER BY version DESC', (entry_id,))]

    def file(self, file_id):
        identifier(file_id)
        with self.connect() as db:
            row = db.execute('SELECT * FROM files WHERE id=?', (file_id,)).fetchone()
        if not row:
            fail('原件不存在', 404)
        return {'id': row['id'], 'name': row['name'], 'kind': row['kind'], 'mime': MIMES[row['kind']],
                'base64': base64.b64encode(row['raw']).decode(), 'preview': row['preview'], 'note': row['note']}

    def start(self, data):
        meta = metadata(data)
        name = text(data.get('filename'), 200, '文件名', True)
        kind = name.rsplit('.', 1)[-1].lower()
        if kind not in MIMES:
            fail('支持 MD、DOC、DOCX、PDF')
        if type(data.get('size')) is not int or not 0 < data['size'] <= LIMIT:
            fail('文件大小须在 1 字节至 10 MB 之间')
        upload_id = uuid.uuid4().hex
        with self.connect() as db:
            if db.execute('SELECT count(*) FROM uploads').fetchone()[0] >= 8:
                fail('未完成的导入过多，请等待过期清理后重试', 429)
            db.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)', (upload_id, json.dumps(meta), name, kind, data['size'], b'', now()))
        return {'uploadId': upload_id, 'chunkBytes': 24576}

    def chunk(self, data):
        identifier(data.get('uploadId'))
        encoded = text(data.get('base64'), 32768, '分片')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError:
            fail('分片编码无效')
        if not raw:
            fail('分片不能为空')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM uploads WHERE id=?', (data['uploadId'],)).fetchone()
            if not row:
                fail('导入会话已过期或不存在', 404)
            if type(data.get('offset')) is not int or data['offset'] != len(row['raw']):
                fail('分片位置不一致，请重新导入', 409)
            if len(row['raw']) + len(raw) > row['size']:
                fail('分片超过声明的文件大小')
            db.execute('UPDATE uploads SET raw=? WHERE id=?', (row['raw'] + raw, row['id']))
            return {'received': len(row['raw']) + len(raw)}

    def finish(self, data, revision):
        identifier(data.get('uploadId'))
        with self.connect() as db:
            row = db.execute('SELECT * FROM uploads WHERE id=?', (data['uploadId'],)).fetchone()
        if not row or len(row['raw']) != row['size']:
            fail('导入尚未完成或会话不存在')
        content, note = preview(row['raw'], row['kind'])
        if len(content) > 200000:
            content = content[:200000]
            note += ' 正文视图仅展示前 200,000 字符，完整内容见原件。'
        attachment = {'id': row['id'], 'name': row['name'], 'kind': row['kind'], 'size': row['size'],
                      'sha256': hashlib.sha256(row['raw']).hexdigest(), 'note': note}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM uploads WHERE id=?', (row['id'],)).fetchone():
                fail('文件已经导入', 409)
            db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)', (row['id'], row['name'], row['kind'], row['raw'], content, note))
            entry = self.save(json.loads(row['meta']), revision, attachment, db)
            db.execute('DELETE FROM uploads WHERE id=?', (row['id'],))
        return entry

    def cancel(self, upload_id):
        identifier(upload_id)
        with self.connect() as db:
            db.execute('DELETE FROM uploads WHERE id=?', (upload_id,))
        return {'cancelled': True}

    def backup(self):
        with self.connect() as db:
            db.execute('BEGIN')
            entries = [json.loads(r['document']) for r in db.execute('SELECT document FROM entries')]
            history = [json.loads(r['document']) for r in db.execute('SELECT document FROM history')]
            files = [{'id': r['id'], 'name': r['name'], 'kind': r['kind'], 'base64': base64.b64encode(r['raw']).decode(), 'preview': r['preview'], 'note': r['note']} for r in db.execute('SELECT * FROM files')]
        return {'format': 'projectmind-worklog-backup-v1', 'exportedAt': now(), 'entries': entries, 'history': history, 'files': files}


def repository_storage_folder(repo):
    """Resolve the repository's common Git directory — the shared D
    storage context. D-01: the explicit repo argument always wins; inherited
    GIT_* environment (GIT_DIR, GIT_WORK_TREE, GIT_COMMON_DIR, ...) is
    stripped from the subprocess so it can never silently redirect D storage
    into another repository. Side-effect-free (D-02): no Store is
    constructed, no directory created, no SQLite file touched."""
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    result = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--git-common-dir'],
                            capture_output=True, text=True, timeout=5, env=env)
    if result.returncode:
        fail('无法定位项目日志存储目录')
    folder = Path(result.stdout.strip())
    if not folder.is_absolute():
        folder = Path(repo) / folder
    return folder.resolve()


def repository_store(repo):
    return Store(repository_storage_folder(repo) / 'projectmind-worklog' / 'records.sqlite3')
