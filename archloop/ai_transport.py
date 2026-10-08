"""Minimal reusable server-side AI transport (A role, public seam).

Extracted from app.py's explain path so C (map_proposal) and the workbench
generation can call the same configured model without copying Git-selection
rules or credentials. Configuration and exception semantics are preserved:
AIError on missing config / HTTP failure / transport failure / bad payload.
Keys stay on the server; nothing logs the key.

Provider support: the transport speaks two wire protocols and takes the
endpoint from server-side configuration only, so any provider that exposes an
OpenAI-compatible API can be used without code changes:

- `responses`        — OpenAI's Responses API (strict JSON schema enforced
                       server-side). Default for api.openai.com.
- `chat_completions` — the de-facto standard `/chat/completions` shape used by
                       DeepSeek, DashScope/Qwen (compatible-mode), Moonshot/
                       Kimi, Zhipu GLM (v4), OpenRouter, vLLM/Ollama/LM Studio
                       and OpenAI-compatible gateways. The JSON schema is
                       validated in-process, so a provider that ignores
                       `response_format` still cannot return a non-conforming
                       graph.

Environment (server-side only; a client can never choose a model or endpoint):

| variable | meaning |
| --- | --- |
| `PROJECTMIND_AI_API_KEY` or `OPENAI_API_KEY` | API key (never logged) |
| `PROJECTMIND_AI_MODEL` | model id, e.g. `deepseek-chat`, `qwen-plus`, `kimi-k2.6`, `gpt-4o-mini` |
| `PROJECTMIND_AI_BASE_URL` | endpoint base, e.g. `https://api.deepseek.com/v1` |
| `PROJECTMIND_AI_PROTOCOL` | `auto` (default), `responses` or `chat_completions` |

`auto` uses `responses` for `api.openai.com` and `chat_completions` for every
other base URL. With no base URL set the OpenAI default is kept, so the
previous behaviour is unchanged.
"""
from __future__ import annotations

import json
import math
import ipaddress
import os
from http import HTTPStatus
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class AIError(Exception):
    """The configured AI transport could not produce a result."""


class AINotConfigured(AIError):
    """AI generation requested but no model is configured on the server."""


DEFAULT_BASE_URL = "https://api.openai.com/v1"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


# Keep a patchable network seam for existing protocol tests; real calls never
# forward the account credential or source context through an HTTP redirect.
urlopen = build_opener(_NoRedirect()).open
PROTOCOLS = ("auto", "responses", "chat_completions")
# the schema subset the project actually uses; an unknown keyword is a
# configuration error, not something to silently ignore
SUPPORTED_SCHEMA_KEYS = {"type", "properties", "required", "items", "enum",
                         "additionalProperties", "description", "minimum", "maximum",
                         "minItems", "maxItems"}
STRUCTURE_INSTRUCTION = (
    "\n\n只输出一个 JSON 对象（不要 markdown 代码块、不要解释文字），必须满足以下 JSON Schema：\n"
    "{schema}\n"
)


