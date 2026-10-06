"""Experimental log store, physically separate from all existing records."""
import json
import subprocess
from pathlib import Path
from extensions.worklog.store import Store as OriginalStore, fail
from extensions.continuity_github.references import references


def common_dir(repo):
    r = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--git-common-dir'], capture_output=True, text=True, timeout=5)
    if r.returncode:
        fail('无法定位实验记录目录')
    path = Path(r.stdout.strip())
    return (path if path.is_absolute() else Path(repo) / path).resolve()


class Store(OriginalStore):
    def save(self, data, revision, attachment=None, db=None):
        if db is None:
            with self.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                return self.save(data, revision, attachment, conn)
        old = self.get(data['id'], db) if data.get('id') else None
        refs = references(data.get('references', old.get('references', []) if old else []))
        item = super().save(data, revision, attachment, db)
        item['references'] = refs
        if old and old.get('sourceRecord'):
            item['sourceRecord'] = old['sourceRecord']
        document = json.dumps(item, ensure_ascii=False)
        db.execute('UPDATE entries SET document=? WHERE id=?', (document, item['id']))
        db.execute('UPDATE history SET document=? WHERE id=? AND version=?', (document, item['id'], item['version']))
        return item

    def start(self, data):
        # The legacy importer strips optional metadata; retain validated references.
        refs = references(data.get('references', []))
        result = super().start(data)
        with self.connect() as db:
            row = db.execute('SELECT meta FROM uploads WHERE id=?', (result['uploadId'],)).fetchone()
            meta = json.loads(row['meta']); meta['references'] = refs
            db.execute('UPDATE uploads SET meta=? WHERE id=?', (json.dumps(meta), result['uploadId']))
        return result


def repository_store(repo):
    return Store(common_dir(repo) / 'projectmind-worklog-github' / 'records.sqlite3')
