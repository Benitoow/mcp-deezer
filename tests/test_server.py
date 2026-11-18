from __future__ import annotations

import asyncio
import json

from mcp.types import CallToolRequestParams

from mcp_deezer import catalog, server
from mcp_deezer.catalog import ToolSpec
from tests.fakes import FakeClient, connection, playlist_payload


def _factory(client):
    async def get_client():
        return client

    return get_client


def call(name: str, arguments: dict, client: FakeClient, monkeypatch) -> object:
    monkeypatch.setattr(server, "get_client", _factory(client))
    return asyncio.run(
        server._handle_call_tool(None, CallToolRequestParams(name=name, arguments=arguments))
    )


def test_list_tools_exposes_the_catalog():
    result = asyncio.run(server._handle_list_tools(None, None))

    assert [tool.name for tool in result.tools] == [
        spec.tool.name for spec in catalog.visible_specs()
    ]
    assert all(tool.annotations is not None for tool in result.tools)


def test_unknown_tool_names_the_available_ones(monkeypatch):
    result = call("nope", {}, FakeClient(), monkeypatch)

    assert result.is_error is True
    assert "nope" in result.content[0].text
    assert "get_playlist" in result.content[0].text


def test_invalid_arguments_point_at_the_field(monkeypatch):
    result = call("search", {}, FakeClient(), monkeypatch)

    assert result.is_error is True
    assert "Invalid arguments for search" in result.content[0].text
    assert "query" in result.content[0].text


def test_invalid_id_pattern_is_rejected_by_the_schema(monkeypatch):
    result = call(
        "get_track", {"track_id": "https://deezer.com/track/1"}, FakeClient(), monkeypatch
    )

    assert result.is_error is True
    assert "track_id" in result.content[0].text


def test_successful_call_returns_compact_text_and_structured_content(monkeypatch):
    client = FakeClient({"get_user_playlists": {"playlists": connection([playlist_payload()])}})

    result = call("get_playlists", {}, client, monkeypatch)

    assert result.is_error is False
    text = result.content[0].text
    assert "\n" not in text  # compact JSON: no indentation to pay for twice
    assert json.loads(text) == result.structured_content
    assert result.structured_content["count"] == 1


def test_tool_errors_are_reported_with_a_hint(monkeypatch):
    client = FakeClient({"get_playlist": None})

    result = call("get_playlist", {"playlist_id": "9"}, client, monkeypatch)

    assert result.is_error is True
    assert "not found" in result.content[0].text


def test_read_only_mode_rejects_write_tools(monkeypatch):
    monkeypatch.setenv("DEEZER_READ_ONLY", "1")

    result = call(
        "delete_playlist", {"playlist_id": "9", "confirm": True}, FakeClient(), monkeypatch
    )

    assert result.is_error is True
    assert "disabled" in result.content[0].text


def test_non_object_handler_result_is_an_error_not_a_crash(monkeypatch):
    async def broken(_client, _args):
        return [{"id": "1"}]

    original = catalog.REGISTRY["get_me"]
    monkeypatch.setitem(
        catalog.REGISTRY,
        "get_me",
        ToolSpec(tool=original.tool, handler=broken, write=False),
    )

    result = call("get_me", {}, FakeClient(), monkeypatch)

    assert result.is_error is True
    assert "non-object" in result.content[0].text


def test_upstream_failure_is_reported_without_leaking_the_arl(monkeypatch):
    secret = "a" * 192
    monkeypatch.setenv("DEEZER_ARL", secret)

    class Boom(Exception):
        pass

    client = FakeClient({"get_me": Boom(f"request failed with {secret}")})

    result = call("get_me", {}, client, monkeypatch)

    assert result.is_error is True
    assert secret not in result.content[0].text
    assert "[REDACTED]" in result.content[0].text


def test_instructions_forbid_silent_deletions():
    assert "delete_playlist" in server.INSTRUCTIONS
    assert "confirm" in server.INSTRUCTIONS


def test_server_is_created_with_instructions_and_lifespan():
    instance = server.create_server()

    assert instance.name == "mcp-deezer"
