"""Deterministic GitHub locators; no network access or remote status claims."""
import hashlib
import re
from urllib.parse import urlsplit, unquote
from extensions.worklog.store import text, fail


def references(values):
    if not isinstance(values, list) or len(values) > 30:
        fail('关联资料最多 30 项')
    result, seen = [], set()
    for raw in values:
        if not isinstance(raw, dict):
            fail('关联资料须为对象')
        url = text(raw.get('url'), 2000, 'GitHub 链接', True).strip()
        if any(ord(c) < 32 for c in url):
            fail('链接不能含控制字符')
        try:
            p = urlsplit(url)
            if p.scheme != 'https' or p.netloc.lower() != 'github.com' or p.query or p.username or p.password:
                raise ValueError()
            parts = p.path.strip('/').split('/')
            owner, repo, kind, target = parts[:4]
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', repo) or repo in ('.', '..'):
                raise ValueError()
            if kind in ('issues', 'pull'):
                if len(parts) != 4 or not re.fullmatch(r'[1-9][0-9]{0,9}', target) or p.fragment:
                    raise ValueError()
                category = 'issue' if kind == 'issues' else 'pr'
            elif kind in ('commit', 'blob'):
                if not re.fullmatch(r'[a-fA-F0-9]{40}', target):
                    fail('提交和源码链接请使用完整 40 位 SHA，避免分支移动后依据改变')
                target = target.lower()
                if kind == 'commit' and (len(parts) != 4 or p.fragment):
                    raise ValueError()
                if kind == 'blob':
                    if len(parts) < 5 or any(unquote(v) in ('', '.', '..') or '\\' in unquote(v) or '/' in unquote(v) for v in parts[4:]):
                        raise ValueError()
                    if p.fragment and not re.fullmatch(r'L[1-9][0-9]*(?:-L[1-9][0-9]*)?', p.fragment):
                        raise ValueError()
                category = 'commit' if kind == 'commit' else 'code'
            else:
                raise ValueError()
        except (ValueError, IndexError):
            fail('只接受 github.com 的 HTTPS Issue、PR、完整提交或固定版本源码链接')
        owner, repo = owner.lower(), repo.lower()
        canonical = f'https://github.com/{owner}/{repo}/{kind}/{target}'
        if category == 'code':
            canonical += '/' + '/'.join(parts[4:]) + ('#' + p.fragment if p.fragment else '')
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append({'id': hashlib.sha256(canonical.encode()).hexdigest(), 'url': canonical,
                       'repository': owner + '/' + repo, 'kind': category,
                       'revision': target if category in ('commit', 'code') else None,
                       'path': '/'.join(unquote(v) for v in parts[4:]) if category == 'code' else None,
                       'label': text(raw.get('label', ''), 200, '关联标题'),
                       'reason': text(raw.get('reason', ''), 1000, '关联说明'),
                       'status': 'user_link_unverified'})
    return result


def all_references(record):
    unique = {}
    for values in [record.get('references', [])] + [log.get('references', []) for log in record.get('logs', [])]:
        for item in references(values):
            unique.setdefault(item['id'], item)
    return list(unique.values())
