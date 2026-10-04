# -*- coding: utf-8 -*-
"""Map Proposal extension (Role C) — convergence handler seam (K01).

The handler keeps the registered route, the extension identity and the
ExtensionHost contract. All C logic lives in the single canonical scheduler
(engine.suggest_map); there is no second candidate engine and no shared
mutable request state between calls. Input errors are controlled rejections;
the legacy envelope is a projection of the canonical four-bucket result (K03).
"""

from http import HTTPStatus
from pathlib import Path

from extension_host import ExtensionError

from extensions.map_proposal import engine, model
from extensions.map_proposal.facts_adapter import FactsMismatch

EXTENSION = {
    "title": "项目地图提案 (Map Proposal)",
    "description": "基于 pinned Git diff、B 代码事实、当前人工地图与可选 Context Authority 底座，提出六类候选提案；不写正式地图。",
}


def handle(context, method: str, data: dict) -> dict:
    if method not in ("POST", "GET"):
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, "此扩展仅支持 POST 与 GET 请求")

    try:
        return engine.suggest_map(Path(context.repo), data or {})
    except (model.RequestError, FactsMismatch) as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
    except ValueError as exc:
        # Internal invariant violation (proposal shape, evidence kinds) must
        # not surface internals or secrets as a seemingly valid response.
        raise ExtensionError(HTTPStatus.INTERNAL_SERVER_ERROR, "候选发布不变式被违反") from exc
