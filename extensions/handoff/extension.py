"""Independently owned HTTP adapter for the D handoff draft."""
from http import HTTPStatus
from extension_host import ExtensionError
from extensions.handoff.handoff import HandoffError, build_handoff, render_markdown

EXTENSION = {'title': '交接包', 'description': '把同一版本的项目证据整理给下一位队友或 AI。'}


def handle(context, method, data):
    if method != 'POST':
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, '请使用 POST 并明确提供仓库来源')
    try:
        snapshot = context.snapshot()
        if data.get('expectedRevision') != snapshot['revision']:
            raise HandoffError('代码版本已变化或未提供预期版本，请刷新页面')
        base = data.get('baseRevision')
        if base is not None and (not isinstance(base, str) or not base):
            raise HandoffError('基准提交须为完整 SHA，或省略')
        comparison = context.compare(base, snapshot['revision']) if base else None
        result = build_handoff(snapshot, data.get('sourceLocator'), comparison, data.get('aiCandidates'))
        return {'handoff': result, 'markdown': render_markdown(result)}
    except (HandoffError, KeyError, TypeError, ValueError) as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
