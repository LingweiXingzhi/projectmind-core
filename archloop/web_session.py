"""Loopback write sessions + CSRF for the public workbench write entries.

Every POST below /api/archloop/ must carry a live server-side session cookie
and the matching per-session anti-forgery header. The session is issued by the
server itself (`GET /api/archloop/session`): a request that merely omits
session/CSRF — a cross-site form, a bare script, a redirected browser — is
refused with a machine code before any service call, so it can never create
workspaces, apply operations, publish versions or start fix tasks.

The session also carries the *declared local operator* (本机操作者声明). It is
not an identity provider: the contract says the actor is an operator
declaration, so the server binds it to this session instead of trusting a
field inside the request body.
"""
from __future__ import annotations

import secrets
import threading
import time

from .contract import ContractError

SESSION_COOKIE = "pm_archloop_session"
CSRF_HEADER = "X-CSRF-Token"
DEFAULT_TTL_SECONDS = 1800
MAX_SESSIONS = 256
OPERATOR_LIMIT = 100


class WriteSessionRegistry:
    """Thread-safe in-memory sessions for one running server instance.

    Sessions are deliberately not persisted: a restart invalidates every
    outstanding write session and the next browser action re-issues one. That
    is the same boundary as the human-review session — no write authority
    survives the process it was granted by.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS,
                 max_sessions: int = MAX_SESSIONS) -> None:
        self._lock = threading.Lock()
        self._ttl = int(ttl_seconds)
        self._max = int(max_sessions)
        self._sessions: dict[str, dict] = {}

    def _prune(self, now: float) -> None:
        expired = [key for key, item in self._sessions.items()
                   if now - item["lastSeen"] > self._ttl]
        for key in expired:
            self._sessions.pop(key, None)

    def issue(self, operator: str = "", *, ai_profile: str | None = None) -> dict:
        """Create a server-side session and return its identifiers.

        The caller (app.py) puts the cookie on the response; only the CSRF
        token is echoed in the JSON body. The cookie is HttpOnly, so a script
        from another origin can neither read nor forge it.
        """
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            while len(self._sessions) >= self._max:
                oldest = min(self._sessions, key=lambda key: self._sessions[key]["lastSeen"])
                self._sessions.pop(oldest, None)
            session_id = secrets.token_urlsafe(24)
            csrf = secrets.token_urlsafe(24)
            declared = (operator or "").strip()[:OPERATOR_LIMIT]
            self._sessions[session_id] = {"csrf": csrf, "operator": declared,
                                          "aiProfile": ai_profile or secrets.token_urlsafe(24),
                                          "created": now, "lastSeen": now}
            return {"sessionId": session_id, "csrfToken": csrf,
                    "ttlSeconds": self._ttl, "operator": declared}

    def read(self, session_id: str | None) -> dict | None:
        """Server-side cookie lookup for private AI profile reads, not write authority."""
        with self._lock:
            self._prune(time.monotonic())
            item = self._sessions.get(session_id)
            return dict(item) if item else None

    def verify(self, session_id: str | None, csrf_token: str | None) -> dict:
        """Return the live session or refuse with a machine code."""
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            if not session_id or session_id not in self._sessions:
                raise ContractError(
                    "FORBIDDEN_SESSION",
                    "写入口需要服务端会话：先向 /api/archloop/session 建立本机会话",
                    {"header": CSRF_HEADER})
            item = self._sessions[session_id]
            if not isinstance(csrf_token, str) or not secrets.compare_digest(item["csrf"], csrf_token):
                raise ContractError(
                    "FORBIDDEN_CSRF",
                    "会话防伪令牌缺失或不匹配；跨站请求不能执行写操作",
                    {"header": CSRF_HEADER})
            item["lastSeen"] = now
            return dict(item)


def parse_session_cookie(cookie_header: str | None) -> str | None:
    """Extract the session id from a Cookie header (None when absent)."""
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == SESSION_COOKIE and value:
            return value
    return None


__all__ = ["WriteSessionRegistry", "parse_session_cookie", "SESSION_COOKIE", "CSRF_HEADER"]
