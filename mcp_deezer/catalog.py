"""Tool catalog: JSON Schemas, MCP annotations and the handler registry.

Each tool declares its schema, its annotations *and* its handler in one place, so
the advertised surface cannot drift from the implementation (the v1 catalog and
the v1 dispatch were two hand-maintained lists, and they had diverged).

Only *input* schemas take part in validation; output schemas exist so clients can
verify ``structuredContent`` — every handler below returns a JSON object.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.types import Tool, ToolAnnotations

from . import config

Handler = Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool, its handler, and whether it mutates the account."""

    tool: Tool
    handler: Handler
    write: bool


REGISTRY: dict[str, ToolSpec] = {}

# ─── Reusable schema fragments ───────────────────────────────────────────────

ID = {
    "type": "string",
    "pattern": "^[0-9]+$",
    "description": "Deezer numeric id, not a URL.",
}
LIMIT = {
    "type": "integer",
    "minimum": 1,
    "maximum": config.MAX_LIMIT,
    "default": config.DEFAULT_LIMIT,
}
CURSOR = {
    "type": "string",
    "minLength": 1,
    "description": "Cursor from a previous `next_cursor`.",
}
TRACK_IDS = {
    "type": "array",
    "items": {"type": "string", "pattern": "^[0-9]+$"},
    "minItems": 1,
    "maxItems": config.MAX_LIMIT,
    "description": "Deezer track ids, batched internally.",
}

# Deliberately permissive and compact: tool definitions are paid for in every client's
# system prompt, and very few clients validate output schemas. The real shape is carried
# by `structuredContent`, and every handler is contract-tested to return an object.
OBJECT: dict[str, Any] = {"type": "object"}
PAGE: dict[str, Any] = {
    "type": "object",
    "properties": {"items": {"type": "array"}, "count": {"type": "integer"}},
    "required": ["items", "count"],
}


def object_schema(**_properties: Any) -> dict[str, Any]:
    """Permissive object schema; the payload shape is documented in the description."""
    return OBJECT


def ack_schema(**_properties: Any) -> dict[str, Any]:
    """Permissive object schema for mutation results."""
    return OBJECT


# ─── Registration ───────────────────────────────────────────────────────────


def register(
    *,
    name: str,
    title: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    read_only: bool = True,
    destructive: bool = False,
    idempotent: bool = False,
) -> Callable[[Handler], Handler]:
    """Register a handler and the MCP metadata that advertises it."""

    annotations = ToolAnnotations(
        title=title,
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=True,
    )

    def decorator(handler: Handler) -> Handler:
        if name in REGISTRY:  # pragma: no cover - developer error
            raise RuntimeError(f"duplicate tool name: {name}")
        REGISTRY[name] = ToolSpec(
            tool=Tool(
                name=name,
                title=title,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                annotations=annotations,
            ),
            handler=handler,
            write=not read_only,
        )
        return handler

    return decorator


def visible_specs() -> list[ToolSpec]:
    """Tools currently exposed, honouring ``DEEZER_READ_ONLY``."""
    allowed = config.read_only()
    return [spec for spec in REGISTRY.values() if not (allowed and spec.write)]


def get_spec(name: str) -> ToolSpec | None:
    """Look up a callable tool; a write tool is invisible in read-only mode."""
    spec = REGISTRY.get(name)
    if spec is None:
        return None
    if config.read_only() and spec.write:
        return None
    return spec


def write_tool_names() -> set[str]:
    return {name for name, spec in REGISTRY.items() if spec.write}
