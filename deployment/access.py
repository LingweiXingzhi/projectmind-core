"""Server accounts and bounded browser sessions; never trust forwarded identity."""
from dataclasses import dataclass
import hashlib
import hmac
from http.cookies import CookieError, SimpleCookie
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
import tempfile

from extensions.architecture_workspace.deployment_preflight import validate_origin

COOKIE = "__Host-projectmind"
ITERATIONS = 600_000
USER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


class AccessError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def check(condition, code="INVALID_INPUT", message="请求或配置无效", status=400):
    if not condition:
        raise AccessError(status, code, message)


def _outside_git(path):
    raw = Path(path)
    check(raw.is_absolute() and not raw.is_symlink())
    result = raw.resolve()
    check(not any((p / ".git").exists() for p in (result, *result.parents)),
          message="账号文件必须放在 Git 工作副本之外")
    return result


def password_record(password):
    check(isinstance(password, str) and 16 <= len(password) <= 1024,
          message="密码至少 16 个字符，最多 1024 个字符")
    salt = secrets.token_bytes(16)
    return {"salt": salt.hex(), "iterations": ITERATIONS,
            "hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()}


def create_account_file(path, username, password):
    """Explicit provisioning; never overwrite an existing account file."""
    check(os.name == "posix", message="公网部署目前要求 POSIX 文件权限；Windows 本地模式仍可用")
    check(isinstance(username, str) and USER.fullmatch(username))
    path = _outside_git(path)
    record = {"schemaVersion": "projectmind_accounts_v1", "users": {username: password_record(password)}}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle); handle.write("\n")


def add_account(path, username, password):
    """Administrator-only atomic add; existing users/hashes stay unchanged."""
    check(os.name == "posix", message="公网账号维护目前要求 POSIX 文件权限")
    check(isinstance(username, str) and USER.fullmatch(username))
    path = _outside_git(path)
    lock = path.with_name(path.name + ".lock")
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    temporary = None
    try:
        users = load_accounts(path)
        check(username not in users and len(users) < 64, message="账号已存在或数量已达上限")
        users[username] = password_record(password)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".accounts-", delete=False) as file:
            temporary = Path(file.name)
            json.dump({"schemaVersion": "projectmind_accounts_v1", "users": users}, file)
            file.write("\n"); file.flush(); os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()
        lock.unlink()


def load_accounts(path):
    path = _outside_git(path)
    check(path.is_file() and path.stat().st_size <= 65536, message="需要有效的独立账号文件")
    check(os.name == "nt" or path.stat().st_mode & 0o077 == 0,
          message="账号文件权限必须为 0600")
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    check(isinstance(value, dict) and set(value) == {"schemaVersion", "users"}
          and value["schemaVersion"] == "projectmind_accounts_v1")
    users = value["users"]
    check(isinstance(users, dict) and 1 <= len(users) <= 64)
    for name, record in users.items():
        check(USER.fullmatch(name) and isinstance(record, dict)
              and set(record) == {"salt", "iterations", "hash"})
        check(type(record["iterations"]) is int and record["iterations"] == ITERATIONS
              and isinstance(record["salt"], str) and re.fullmatch(r"[0-9a-f]{32}", record["salt"])
              and isinstance(record["hash"], str) and re.fullmatch(r"[0-9a-f]{64}", record["hash"]))
    return users


@dataclass(frozen=True)
class BrowserSession:
    actor: str
    binding: str
    csrf: str
    expires: float


