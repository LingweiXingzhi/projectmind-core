"""Explicit private data root; SQLite locks + transactions provide atomic CAS."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .errors import WorkspaceError, require
from .schema import canonical


class Store:
    def __init__(self, root):
        require(Path(root).is_absolute(), detail="数据根必须是显式绝对路径")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "workspace.sqlite3"
        require(not self.path.is_symlink(), detail="数据文件不能是符号链接")
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS documents "
                       "(kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, "
                       "PRIMARY KEY(kind,id))")
        os.chmod(self.path, 0o600)

    @contextmanager
    def transaction(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except sqlite3.Error as exc:
            if db and db.in_transaction:
                db.rollback()
            raise WorkspaceError("STORAGE_FAILED") from exc
        except BaseException:
            if db and db.in_transaction:
                db.rollback()
            raise
        finally:
            if db:
                db.close()

    @staticmethod
    def get(db, kind, key, optional=False):
        row = db.execute("SELECT body FROM documents WHERE kind=? AND id=?",
                         (kind, key)).fetchone()
        if row is None:
            require(optional, "NOT_FOUND")
            return None
        return json.loads(row[0])

    @staticmethod
    def put(db, kind, key, value, immutable=False):
        body = canonical(value)
        previous = Store.get(db, kind, key, optional=True)
        if immutable and previous is not None:
            require(canonical(previous) == body, "VERSION_CONFLICT")
            return
        db.execute("INSERT INTO documents VALUES(?,?,?) "
                   "ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body", (kind, key, body))
