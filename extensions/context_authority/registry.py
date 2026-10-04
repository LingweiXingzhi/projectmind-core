"""Claim registry: load/validate the append-only claims.jsonl.

The registry is the ONLY mutable data source of Context Authority.
CURRENT_STATE is always a derived view produced by resolver.resolve().
"""
from __future__ import annotations

import json
from pathlib import Path

from extensions.context_authority.schema import (
    normalize_claim,
    validate_claim,
)


class RegistryError(ValueError):
    """Structural registry problem (unreadable file, malformed JSONL)."""


class RegistryProblems:
    """Non-fatal problems that must surface in output, never be swallowed."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, kind: str, detail: str, **extra) -> None:
        self.items.append({"kind": kind, "detail": detail, **extra})

    def __len__(self) -> int:
        return len(self.items)


def validate_registry_claims(claims: list[dict]) -> list[dict]:
    """Enforce the registry boundary for direct resolver/tooling callers too."""
    if not isinstance(claims, list):
        raise RegistryError("claims must be a list")
    validated = []
    seen = set()
    for claim in claims:
        normalized = normalize_claim(validate_claim(claim))
        if normalized["id"] in seen:
            raise RegistryError(f"duplicate claim id {normalized['id']!r}")
        seen.add(normalized["id"])
        validated.append(normalized)
    return validated


def load_registry(path: Path, problems: RegistryProblems | None = None) -> list[dict]:
    """Load + validate claims.jsonl. Raises RegistryError for structural
    problems and ClaimValidationError (via validate_claim) for bad entries.
    Line order is irrelevant downstream (resolver sorts deterministically)."""
    if not path.is_file():
        raise RegistryError(f"claims registry not found: {path}")
    raw = path.read_text(encoding="utf-8")
    claims: list[dict] = []
    seen_ids: dict[str, int] = {}
    for lineno, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"line {lineno}: invalid JSON: {exc}") from exc
        try:
            claims.append(normalize_claim(validate_claim(obj)))
        except ValueError as exc:
            raise type(exc)(f"line {lineno}: {exc}") from exc
        cid = obj["id"]
        if cid in seen_ids:
            raise ValueError(
                f"line {lineno}: duplicate claim id {cid!r} "
                f"(first seen on line {seen_ids[cid]})")
        seen_ids[cid] = lineno
    return claims


def save_registry(path: Path, claims: list[dict]) -> None:
    """Append-only helper for tooling/tests; the server itself never writes."""
    claims = validate_registry_claims(claims)
    existing = load_registry(path) if path.exists() else []
    validate_registry_claims(existing + claims)
    payload = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
                      for c in claims)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
