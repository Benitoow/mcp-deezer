"""MCP server wiring: catalog exposure, dispatch, and graceful shutdown."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from jsonschema import ValidationError, validate
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from . import __version__, catalog, config, tools_read, tools_write  # noqa: F401  (importing them fills the registry)
from .client import close_client, get_client
from .errors import ToolError, error_text

logger = logging.getLogger("mcp_deezer")

INSTRUCTIONS = (
    "Unofficial Deezer server authenticated with an ARL session cookie from deezer.com.\n"
    '- Deezer ids are numeric strings (e.g. "3135556"), never URLs.\n'
    "- Read tools (get_*, search, get_lyrics) are safe and repeatable.\n"
    "- Write tools change the user's real account. Confirm with the user before "
    "set_favorite, create_playlist, update_playlist and edit_playlist_tracks; "
    "delete_playlist is irreversible and additionally requires confirm=true.\n"
    "- Every list tool answers {items, count, total, next_cursor}: pass next_cursor as "
    "`cursor` to page further.\n"
    "- get_recently_played returns what Deezer stores (album, playlist, artist, flow), "
    "not individual tracks."
)


def _serialize(payload: dict[str, Any]) -> str:
    """Compact JSON: the text block duplicates structuredContent, so whitespace costs twice."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _tool_result(payload: dict[str, Any]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=_serialize(payload))],
        structured_content=payload,
        is_error=False,
    )


def _tool_error(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], is_error=True)


async def _handle_list_tools(
    _ctx: ServerRequestContext,
    _params: PaginatedRequestParams | None,
) -> ListToolsResult:
    return ListToolsResult(tools=_visible_tools())


def _visible_tools() -> list[Tool]:
    return [spec.tool for spec in catalog.visible_specs()]


async def _handle_call_tool(
    _ctx: ServerRequestContext,
    params: CallToolRequestParams,
) -> CallToolResult:
    spec = catalog.get_spec(params.name)
    if spec is None:
        available = ", ".join(spec_.tool.name for spec_ in catalog.visible_specs())
        return _tool_error(f"Unknown or disabled tool: {params.name}. Available: {available}")

    arguments = params.arguments or {}
    try:
        validate(instance=arguments, schema=spec.tool.input_schema)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        where = f" at `{location}`" if location else ""
        return _tool_error(f"Invalid arguments for {params.name}{where}: {exc.message}")

    started = time.perf_counter()
    try:
        client = await get_client()
        payload: Any = await spec.handler(client, arguments)
    except ToolError as exc:
        logger.info("%s -> tool error: %s", params.name, exc)
        return _tool_error(str(exc))
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # upstream failure: report, never crash the server
        logger.warning(
            "tool %s failed: %s",
            params.name,
            error_text(exc),
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        return _tool_error(error_text(exc))

    logger.debug("%s -> %.0f ms", params.name, (time.perf_counter() - started) * 1000)
    if not isinstance(payload, dict):
        logger.error("tool %s returned %s, not a dict", params.name, type(payload).__name__)
        return _tool_error(f"Internal error: {params.name} produced a non-object result.")
    return _tool_result(payload)


@asynccontextmanager
async def _lifespan(_server: Server[Any]) -> AsyncIterator[dict[str, Any]]:
    if not (
        os.environ.get("DEEZER_ARL", "").strip() or os.environ.get("DEEZER_ARL_FILE", "").strip()
    ):
        logger.warning("DEEZER_ARL is not set: tools will fail until it is configured.")
    if config.read_only():
        logger.info("read-only mode: %d write tools hidden", len(catalog.write_tool_names()))
    try:
        yield {}
    finally:
        await close_client()
        logger.debug("mcp-deezer stopped")


def create_server() -> Server[Any]:
    return Server(
        "mcp-deezer",
        version=__version__,
        title="Deezer",
        description="Unofficial Deezer MCP server authenticated with an ARL session cookie.",
        instructions=INSTRUCTIONS,
        on_list_tools=_handle_list_tools,
        on_call_tool=_handle_call_tool,
        lifespan=_lifespan,
    )


async def main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=config.log_level(),
        format="%(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())


if __name__ == "__main__":
    run()
