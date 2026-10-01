"""ProjectMind extension adapter. Core routes remain owned by A."""
from http import HTTPStatus

from extension_host import ExtensionError
from extensions.code_facts.facts import CodeFactsError, collect_code_facts

EXTENSION = {"title": "代码事实", "description": "查看指定 Git 提交中的 Python 定义与位置"}


def handle(context, method: str, data: dict) -> dict:
    if method not in ("GET", "POST"):
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "只支持 GET 或 POST")
    if not isinstance(data, dict) or set(data) - {"revision", "paths"}:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "输入仅接受 revision 和可选 paths")
    paths = data.get("paths")
    if method == "GET":
        if paths is not None and not isinstance(paths, str):
            raise ExtensionError(HTTPStatus.BAD_REQUEST, "GET paths 须为换行分隔的字符串")
        paths = None if paths is None or paths == "" else paths.splitlines()
    try:
        return collect_code_facts(context.repo, data.get("revision"), paths)
    except CodeFactsError as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
