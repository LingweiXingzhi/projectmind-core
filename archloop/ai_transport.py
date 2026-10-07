"""Minimal reusable server-side AI transport (A role, public seam).

Extracted from app.py's explain path so C (map_proposal) and the workbench
generation can call the same configured model without copying Git-selection
rules or credentials. Configuration and exception semantics are preserved:
AIError on missing config / HTTP failure / transport failure / bad payload.
Keys stay on the server; nothing logs the key.
"""
from __future__ import annotations

import json
import os
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIError(Exception):
    """The configured AI transport could not produce a result."""


class AINotConfigured(AIError):
    """AI generation requested but no model is configured on the server."""


def ai_status() -> dict:
    model = os.environ.get("PROJECTMIND_AI_MODEL", "").strip()
    configured = bool(os.environ.get("OPENAI_API_KEY") and model)
    return {"configured": configured, "model": model if configured else None,
            "note": "服务端已配置模型；生成结果是待确认的 AI 候选。" if configured
                    else "AI 生成尚未配置。需在启动程序前设置 OPENAI_API_KEY 和 PROJECTMIND_AI_MODEL。"}


def call_model(instructions: str, payload: dict, schema_name: str, schema: dict,
               timeout: int = 60) -> dict:
    """Send one bounded JSON-schema request to the configured Responses API."""
    key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("PROJECTMIND_AI_MODEL", "").strip()
    if not key or not model:
        raise AINotConfigured("AI 生成尚未配置。")
    body = {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = json.load(response)
    except HTTPError as exc:
        raise AIError(f"AI 服务返回 HTTP {exc.code}。请检查模型、密钥或额度。") from exc
    except (URLError, TimeoutError) as exc:
        raise AIError("无法连接 AI 服务，请稍后重试。") from exc
    if raw.get("status") != "completed":
        raise AIError("AI 服务未完成请求，请稍后重试。")
    texts = [content.get("text", "") for item in raw.get("output", []) if item.get("type") == "message"
             for content in item.get("content", []) if content.get("type") == "output_text"]
    if not texts:
        raise AIError("AI 服务没有返回可用文字。")
    try:
        return json.loads("".join(texts))
    except json.JSONDecodeError as exc:
        raise AIError("AI 服务返回了无法读取的内容。") from exc


__all__ = ["AIError", "AINotConfigured", "ai_status", "call_model", "HTTPStatus"]
