import asyncio
import json

from mcp.types import CallToolRequestParams

from mcp_deezer import server as server_module


def test_tool_catalog_is_unique_and_complete():
    names = [tool.name for tool in server_module.TOOLS]

    assert len(names) == 29
    assert len(names) == len(set(names))
    assert set(names) == set(server_module.TOOLS_BY_NAME)


def test_nav_supports_nested_dicts_and_lists():
    payload = {"contributors": {"edges": [{"node": {"name": "Daft Punk"}}]}}

    assert server_module._nav(payload, "contributors", "edges", 0, "node", "name") == "Daft Punk"
    assert server_module._nav(payload, "contributors", "edges", 4, "node") is None
    assert server_module._nav(payload, "missing", default="fallback") == "fallback"


def test_server_registers_v2_tool_handlers():
    mcp_server = server_module.create_server()

    assert mcp_server.get_request_handler("tools/list") is not None
    assert mcp_server.get_request_handler("tools/call") is not None


def test_list_tools_handler_returns_catalog():
    result = asyncio.run(server_module._handle_list_tools(None, None))

    assert [tool.name for tool in result.tools] == [tool.name for tool in server_module.TOOLS]


def test_unknown_tool_is_reported_as_tool_error():
    params = CallToolRequestParams(name="does_not_exist", arguments={})

    result = asyncio.run(server_module._handle_call_tool(None, params))

    assert result.is_error is True
    assert result.content[0].text == "Unknown tool: does_not_exist"


def test_arguments_are_validated_before_deezer_auth():
    params = CallToolRequestParams(name="search", arguments={})

    result = asyncio.run(server_module._handle_call_tool(None, params))

    assert result.is_error is True
    assert "Invalid arguments for search" in result.content[0].text
    assert "query" in result.content[0].text


def test_missing_arl_is_returned_as_tool_error(monkeypatch):
    monkeypatch.delenv("DEEZER_ARL", raising=False)
    monkeypatch.setattr(server_module, "_client", None)
    params = CallToolRequestParams(name="get_me", arguments={})

    result = asyncio.run(server_module._handle_call_tool(None, params))

    assert result.is_error is True
    assert "DEEZER_ARL not set" in result.content[0].text


def test_successful_dispatch_has_text_and_structured_content(monkeypatch):
    async def fake_dispatch(name, arguments):
        return {"name": name, "arguments": arguments}

    monkeypatch.setattr(server_module, "_dispatch", fake_dispatch)
    params = CallToolRequestParams(name="search", arguments={"query": "Daft Punk"})

    result = asyncio.run(server_module._handle_call_tool(None, params))

    assert result.is_error is False
    assert result.structured_content == {"name": "search", "arguments": {"query": "Daft Punk"}}
    assert json.loads(result.content[0].text) == result.structured_content


def test_error_formatter_redacts_arl(monkeypatch):
    secret = "a" * 192
    monkeypatch.setenv("DEEZER_ARL", secret)

    message = server_module._safe_error_text(RuntimeError(f"request failed with {secret}"))

    assert secret not in message
    assert "[REDACTED]" in message
