"""Read-only legacy seam. A owns protected writes and the shared workspace UI."""
import os
from http import HTTPStatus

from extension_host import ExtensionError
from extensions.architecture_workspace.errors import WorkspaceError
from extensions.architecture_workspace.service import WorkspaceService

EXTENSION = {"title": "架构工作区", "description": "草稿、人审与版本；主工作台待接入"}


def handle(context, method, data):
    if method != "GET":
        raise ExtensionError(HTTPStatus.FORBIDDEN, "PUBLIC_ADAPTER_REQUIRED")
    if not isinstance(data, dict) or set(data) - {"workspaceId", "mapRevision"}:
        return WorkspaceError("INVALID_INPUT").as_dict()
    root = os.environ.get("PROJECTMIND_ARCHITECTURE_DATA_ROOT")
    if not root:
        return {"status": "integration_pending", "note": "尚未配置本机架构工作区",
                "writeStatus": "PUBLIC_ADAPTER_REQUIRED"}
    try:
        service = WorkspaceService(root, code_repositories=(context.repo,))
        workspace_id = data.get("workspaceId")
        if not workspace_id:
            return {"status": "ready", "writeStatus": "PUBLIC_ADAPTER_REQUIRED"}
        if data.get("mapRevision"):
            return service.get_version(workspace_id, data["mapRevision"])
        return service.graph_snapshot(workspace_id)
    except WorkspaceError as exc:
        return exc.as_dict()