class PublicAccess:
    def __init__(self, origin, accounts, *, max_sessions=128, ttl=3600, clock=time.time):
        check(os.name == "posix", message="公网部署目前要求 POSIX 文件权限")
        parsed = validate_origin(origin, public=True)
        check(type(max_sessions) is int and max_sessions > 0 and 0 < ttl <= 3600)
        self.origin, self.host, self.users = origin, parsed.netloc, load_accounts(accounts)
        self.max_sessions, self.ttl, self.clock = max_sessions, ttl, clock
        self.sessions, self.attempts, self.lock = {}, {}, threading.RLock()
        self.dummy = password_record(secrets.token_urlsafe(32))

    def transport(self, environ, *, write=False):
        try:
            local = ipaddress.ip_address(environ.get("REMOTE_ADDR", "")).is_loopback
        except ValueError:
            local = False
        check(local and environ.get("HTTP_HOST") == self.host,
              "FORBIDDEN_HOST", "只接受配置的 HTTPS 入口经本机代理访问", 403)
        origin = environ.get("HTTP_ORIGIN")
        check(origin == self.origin if write else origin in (None, self.origin),
              "FORBIDDEN_ORIGIN", "请求来源与 HTTPS 入口不同", 403)

    def _prune(self, now):
        for sid in [sid for sid, value in self.sessions.items() if value.expires <= now]:
            del self.sessions[sid]
        for name in list(self.attempts):
            self.attempts[name] = [t for t in self.attempts[name] if now - t < 60]
            if not self.attempts[name]:
                del self.attempts[name]

    def login(self, username, password):
        check(isinstance(username, str) and isinstance(password, str)
              and len(username) <= 64 and len(password) <= 1024)
        with self.lock:
            now = self.clock(); self._prune(now)
            bucket = username if username in self.users else "<unknown>"
            attempts = self.attempts.setdefault(bucket, [])
            check(len(attempts) < 10, "LOGIN_RATE_LIMIT", "登录尝试过多，请稍后重试", 429)
            attempts.append(now)
            record = self.users.get(username, self.dummy)
            hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(record["salt"]),
                                         record["iterations"]).hex()
            check(hmac.compare_digest(hashed, record["hash"]) and username in self.users,
                  "LOGIN_FAILED", "用户名或密码错误", 401)
            self.attempts.pop(bucket, None)
            check(len(self.sessions) < self.max_sessions, "SESSION_CAPACITY", "会话已达容量上限", 429)
            sid = secrets.token_urlsafe(32)
            check(sid not in self.sessions, "SESSION_CAPACITY", "请重试", 429)
            session = BrowserSession(username, hashlib.sha256(sid.encode()).hexdigest(),
                                     secrets.token_urlsafe(32), now + self.ttl)
            self.sessions[sid] = session
            return sid, session

    def session(self, environ, *, write=False):
        raw = environ.get("HTTP_COOKIE", "")
        check(isinstance(raw, str) and len(raw) <= 8192 and raw.count(COOKIE + "=") == 1,
              "LOGIN_REQUIRED", "请先登录", 401)
        cookie = SimpleCookie()
        try:
            cookie.load(raw); sid = cookie[COOKIE].value
        except (KeyError, ValueError, CookieError):
            raise AccessError(401, "LOGIN_REQUIRED", "请先登录") from None
        check(TOKEN.fullmatch(sid), "LOGIN_REQUIRED", "请先登录", 401)
        with self.lock:
            self._prune(self.clock()); session = self.sessions.get(sid)
        check(session is not None, "LOGIN_REQUIRED", "会话过期，请重新登录", 401)
        if write:
            csrf = environ.get("HTTP_X_PROJECTMIND_CSRF", "")
            check(isinstance(csrf, str) and csrf.isascii() and hmac.compare_digest(csrf, session.csrf),
                  "CSRF_REQUIRED", "防伪令牌无效，请刷新页面", 403)
        return session

    def logout(self, environ):
        self.session(environ, write=True)
        cookie = SimpleCookie(); cookie.load(environ["HTTP_COOKIE"])
        with self.lock:
            self.sessions.pop(cookie[COOKIE].value, None)

    def cookie(self, sid=None):
        return (f"{COOKIE}={sid or ''}; Path=/; Secure; HttpOnly; SameSite=Strict; "
                f"Max-Age={int(self.ttl) if sid else 0}")
