"""Shared helper for HTTP tests: establish a real workbench write session.

The public write seam (D-A-02) requires a server-issued session cookie plus the
matching anti-forgery header on every POST under /api/archloop/. Tests that
exercise the real user path must therefore bootstrap a session exactly like the
browser does — this helper does only that, over real HTTP.
"""
from __future__ import annotations

import json
import urllib.request
from http.cookies import SimpleCookie
from urllib.parse import quote

from archloop.web_session import CSRF_HEADER, SESSION_COOKIE


def establish_session(base_url: str, *, origin: str | None = None,
                      operator: str | None = None) -> tuple[str | None, str | None]:
    """Return (cookie_header, csrf_token) for a live server-side session."""
    url = base_url.rstrip("/") + "/api/archloop/session"
    if operator:
        url += "?operator=" + quote(operator)
    request = urllib.request.Request(url, method="GET")
    request.add_header("Origin", origin or base_url.rstrip("/"))
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
        raw = response.headers.get("Set-Cookie") or ""
    jar = SimpleCookie()
    jar.load(raw)
    cookie = None
    if SESSION_COOKIE in jar:
        cookie = f"{SESSION_COOKIE}={jar[SESSION_COOKIE].value}"
    return cookie, body.get("csrfToken")


def session_headers(cookie: str | None, csrf: str | None, origin: str) -> dict:
    headers = {"Origin": origin}
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers[CSRF_HEADER] = csrf
    return headers


__all__ = ["establish_session", "session_headers"]