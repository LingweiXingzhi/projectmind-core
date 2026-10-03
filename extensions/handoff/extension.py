"""Independently owned HTTP adapter for the D handoff draft."""
from http import HTTPStatus
import subprocess
from extension_host import ExtensionError
from extensions.handoff.handoff import HandoffError, SHA, build_handoff, render_markdown, render_ai_context

EXTENSION = {'title': '交接包', 'description': '把同一版本的项目证据整理给下一位队友或 AI。'}
CORE_SOURCE = 'https://github.com/LingweiXingzhi/projectmind-core'


def main_revision(context):
    """Resolve the locally fetched remote tracking ref, without network access."""
    try:
        result = subprocess.run(['git', '-C', str(context.repo), 'rev-parse', '--verify',
                                 'refs/remotes/origin/main^{commit}'], capture_output=True,
                                text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HandoffError('无法读取本机 origin/main，请检查 Git 仓库') from exc
    revision = result.stdout.strip()
    if result.returncode or not SHA.fullmatch(revision):
        raise HandoffError('本机没有 origin/main，请在 GitHub Desktop 执行 Fetch origin 后重试')
    return revision


def handle(context, method, data):
    try:
        if method == 'GET':
            try:
                revision, error = main_revision(context), ''
            except HandoffError as exc:
                revision, error = None, str(exc)
            return {'defaultSource': CORE_SOURCE, 'mainRevision': revision, 'mainError': error,
                    'mainNote': '使用本机已取得的 origin/main；需要最新版本时先执行 Fetch origin。'}
        if method != 'POST':
            raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, '请使用 GET 或 POST')
        if not isinstance(data, dict):
            raise HandoffError('交接请求必须为 JSON 对象')
        snapshot = context.snapshot()
        if data.get('expectedRevision') != snapshot['revision']:
            raise HandoffError('代码版本已变化或未提供预期版本，请刷新页面')
        mode = data.get('comparisonMode', 'custom')
        if mode not in ('custom', 'main'):
            raise HandoffError('比较方式须为 custom 或 main')
        base = data.get('baseRevision')
        if mode == 'main':
            if base is not None:
                raise HandoffError('对比 main 时不能同时指定其他基准')
            base = main_revision(context)
        if base is not None and (not isinstance(base, str) or not SHA.fullmatch(base)):
            raise HandoffError('基准提交须为完整 SHA，或省略')
        comparison = context.compare(base, snapshot['revision']) if base else None
        result = build_handoff(snapshot, data.get('sourceLocator'), comparison,
                               data.get('aiCandidates'), data.get('workNotes'))
        if mode == 'main':
            result['comparisonSource'] = 'refs/remotes/origin/main（本机已取得的版本，生成时解析）'
        return {'handoff': result, 'markdown': render_markdown(result), 'aiContext': render_ai_context(result)}
    except (HandoffError, KeyError, TypeError, ValueError) as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
