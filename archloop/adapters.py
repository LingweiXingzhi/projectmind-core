"""Single adapter seam between the A workbench and B/C/D backends.

Production path: only registered real backends answer. When a backend is
missing the adapter raises BACKEND_UNAVAILABLE — a dev sample never silently
substitutes for AI output, persistence, review or handoff.

Dev path: callers may pass mode="dev_sample" to exercise the UI against the
labeled sample backend. Every sample response carries provenance markers
(`origin: "dev_sample"`, `labeled: "演示数据"`) and sample review/publish
operations are rejected at the adapter so no simulated human approval is
recorded anywhere.
"""
from __future__ import annotations

from .contract import ContractError

PRODUCTION_MODE = "production"
DEV_SAMPLE_MODE = "dev_sample"


class AdapterRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, dict] = {}

    def register(self, capability: str, backend: dict) -> None:
        if capability not in ("persistence", "proposal", "correction", "handoff"):
            raise ValueError(f"unknown adapter capability: {capability}")
        kind = backend.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError("backend needs a kind")
        self._backends[capability] = backend

    def unregister(self, capability: str) -> None:
        self._backends.pop(capability, None)

    def backend(self, capability: str, mode: str = PRODUCTION_MODE) -> dict:
        registered = self._backends.get(capability)
        if registered is not None:
            return registered
        if mode == DEV_SAMPLE_MODE:
            return {"kind": "dev_sample", "labeled": "演示数据", "origin": "dev_sample"}
        raise ContractError(
            "BACKEND_UNAVAILABLE",
            f"{capability} 后端尚未接入；生产路径不提供开发样例顶替。",
            {"capability": capability},
        )

    def listing(self) -> dict:
        return {
            "registered": {capability: backend.get("kind") for capability, backend in self._backends.items()},
            "modes": [PRODUCTION_MODE, DEV_SAMPLE_MODE],
        }


def reject_sample_review(operation: dict) -> None:
    """Review/publish may never run against a sample backend."""
    origin = operation.get("origin")
    if origin == "dev_sample":
        raise ContractError(
            "DEV_SAMPLE_DISABLED",
            "演示数据不能提交人审或发布版本；请接入真实后端后重试。",
        )


def call_backend(backend: dict, action: str, payload: dict) -> dict:
    """Invoke a registered real backend; failures stay machine-coded."""
    call = backend.get("call")
    if not callable(call):
        raise ContractError("BACKEND_UNAVAILABLE",
                            f"{backend.get('kind')} 后端没有可调用的处理接口")
    try:
        reply = call(action, payload)
    except ContractError:
        raise
    except Exception as exc:  # backend faults must not leak as 500s
        raise ContractError("BACKEND_UNAVAILABLE",
                            f"{backend.get('kind')} 后端调用失败：{type(exc).__name__}") from exc
    if not isinstance(reply, dict):
        raise ContractError("BACKEND_UNAVAILABLE",
                            f"{backend.get('kind')} 后端返回了非对象结果")
    return reply


__all__ = ["AdapterRegistry", "DEV_SAMPLE_MODE", "PRODUCTION_MODE", "call_backend", "reject_sample_review"]