def ai_config() -> dict:
    """Server-side AI configuration (env only; validated, never echoed)."""
    key = (os.environ.get("PROJECTMIND_AI_API_KEY")
           or os.environ.get("OPENAI_API_KEY") or "").strip()
    model = os.environ.get("PROJECTMIND_AI_MODEL", "").strip()
    base = (os.environ.get("PROJECTMIND_AI_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
    protocol = (os.environ.get("PROJECTMIND_AI_PROTOCOL") or "auto").strip().lower()

    parts = urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.netloc or not parts.hostname:
        raise AIError("PROJECTMIND_AI_BASE_URL 必须是 http(s) 的绝对地址。")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise AIError("PROJECTMIND_AI_BASE_URL 不能包含凭据、查询或片段。")
    try:
        parts.port
        local = parts.hostname == 'localhost' or ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        local = False
        try:
            parts.port
        except ValueError:
            raise AIError('模型端点端口无效。') from None
    if parts.scheme == 'http' and not local:
        raise AIError('远程模型端点必须使用 HTTPS；HTTP 仅用于明确的本机服务。')
    if protocol not in PROTOCOLS:
        raise AIError(f"PROJECTMIND_AI_PROTOCOL 必须是 {PROTOCOLS} 之一。")
    if protocol == "auto":
        protocol = "responses" if parts.hostname == "api.openai.com" else "chat_completions"
    return {"key": key, "model": model, "base": base, "host": parts.hostname or "",
            "protocol": protocol, "configured": bool(key and model)}


def ai_status() -> dict:
    """Public AI status: what is configured and how to configure the rest.

    The key is never part of this payload; the endpoint host is shown so an
    operator can confirm which provider the server will call.
    """
    try:
        config = ai_config()
    except AIError as exc:
        return {"configured": False, "model": None, "protocol": None, "provider": None,
                "note": f"AI 配置无效：{exc}"}
    if not config["configured"]:
        return {"configured": False, "model": None, "protocol": config["protocol"],
                "provider": config["host"],
                "note": ("AI 生成尚未配置。需在启动程序前设置 OPENAI_API_KEY（或 "
                         "PROJECTMIND_AI_API_KEY）与 PROJECTMIND_AI_MODEL；"
                         "其他厂商用 PROJECTMIND_AI_BASE_URL 指向其兼容端点。")}
    return {"configured": True, "model": config["model"], "protocol": config["protocol"],
            "provider": config["host"],
            "note": (f"服务端已配置模型 {config['model']} @ {config['host']}"
                     f"（{config['protocol']}）；生成结果是待确认的 AI 候选。")}


def _schema_problems(value, schema, path: str = "$") -> list[str]:
    """Validate the project's schema subset in-process (both protocols).

    OpenAI's Responses API enforces the schema server-side; providers reached
    over chat/completions usually do not, so the transport validates the
    returned object itself instead of trusting `response_format`.
    """
    unknown = set(schema) - SUPPORTED_SCHEMA_KEYS
    if unknown:
        raise AIError(f"内部 schema 使用了不支持的校验关键字：{sorted(unknown)}")
    expected = schema.get("type")
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
    }
    if expected is not None and (not isinstance(expected, str) or expected not in checks):
        raise AIError('内部 schema 使用了不支持的类型。')
    if expected in checks and not checks[expected](value):
        return [f"{path}: 期望 {expected}，实际 {type(value).__name__}"]
    problems: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: 取值不在枚举 {schema['enum']} 内")
    if expected == "object":
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{path}.{name}: 缺少必填字段")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                problems.append(f"{path}: 出现未定义字段（{len(extra)} 个）")
        for name, sub in properties.items():
            if name in value:
                problems.extend(_schema_problems(value[name], sub, f"{path}.{name}"))
    elif expected == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            problems.append(f"{path}: 元素少于 {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            problems.append(f"{path}: 元素多于 {schema['maxItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                problems.extend(_schema_problems(item, item_schema, f"{path}[{index}]"))
    elif expected in ("integer", "number"):
        if isinstance(value, float) and not math.isfinite(value):
            return [f'{path}: 不允许非有限数值']
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: 小于最小值 {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: 大于最大值 {schema['maximum']}")
    return problems


def _validated(value, schema: dict) -> dict:
    problems = _schema_problems(value, schema)
    if problems:
        raise AIError("模型返回的内容不符合约定结构：" + "；".join(problems[:5]))
    return value


def _post_json(url: str, body: dict, key: str, timeout: int) -> dict:
    try:
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError):
        raise AIError('模型请求不是有效的 JSON 内容。') from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise AIError('模型请求超过当前 1 MiB 上限。')
    request = Request(url, data=encoded,
                      headers={"Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"},
                      method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            declared = (getattr(response, 'headers', {}) or {}).get('Content-Length')
            if declared and (not declared.isdecimal() or int(declared) > MAX_RESPONSE_BYTES):
                raise AIError('模型响应超过上限或长度无效。')
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise AIError('模型响应超过当前 2 MiB 上限。')
            value = json.loads(raw, parse_constant=_invalid_constant)
            if not isinstance(value, dict):
                raise AIError('模型响应必须是 JSON 对象。')
            return value
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise AIError(f"AI 服务返回 HTTP {code}。请检查模型、密钥、额度或端点地址。") from None
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise AIError("无法连接 AI 服务，请检查 PROJECTMIND_AI_BASE_URL 与网络后重试。") from exc
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise AIError('模型响应不是有效的 JSON 内容。') from None


def _invalid_constant(value):
    raise ValueError('non-finite JSON number')


def _payload_text(payload):
    try:
        return json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        raise AIError('模型输入不是有效的 JSON 内容。') from None


def _call_responses(config: dict, instructions: str, payload: dict,
                    schema_name: str, schema: dict, timeout: int) -> dict:
    body = {
        "model": config["model"],
        "store": False,
        "instructions": instructions,
        "input": _payload_text(payload),
        "text": {"format": {"type": "json_schema", "name": schema_name,
                            "strict": True, "schema": schema}},
    }
    raw = _post_json(config["base"] + "/responses", body, config["key"], timeout)
    if raw.get("status") != "completed":
        raise AIError("AI 服务未完成请求，请稍后重试。")
    output = raw.get('output')
    if not isinstance(output, list) or not all(isinstance(item, dict) for item in output):
        raise AIError('AI 服务返回的 output 结构无效。')
    texts = []
    for item in output:
        if item.get('type') != 'message':
            continue
        contents = item.get('content')
        if not isinstance(contents, list) or not all(isinstance(value, dict) for value in contents):
            raise AIError('AI 服务返回的消息结构无效。')
        for content in contents:
            if content.get('type') == 'output_text':
                if not isinstance(content.get('text'), str):
                    raise AIError('AI 服务返回的文字结构无效。')
                texts.append(content['text'])
    if not texts:
        raise AIError("AI 服务没有返回可用文字。")
    return _parse_json_text("".join(texts), schema)


def _call_chat_completions(config: dict, instructions: str, payload: dict,
                           schema_name: str, schema: dict, timeout: int) -> dict:
    structure = STRUCTURE_INSTRUCTION.format(
        schema=json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
    messages = [{"role": "system", "content": instructions + structure},
                {"role": "user", "content": _payload_text(payload)}]
    body = {"model": config["model"], "messages": messages, "stream": False,
            "response_format": {"type": "json_object"}}
    url = config["base"] + "/chat/completions"
    try:
        raw = _post_json(url, body, config["key"], timeout)
    except AIError as exc:
        # a bounded fallback: some compatible providers reject `response_format`
        # with HTTP 400. The structure is then enforced by the instruction and
        # by the in-process schema validation below, never by trust.
        if "HTTP 400" not in str(exc):
            raise
        body.pop("response_format", None)
        raw = _post_json(url, body, config["key"], timeout)
    choices = raw.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) \
            or not isinstance(choices[0].get('message'), dict):
        raise AIError('AI 服务返回的 choices/message 结构无效。')
    text = choices[0]['message'].get('content')
    if not isinstance(text, str) or not text.strip():
        raise AIError("AI 服务没有返回可用文字。")
    return _parse_json_text(text, schema)


def _parse_json_text(text: str, schema: dict) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # tolerate a fenced block, which compatible providers still emit
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()
    try:
        value = json.loads(cleaned, parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise AIError("AI 服务返回了无法读取的内容。") from exc
    if not isinstance(value, dict):
        raise AIError("AI 服务返回了无法读取的内容。")
    return _validated(value, schema)


def call_model(instructions: str, payload: dict, schema_name: str, schema: dict,
               timeout: int = 60) -> dict:
    """Send one bounded JSON request to the configured provider."""
    config = ai_config()
    if not config["configured"]:
        raise AINotConfigured("AI 生成尚未配置。")
    if config["protocol"] == "responses":
        return _call_responses(config, instructions, payload, schema_name, schema, timeout)
    return _call_chat_completions(config, instructions, payload, schema_name, schema, timeout)


__all__ = ["AIError", "AINotConfigured", "ai_config", "ai_status", "call_model",
           "DEFAULT_BASE_URL", "PROTOCOLS", "HTTPStatus"]
