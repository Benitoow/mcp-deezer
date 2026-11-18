"""End-to-end tests over a real MCP transport (in-memory streams).

These are the tests that would have caught the v1 production bug: a list-returning
tool was rejected by the MCP layer with "Handler returned an invalid result", so ten
tools never worked for any client.
"""

from __future__ import annotations

import asyncio
from typing import Any

import anyio
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from mcp_deezer import server as server_module
from tests.fakes import FakeClient, connection, playlist_payload, track_payload


def _factory(client: FakeClient):
    async def get_client():
        return client

    return get_client


def _run(monkeypatch, scenario, client: FakeClient | None = None) -> Any:
    box: dict[str, Any] = {}

    async def main():
        server = server_module.create_server()
        async with create_client_server_memory_streams() as (client_streams, server_streams):

            async def serve():
                await server.run(*server_streams, server.create_initialization_options())

            async with anyio.create_task_group() as task_group:
                task_group.start_soon(serve)
                try:
                    async with ClientSession(*client_streams) as session:
                        await session.initialize()
                        box["result"] = await scenario(session)
                finally:
                    task_group.cancel_scope.cancel()

    monkeypatch.setattr(server_module, "get_client", _factory(client or FakeClient()))
    asyncio.run(main())
    return box.get("result")


def test_list_tools_over_the_wire(monkeypatch):
    async def scenario(session):
        return await session.list_tools()

    result = _run(monkeypatch, scenario)

    names = [tool.name for tool in result.tools]
    assert len(names) == 21
    assert all(tool.annotations is not None for tool in result.tools)


def test_list_returning_tools_survive_the_protocol(monkeypatch):
    """v1 answered these with a bare list, which the MCP layer rejects."""

    async def scenario(session):
        results = {}
        for name in ("get_flow", "get_favorites", "get_playlists", "get_recently_played"):
            results[name] = await session.call_tool(name, {})
        return results

    client = FakeClient(
        {
            "get_flow": {"flow": {"tracks": [track_payload()]}},
            "get_favorite_tracks": {"user_favorites": {"tracks": connection([track_payload()])}},
            "get_user_playlists": {"playlists": connection([playlist_payload()])},
            "get_recently_played": {
                "recently_played": connection([{"typename__": "Album", "id": "9", "title": "X"}])
            },
        }
    )
    results = _run(monkeypatch, scenario, client)

    for name, result in results.items():
        assert not result.is_error, f"{name} failed: {result.content[0].text}"
        assert isinstance(result.structured_content, dict), name
        assert result.structured_content["count"] == 1, name


def test_unknown_tool_is_a_tool_error(monkeypatch):
    async def scenario(session):
        return await session.call_tool("nope", {})

    result = _run(monkeypatch, scenario)

    assert result.is_error is True


def test_read_only_mode_over_the_wire(monkeypatch):
    monkeypatch.setenv("DEEZER_READ_ONLY", "1")

    async def scenario(session):
        tools = await session.list_tools()
        call = await session.call_tool("delete_playlist", {"playlist_id": "9", "confirm": True})
        return tools, call

    tools, call = _run(monkeypatch, scenario)

    assert len(tools.tools) == 16
    assert "delete_playlist" not in [tool.name for tool in tools.tools]
    assert call.is_error is True


@pytest.mark.parametrize(
    "name,arguments", [("get_track", {"track_id": "1"}), ("search", {"query": "x"})]
)
def test_detail_tools_answer_over_the_wire(monkeypatch, name, arguments):
    async def scenario(session):
        return await session.call_tool(name, arguments)

    client = FakeClient(
        {
            "get_track": track_payload(),
            "search": {"results": {"tracks": connection([track_payload()])}},
        }
    )
    result = _run(monkeypatch, scenario, client)

    assert not result.is_error, result.content[0].text
    assert isinstance(result.structured_content, dict)
