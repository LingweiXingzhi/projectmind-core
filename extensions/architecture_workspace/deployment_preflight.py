"""Read-only deployment probes against an explicitly configured loopback service.

Public Host/Origin values are preserved for diagnosis. No approval, login,
writes, proxy rewrite, DNS lookup of the public domain or cloud deployment is
performed. A successful local read cannot establish public authentication.
"""
from __future__ import annotations

import argparse
from http.client import HTTPConnection, HTTPException
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .errors import WorkspaceError, require
from .surface_smoke import _new_root

MAX_RESPONSE = 64 * 1024
ENDPOINTS = ("/api/archloop", "/api/archloop/backend")
PUBLIC_ERROR_CODES = frozenset({"FORBIDDEN_HOST", "FORBIDDEN_ORIGIN", "BACKEND_UNAVAILABLE",
                               "NOT_FOUND", "VALIDATION_FAILED", "STORAGE_FAILED", "INTERNAL_ERROR"})


def validate_origin(value, *, public=False):
    require(isinstance(value, str) and 0 < len(value) <= 300)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise WorkspaceError("INVALID_INPUT", "来源地址格式错误") from exc
    require("@" not in parsed.netloc and not parsed.path
            and not parsed.query and not parsed.fragment
            and not any(ord(c) < 33 or ord(c) == 127 for c in value),
            detail="来源必须是准确的 scheme://host[:port]，不得含凭据、路径或控制字符")
    if public:
        require(parsed.scheme == "https" and isinstance(parsed.hostname, str),
                detail="公网入口必须为 HTTPS 来源")
        host = parsed.hostname
        require(host.isascii() and len(host) <= 253 and "." in host
                and all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                        for part in host.split(".")),
                detail="请使用完整 ASCII 域名；国际域名使用 punycode")
        require(host.lower() != "localhost" and not host.lower().endswith((".localhost", ".local")))
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise WorkspaceError("INVALID_INPUT", "此预检要求明确的 HTTPS 域名")
        require(port is None or 0 < port <= 65535)
        # Browser origins omit the default HTTPS port. Refuse ambiguous
        # noncanonical spelling rather than silently rewriting a boundary.
        require(port != 443, detail="HTTPS 默认端口请省略 :443")
    else:
        require(parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "::1")
                and port is not None and 0 < port <= 65535,
                detail="预检只连接显式的 loopback HTTP 服务和端口")
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    canonical = f"{parsed.scheme}://{hostname}" + (f":{port}" if port is not None else "")
    require(value == canonical, detail="来源需为浏览器使用的规范拼写：小写主机、无空端口或端口前导零")
    return parsed


def _metadata(path, status, body):
    """Never persist the raw response, model name, data root or grant fields."""
    value = {"path": path, "httpStatus": status, "jsonObject": isinstance(body, dict)}
    if not isinstance(body, dict):
        return value
    error = body.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        if isinstance(code, str) and code in PUBLIC_ERROR_CODES:
            value["errorCode"] = code
    if body.get("service") == "architecture-workbench":
        value["service"] = body["service"]
    generation = body.get("generation")
    if isinstance(generation, dict) and type(generation.get("configured")) is bool:
        value["aiConfiguredReported"] = generation["configured"]
    # Fixed A803c's backend_status exposes B under versionService.
    backend = body.get("versionService")
    if isinstance(backend, dict) and type(backend.get("available")) is bool:
        value["bAvailableReported"] = backend["available"]
    return value


def _probe(base, path, *, host, origin):
    connection = HTTPConnection(base.hostname, base.port, timeout=5)
    headers = {"Host": host, "Accept": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            return {"path": path, "httpStatus": response.status, "probeError": "RESPONSE_TOO_LARGE"}
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            return {"path": path, "httpStatus": response.status, "probeError": "INVALID_JSON"}
        return _metadata(path, response.status, body)
    except (OSError, HTTPException) as exc:
        return {"path": path, "probeError": type(exc).__name__}
    finally:
        connection.close()


def collect(base_url, public_origin):
    base = validate_origin(base_url)
    public = validate_origin(public_origin, public=True)
    variants = (
        ("configuredLoopbackOrigin", base.netloc, base_url),
        ("noBrowserOrigin", base.netloc, None),
        ("publicHostAndOrigin", public.netloc, public_origin),
        ("publicOriginWithLocalHost", base.netloc, public_origin),
    )
    observations = []
    for variant, host, origin in variants:
        for path in ENDPOINTS:
            observations.append({"variant": variant, **_probe(base, path, host=host, origin=origin)})
    blockers = [{"code": "PUBLIC_NETWORK_NOT_RUN",
                 "owner": "A/operations", "detail": "未连接公网域名；仅发送目标 Host/Origin 到本机服务"},
                {"code": "INGRESS_AUTH_NOT_VERIFIED",
                 "owner": "A", "detail": "本机读取成功不能证明公网登录、用户隔离或受信代理"},
                {"code": "PROXY_TLS_NOT_VERIFIED",
                 "owner": "A/operations", "detail": "未启动 HTTPS 终结入口或验证证书、转发边界"},
                {"code": "PUBLIC_REVIEW_NOT_RUN",
                 "owner": "A/B/D", "detail": "未进行真实远程会话、CSRF、人审与发布"}]
    for path in ENDPOINTS:
        local = next(o for o in observations
                     if o["path"] == path and o["variant"] == "configuredLoopbackOrigin")
        remote = next(o for o in observations
                      if o["path"] == path and o["variant"] == "publicHostAndOrigin")
        if local.get("httpStatus") != 200 or not local.get("jsonObject"):
            blockers.append({"code": "LOCAL_SERVICE_NOT_READY", "owner": "A",
                             "path": path, "detail": "本机基线接口未正常返回"})
        if remote.get("httpStatus") != 200:
            blockers.append({"code": "PUBLIC_ORIGIN_REJECTED", "owner": "A",
                             "path": path, "detail": "保持公网 Host/Origin 的请求未被当前服务接受"})
    return {"schemaVersion": "b_deployment_preflight_v1", "status": "NOT_READY_FOR_PUBLIC_DEPLOYMENT",
            "writePerformed": False, "networkScope": "explicit_loopback_only",
            "publicDomainResolved": False, "rawResponsesPersisted": False,
            "baseUrl": base_url, "targetPublicOrigin": public_origin,
            "observations": observations, "blockers": blockers,
            "limits": ["预检报告不是身份认证、TLS 或公网部署证明。",
                       "不修改 Host/Origin，不创建人审会话，不读环境密钥，不修改仓库或数据库。",
                       "即使目标头获得 200，也必须独立验证登录与跨用户/跨站/发布边界。"]}


def run(output, *, base_url, public_origin):
    # Validate before allocating output. The directory guard preserves any
    # existing checkout or evidence and does not label these reads human review.
    validate_origin(base_url)
    validate_origin(public_origin, public=True)
    try:
        root = _new_root(output, True)
        report = collect(base_url, public_origin)
        (root / "DEPLOYMENT_PREFLIGHT.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise WorkspaceError("STORAGE_FAILED", "无法创建或保存新的预检报告") from exc
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--public-origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.output, base_url=args.base_url, public_origin=args.public_origin)
    except WorkspaceError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps({"status": result["status"], "requests": len(result["observations"]),
                      "writePerformed": False}, ensure_ascii=False))
    raise SystemExit(2)  # Honest NOT_READY until real ingress/auth is separately verified.


if __name__ == "__main__":
    main()
