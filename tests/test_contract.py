"""Acceptance and contract tests.

Two regressions from v1 are locked down here:
* every tool answers with a JSON object (v1 returned bare lists, which the MCP
  layer rejects with "Handler returned an invalid result");
* the response fields the handlers read still exist on the installed client models
  (v1 guessed camelCase paths and three tools silently returned ``[]``).
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

import pytest
from mcp.types import CallToolRequestParams
from mcp_types import methods as _methods

from mcp_deezer import catalog, server

PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"]

CLIENT_METHODS = [
    "get_me",
    "search",
    "get_track",
    "get_artist",
    "get_album",
    "get_playlist",
    "get_charts",
    "get_similar_tracks",
    "get_similar_artists",
    "get_flow",
    "get_recommendations",
    "get_recently_played",
    "get_user_charts",
    "get_favorite_tracks",
    "get_favorite_albums",
    "get_favorite_artists",
    "get_favorite_playlists",
    "get_user_playlists",
    "add_track_to_favorite",
    "remove_track_from_favorite",
    "add_album_to_favorite",
    "remove_album_from_favorite",
    "add_artist_to_favorite",
    "remove_artist_from_favorite",
    "add_playlist_to_favorite",
    "remove_playlist_from_favorite",
    "create_playlist",
    "update_playlist",
    "delete_playlist",
    "add_tracks_to_playlist",
    "remove_tracks_from_playlist",
]

# tool -> (generated module, model class, field the handler reads)
RESPONSE_FIELDS = {
    "get_me": ("get_me", "GetMeMe", "id"),
    "search": ("search", "SearchSearch", "results"),
    "get_track": ("get_track", "GetTrackTrack", "lyrics"),
    "get_artist": ("get_artist", "GetArtistArtist", "top_tracks"),
    "get_album": ("get_album", "GetAlbumAlbum", "tracks"),
    "get_playlist": ("get_playlist", "GetPlaylistPlaylist", "tracks"),
    "get_charts": ("get_charts", "GetChartsCharts", "country"),
    "get_similar_tracks": ("get_similar_tracks", "GetSimilarTracksTrack", "recommended_tracks"),
    "get_similar_artists": ("get_similar_artists", "GetSimilarArtistsArtist", "related_artist"),
    "get_flow": ("get_flow", "GetFlowMe", "flow"),
    "get_recommendations": ("get_recommendations", "GetRecommendationsMe", "recommendations"),
    "get_recently_played": ("get_recently_played", "GetRecentlyPlayedMe", "recently_played"),
    "get_user_charts": ("get_user_charts", "GetUserChartsMe", "charts"),
    "get_favorite_tracks": ("get_favorite_tracks", "GetFavoriteTracksMe", "user_favorites"),
    "get_user_playlists": ("get_user_playlists", "GetUserPlaylistsMe", "playlists"),
}


class EmptyClient:
    """Answers None to everything: handlers must degrade to an object or a clean error."""

    def __getattr__(self, _name: str):
        async def method(**_kwargs: Any) -> None:
            return None

        return method


def _dummy_args(spec: catalog.ToolSpec) -> dict:
    props = spec.tool.input_schema.get("properties", {})
    args: dict[str, Any] = {}
    for name in spec.tool.input_schema.get("required", []):
        kind = props.get(name, {}).get("type")
        args[name] = {"array": ["1"], "integer": 1, "boolean": True}.get(kind, "1")
    return args


def _factory(client: Any):
    async def get_client():
        return client

    return get_client


@pytest.mark.parametrize("spec", catalog.visible_specs(), ids=lambda spec: spec.tool.name)
def test_every_tool_answers_with_a_serializable_object(spec, monkeypatch):
    monkeypatch.setattr(server, "get_client", _factory(EmptyClient()))

    result = asyncio.run(
        server._handle_call_tool(
            None,
            CallToolRequestParams(name=spec.tool.name, arguments=_dummy_args(spec)),
        )
    )

    if not result.is_error:
        assert isinstance(result.structured_content, dict), (
            f"{spec.tool.name} returned a bare {type(result.structured_content).__name__}: "
            "structuredContent must be an object"
        )
    dumped = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    for version in PROTOCOL_VERSIONS:
        _methods.serialize_server_result("tools/call", version, dumped)


def test_all_client_methods_used_exist():
    from deezer_python_gql import DeezerGQLClient

    missing = [name for name in CLIENT_METHODS if not hasattr(DeezerGQLClient, name)]

    assert missing == [], f"Deezer client methods disappeared: {missing}"


@pytest.mark.parametrize("tool,module,model,field", [(k, *v) for k, v in RESPONSE_FIELDS.items()])
def test_response_fields_still_exist(tool, module, model, field):
    generated = importlib.import_module(f"deezer_python_gql.generated.{module}")
    klass = getattr(generated, model)

    assert field in klass.model_fields, (
        f"{tool} reads {model}.{field}, which no longer exists — "
        "adapt the handler to the new client models"
    )
