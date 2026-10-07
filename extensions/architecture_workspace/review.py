"""Trusted local UI boundary. Candidate workers receive WorkspaceService only.

A creates local operator sessions and forwards real peer/Host/Origin/header
values here. Never accept these values from request JSON. This is local session
protection, not authentication against another process owned by the same user.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import time
from urllib.parse import urlsplit

from .errors import require
from .schema import text
from .service import token_hash
from .storage import Store


class HumanReviewGateway:
    def __init__(self, service, allowed_origin):
        parsed = urlsplit(allowed_origin)
        require(parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "::1", "localhost")
                and parsed.port and not parsed.path and not parsed.query and not parsed.fragment)
        self.service = service
        self.origin = allowed_origin
        self.host = parsed.netloc
        self.sessions = {}

    def _request(self, *, peer, host, origin):
        try:
            local = ipaddress.ip_address(peer).is_loopback
        except (TypeError, ValueError):
            local = False
        require(local and host == self.host and origin == self.origin, "REQUEST_FORBIDDEN")

    def create_session(self, actor, *, peer, host, origin):
        self._request(peer=peer, host=host, origin=origin)
        text(actor)
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.sessions[sid] = {"actor": actor, "csrf": csrf, "expires": time.time() + 3600}
        return {"sessionId": sid, "csrfToken": csrf}

    def _session(self, *, session_id, csrf_token, peer, host, origin):
        self._request(peer=peer, host=host, origin=origin)
        require(isinstance(session_id, str), "REQUEST_FORBIDDEN")
        session = self.sessions.get(session_id)
        require(session is not None and time.time() < session["expires"]
                and isinstance(csrf_token, str) and hmac.compare_digest(csrf_token, session["csrf"]),
                "REQUEST_FORBIDDEN")
        return session

    def preview_review(self, draft_id, *, auth, **request):
        session = self._session(**auth)
        require("actor" not in request, "REQUEST_FORBIDDEN")
        result = self.service._preview(draft_id, actor=session["actor"], **request)
        with self.service.store.transaction() as db:
            key = token_hash(result["confirmationToken"])
            intent = Store.get(db, "intent", key)
            intent["sessionBinding"] = hashlib.sha256(auth["session_id"].encode()).hexdigest()
            Store.put(db, "intent", key, intent)
        return result

    def confirm_review(self, draft_id, *, auth, **request):
        session = self._session(**auth)
        with self.service.store.transaction() as db:
            intent = Store.get(db, "intent", token_hash(request.get("confirmation_token")),
                               optional=True)
            require(intent is not None and intent["preview"]["actor"] == session["actor"]
                    and intent.get("sessionBinding") == hashlib.sha256(
                        auth["session_id"].encode()).hexdigest(), "REQUEST_FORBIDDEN")
        return self.service.record_review(draft_id, **request)
