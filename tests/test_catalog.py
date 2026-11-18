from __future__ import annotations

import pytest

from mcp_deezer import catalog


def test_catalog_is_complete_and_unique():
    names = [spec.tool.name for spec in catalog.REGISTRY.values()]

    assert len(names) == 21
    assert len(names) == len(set(names))


def test_every_tool_advertises_annotations_and_output_schema():
    for spec in catalog.REGISTRY.values():
        tool = spec.tool
        assert tool.annotations is not None, tool.name
        assert tool.title, tool.name
        assert tool.description, tool.name
        assert tool.output_schema is not None, tool.name
        # structuredContent must be an object, so every output schema is one.
        assert tool.output_schema["type"] == "object", tool.name
        assert tool.input_schema["type"] == "object", tool.name


def test_write_tools_are_flagged_and_destructive_ones_marked():
    writes = catalog.write_tool_names()

    assert writes == {
        "set_favorite",
        "edit_playlist_tracks",
        "create_playlist",
        "update_playlist",
        "delete_playlist",
    }
    for spec in catalog.REGISTRY.values():
        annotations = spec.tool.annotations
        assert annotations is not None
        if spec.write:
            assert annotations.read_only_hint is False, spec.tool.name
        else:
            assert annotations.read_only_hint is True, spec.tool.name

    for name in ("delete_playlist", "edit_playlist_tracks"):
        assert catalog.REGISTRY[name].tool.annotations.destructive_hint is True


def test_list_tools_all_return_pages():
    page_tools = {
        "get_charts",
        "get_similar_tracks",
        "get_similar_artists",
        "get_flow",
        "get_recently_played",
        "get_user_charts",
        "get_favorites",
        "get_playlists",
    }
    for name in page_tools:
        schema = catalog.REGISTRY[name].tool.output_schema
        assert schema["required"] == ["items", "count"], name


def test_read_only_mode_hides_write_tools(monkeypatch):
    monkeypatch.setenv("DEEZER_READ_ONLY", "1")

    names = [spec.tool.name for spec in catalog.visible_specs()]

    assert len(names) == 16
    assert "delete_playlist" not in names
    assert catalog.get_spec("delete_playlist") is None
    assert catalog.get_spec("get_playlist") is not None


@pytest.mark.parametrize(
    "tool_name",
    ["get_track", "get_album", "get_playlist", "search", "delete_playlist"],
)
def test_required_arguments_are_declared(tool_name):
    schema = catalog.REGISTRY[tool_name].tool.input_schema

    assert schema.get("required"), tool_name
    for required in schema["required"]:
        assert required in schema["properties"], (tool_name, required)
