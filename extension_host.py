"""Small local seam for separately owned ProjectMind extension directories."""

from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Callable


ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


@dataclass(frozen=True)
class ExtensionContext:
    repo: Path
    map_path: Path
    snapshot: Callable[[], dict]
    compare: Callable[[str, str], dict]


class ExtensionError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class _LoadedExtension:
    title: str
    description: str
    handle: Callable[[ExtensionContext, str, dict], dict]
    page: Path | None


class ExtensionHost:
    """Load once at server creation; each extension owns its API and optional page."""

    def __init__(self, root: Path, context: ExtensionContext) -> None:
        self.context = context
        self.loaded: dict[str, _LoadedExtension] = {}
        self.unavailable: dict[str, str] = {}
        if not root.exists():
            return
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or folder.name.startswith(".") or folder.name == "__pycache__":
                continue
            identifier = folder.name
            if folder.is_symlink():
                self.unavailable[identifier] = "扩展目录不能是符号链接"
                continue
            if not ID_PATTERN.fullmatch(identifier):
                self.unavailable[identifier] = "目录名须为小写字母、数字或下划线，且以字母开头"
                continue
            source = folder / "extension.py"
            if source.is_symlink():
                self.unavailable[identifier] = "扩展代码不能是符号链接"
                continue
            if not source.is_file():
                self.unavailable[identifier] = "缺少 extension.py"
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"projectmind_extension_{identifier}", source)
                if spec is None or spec.loader is None:
                    raise ImportError("无法读取扩展模块")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                metadata = getattr(module, "EXTENSION", None)
                handle = getattr(module, "handle", None)
                if not isinstance(metadata, dict) or any(
                    not isinstance(metadata.get(key), str) or not metadata[key].strip()
                    for key in ("title", "description")
                ) or not callable(handle):
                    raise ValueError("需要 EXTENSION.title/description 和 handle(context, method, data)")
                page = folder / "index.html"
                self.loaded[identifier] = _LoadedExtension(
                    metadata["title"], metadata["description"], handle,
                    page if page.is_file() and not page.is_symlink() else None,
                )
            except (Exception, SystemExit) as exc:
                self.unavailable[identifier] = f"加载失败：{type(exc).__name__}"

    def listing(self) -> dict:
        entries = [
            {"id": identifier, "title": extension.title, "description": extension.description,
             "status": "ready", "pageUrl": f"/ext/{identifier}",
             "apiUrl": f"/api/extensions/{identifier}"}
            for identifier, extension in self.loaded.items()
        ]
        entries.extend(
            {"id": identifier, "status": "unavailable", "note": reason}
            for identifier, reason in self.unavailable.items()
        )
        return {"extensions": sorted(entries, key=lambda entry: entry["id"])}

    def get(self, identifier: str) -> _LoadedExtension:
        if identifier in self.unavailable:
            raise ExtensionError(HTTPStatus.SERVICE_UNAVAILABLE, self.unavailable[identifier])
        if identifier not in self.loaded:
            raise ExtensionError(HTTPStatus.NOT_FOUND, "扩展不存在")
        return self.loaded[identifier]

    def page(self, identifier: str, generic_page: Path) -> bytes:
        extension = self.get(identifier)
        return (extension.page or generic_page).read_bytes()

    def run(self, identifier: str, method: str, data: dict) -> dict:
        extension = self.get(identifier)
        try:
            result = extension.handle(self.context, method, data)
        except ExtensionError:
            raise
        except Exception as exc:
            raise ExtensionError(HTTPStatus.INTERNAL_SERVER_ERROR, "扩展运行失败") from exc
        if not isinstance(result, dict):
            raise ExtensionError(HTTPStatus.INTERNAL_SERVER_ERROR, "扩展必须返回 JSON 对象")
        try:
            json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ExtensionError(HTTPStatus.INTERNAL_SERVER_ERROR, "扩展结果无法编码为 JSON") from exc
        return result
