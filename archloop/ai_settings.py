"""Private per-instance AI settings and persistent shared demonstration allowance.

No keys in responses, logs, Git or browser storage. Reserve before network;
unknown/failed usage keeps the reservation, including across service restarts.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
from urllib.parse import urlsplit
from .ai_transport import AIError


class SettingsError(AIError):
    def __init__(self, message, code="AI_SETTINGS_INVALID", status=400):
        super().__init__(message)
        self.code, self.status = code, status


def default_settings_path(data_root):
    identity = hashlib.sha256(str(Path(data_root).resolve()).encode()).hexdigest()[:20]
    return Path.home() / ".projectmind" / "instances" / identity / "ai.sqlite3"


class AISettings:
    def __init__(self, path, *, personal=False, allowed_hosts=None, shared_from_env=False):
        self.personal = personal
        self.shared_from_env = bool(shared_from_env and not personal)
        self.allowed_hosts = frozenset(allowed_hosts) if allowed_hosts is not None else None
        raw = Path(path)
        if not raw.is_absolute() or raw.is_symlink():
            raise SettingsError("AI 私有配置必须是独立的绝对路径。")
        self.path = raw.resolve()
        if any((p / ".git").exists() for p in (self.path, *self.path.parents)):
            raise SettingsError("AI 密钥和额度账本必须放在 Git 工作副本之外。")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix" and self.path.parent.stat().st_mode & 0o077:
            raise SettingsError("AI 私有配置目录权限需要为 0700。")
        if not self.path.exists():
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if not self.path.is_file() or self.path.is_symlink():
            raise SettingsError("AI 私有配置不是有效文件。")
        if os.name == "posix" and self.path.stat().st_mode & 0o077:
            raise SettingsError("AI 私有配置文件权限需要为 0600。")
        with self._database() as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL, token_limit INTEGER NOT NULL, output_limit INTEGER NOT NULL, charged INTEGER NOT NULL, reported INTEGER NOT NULL, estimated INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO settings VALUES (1, '{}', 50000, 2048, 0, 0, 0)")
            db.execute("CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, amount INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS preferences (identity TEXT PRIMARY KEY, mode TEXT NOT NULL)")

    def profile(self, identity):
        if not identity:
            raise SettingsError('请先建立浏览器会话。', 'FORBIDDEN_SESSION', 403)
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return AISettings(self.path.parent / 'personal' / (digest + '.sqlite3'), personal=True, allowed_hosts=self.allowed_hosts)

    def selected(self, identity):
        if not identity:
            return 'shared'
        with self._database() as db:
            row = db.execute('SELECT mode FROM preferences WHERE identity=?', (identity,)).fetchone()
        return row['mode'] if row else 'shared'

    def choose(self, identity, mode):
        if not identity or mode not in ('personal','shared'):
            raise SettingsError('请选择个人 API 或共享演示模式。')
        with self._database() as db:
            db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)', (identity, mode))

    @contextmanager
    def _database(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _row(self):
        with self._database() as db:
            return dict(db.execute("SELECT * FROM settings WHERE id=1").fetchone())

    def configuration(self, fallback):
        row = self._row()
        result = ({'key':'','model':'','base':'https://api.openai.com/v1','protocol':'auto'}
                  if self.personal else dict(fallback))
        if not self.shared_from_env:
            result.update(json.loads(row["config"]))
        result["outputLimit"] = row["output_limit"]
        return result

    def budget(self):
        with self._database() as db:
            row = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
            pending = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        return {"tokenLimit": row["token_limit"], "outputLimit": row["output_limit"],
                "chargedTokens": row["charged"], "reportedTokens": row["reported"],
                "estimatedTokens": row["estimated"],
                "remainingTokens": max(0, row["token_limit"] - row["charged"]),
                "pendingRequests": pending, "scope": "personal_profile" if self.personal else "shared_instance",
                "note": "共享演示额度；未返回可信用量的调用按预留额计入。不是供应商账单。"}

    def public(self, config, *, can_edit):
        result = {"canEdit": can_edit, "configured": config["configured"],
                  "model": config["model"], "provider": config["host"],
                  "protocol": config["protocol"], "budget": self.budget()}
        result['managedBy'] = 'server_environment' if self.shared_from_env else 'private_settings'
        if can_edit:
            result.update(baseUrl=config["base"], hasKey=bool(config["key"]))
        return result

    def authorize_provider(self, config):
        # Check again at call time: an administrator may revoke a domain
        # after this profile was saved. Reading it still permits correction.
        if self.personal and self.allowed_hosts is not None:
            parsed = urlsplit(config['base'])
            if parsed.scheme != 'https' or parsed.hostname not in self.allowed_hosts or parsed.port not in (None, 443):
                raise SettingsError('公网个人 API 仅支持运行者登记的 HTTPS 服务域名。请联系运行者登记你的服务。', 'AI_PROVIDER_NOT_ALLOWED', 403)

    def save(self, body, current):
        from .ai_transport import validate_config
        if self.shared_from_env:
            raise SettingsError('共享 API 由服务器环境变量或 Secrets 托管，不通过页面保存密钥。', 'AI_SETTINGS_FORBIDDEN', 403)
        if not isinstance(body, dict) or set(body) != {"baseUrl", "apiKey", "model", "protocol", "tokenLimit", "outputLimit"}:
            raise SettingsError("请填写服务地址、密钥、模型、协议和演示额度。")
        for key, maximum in (("baseUrl", 2048), ("apiKey", 4096), ("model", 200), ("protocol", 40)):
            if not isinstance(body[key], str) or len(body[key]) > maximum or any(ord(c) < 32 for c in body[key]):
                raise SettingsError("配置字段无效，请检查长度和换行。")
        limit, output = body["tokenLimit"], body["outputLimit"]
        if type(limit) is not int or not 1000 <= limit <= 1000000 or type(output) is not int or not 128 <= output <= 8192 or output > limit:
            raise SettingsError("演示总额度需为 1000–1000000 token，单次输出为 128–8192 且不超过总额度。")
        base = body["baseUrl"].strip().rstrip("/")
        key = body["apiKey"].strip()
        if not key:
            if base != current["base"]:
                raise SettingsError("更换服务地址时请重新填写密钥，避免把旧密钥发给另一服务。")
            key = current["key"]
        config = validate_config(key, body["model"].strip(), base, body["protocol"].strip())
        self.authorize_provider(config)
        if not config["configured"]:
            raise SettingsError("请填写 API 密钥和模型名称。")
        stored = {name: config[name] for name in ("key", "model", "base", "protocol")}
        with self._database() as db:
            charged = db.execute("SELECT charged FROM settings WHERE id=1").fetchone()[0]
            if limit < charged:
                raise SettingsError("总额度不能低于已经使用或预留的额度。调整配置不会清零用量。")
            db.execute("UPDATE settings SET config=?, token_limit=?, output_limit=? WHERE id=1",
                       (json.dumps(stored), limit, output))

    def reserve(self, amount):
        if type(amount) is not int or amount <= 0:
            raise SettingsError("AI 请求预算无效。")
        ticket = uuid.uuid4().hex
        with self._database() as db:
            row = db.execute("SELECT token_limit,charged FROM settings WHERE id=1").fetchone()
            if row["charged"] + amount > row["token_limit"]:
                raise SettingsError("演示额度不足以覆盖这次输入和输出。请缩短输入，或由运行者增加额度。", "AI_DEMO_LIMIT", 429)
            db.execute("UPDATE settings SET charged=charged+? WHERE id=1", (amount,))
            db.execute("INSERT INTO reservations VALUES (?,?)", (ticket, amount))
        return ticket

    def settle(self, ticket, actual):
        with self._database() as db:
            row = db.execute("SELECT amount FROM reservations WHERE id=?", (ticket,)).fetchone()
            if not row:
                return
            reserved = row["amount"]
            measured = type(actual) is int and actual > 0
            charge = actual if measured else reserved
            column = "reported" if measured else "estimated"
            db.execute(f"UPDATE settings SET charged=charged+?, {column}={column}+? WHERE id=1",
                       (charge-reserved, charge))
            db.execute("DELETE FROM reservations WHERE id=?", (ticket,))
