"""Argument coercion for tool handlers.

The JSON Schema already rejects malformed input; these helpers turn the remaining
bad values into :class:`ToolError` messages the agent can act on, instead of a
500-style traceback.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .config import DEFAULT_LIMIT, clamp_limit
from .errors import ToolError


def limit_of(args: dict[str, Any], default: int = DEFAULT_LIMIT) -> int:
    """Read the ``limit`` argument, clamped to the advertised bounds."""
    return clamp_limit(args.get("limit"), default)


def require_id(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key, "")).strip()
    if not value.isdigit():
        raise ToolError(f"`{key}` must be a Deezer numeric id, got {value!r}.")
    return value


def option_id(args: dict[str, Any], key: str) -> str | None:
    """Optional id parameter: absent/empty means "not provided"."""
    value = args.get(key)
    if value is None or str(value).strip() == "":
        return None
    return require_id(args, key)


def choice(args: dict[str, Any], key: str, allowed: Iterable[str], default: str) -> str:
    value = str(args.get(key, default) or default).strip().lower()
    options = tuple(allowed)
    if value not in options:
        raise ToolError(f"`{key}` must be one of: {', '.join(options)} (got {value!r}).")
    return value


def clean_ids(values: Any, key: str) -> list[str]:
    """Normalise a list of Deezer ids: strings, digits only, de-duplicated, order kept."""
    if values is None:
        return []
    if not isinstance(values, list) or not values:
        raise ToolError(f"`{key}` must be a non-empty array of Deezer track ids.")
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value.isdigit():
            raise ToolError(f"`{key}` contains a non-numeric id: {value!r}.")
        if value not in seen:
            seen.add(value)
            cleaned.append(value)
    return cleaned
