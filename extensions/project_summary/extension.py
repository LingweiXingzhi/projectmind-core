"""A working example of a separately owned extension."""

from http import HTTPStatus

from extension_host import ExtensionError


EXTENSION = {
    "title": "项目概况示例",
    "description": "演示独立目录如何读取当前快照并提供结果。",
}


def handle(context, method: str, data: dict) -> dict:
    if method != "GET":
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, "此扩展只支持 GET")
    snapshot = context.snapshot()
    return {
        "status": "curated_map_summary",
        "repository": snapshot["repository"],
        "revision": snapshot["revision"],
        "mapOrigin": snapshot["mapOrigin"],
        "nodeCount": len(snapshot["nodes"]),
        "edgeCount": len(snapshot["edges"]),
        "note": "这是扩展接入示例。节点和关系来自人工演示图，不代表自动识别或团队确认。",
    }
