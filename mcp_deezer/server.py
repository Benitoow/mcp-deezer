"""Unofficial MCP server for Deezer account management via an ARL cookie.

Uses deezer-python-gql, an unofficial client for Deezer's internal GraphQL API.

Auth: Set DEEZER_ARL env var to your ARL cookie from deezer.com
"""

import asyncio
import json
import os
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

from mcp_deezer import __version__

_client = None


def _get_arl() -> str:
    arl = os.environ.get("DEEZER_ARL", "").strip()
    if not arl:
        raise RuntimeError(
            "DEEZER_ARL not set. Get your ARL cookie:\n"
            "1. Log into deezer.com → F12 → Application → Cookies → 'arl'\n"
            "2. Set DEEZER_ARL environment variable"
        )
    return arl


async def _get_client():
    global _client
    if _client is None:
        from deezer_python_gql import DeezerGQLClient

        _client = DeezerGQLClient(arl=_get_arl())
    return _client


# ─── Response helpers ────────────────────────────────────────────────────────


def _to_dict(obj: Any) -> Any:
    """Convert Pydantic models to plain dicts/lists."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _edges(d: Any) -> list[dict]:
    """Extract items from GraphQL edges/node pattern.
    Handles {"edges": [{"node": {...}}]} → [{...}]
    Falls back to flat list if no edges found.
    """
    if isinstance(d, list):
        return d
    if not isinstance(d, dict):
        return []
    edge_list = d.get("edges", [])
    if edge_list:
        return [e.get("node", e) for e in edge_list]
    items = d.get("data", d.get("items", []))
    return items if isinstance(items, list) else []


def _nav(obj: Any, *keys: str | int, default=None):
    """Navigate nested dictionaries and lists safely."""
    current = obj
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        elif isinstance(current, list) and isinstance(k, int) and -len(current) <= k < len(current):
            current = current[k]
        else:
            return default
        if current is None:
            return default
    return current


def _get_main_artist_name(track_node: dict) -> str | None:
    """Extract main artist name from track's contributors edges."""
    contribs = track_node.get("contributors", {})
    if not isinstance(contribs, dict):
        return None
    for edge in contribs.get("edges", []):
        roles = edge.get("roles", [])
        if "MAIN" in roles:
            return edge.get("node", {}).get("name")
    # Fallback: first contributor
    edges = contribs.get("edges", [])
    if edges:
        return edges[0].get("node", {}).get("name")
    return None


# ─── Compact formatters ──────────────────────────────────────────────────────


def _track(t: dict) -> dict:
    if not t:
        return t
    album = t.get("album")
    return {
        "id": t.get("id"),
        "title": t.get("title"),
        "artist": _get_main_artist_name(t),
        "album": (album.get("display_title") or album.get("title"))
        if isinstance(album, dict)
        else album,
        "duration": t.get("duration"),
        "link": t.get("link") or f"https://www.deezer.com/track/{t.get('id')}",
    }


def _artist(a: dict) -> dict:
    if not a:
        return a
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "nb_fan": a.get("nb_fan") or a.get("fans_count"),
        "link": a.get("link") or f"https://www.deezer.com/artist/{a.get('id')}",
    }


def _album(a: dict) -> dict:
    if not a:
        return a
    artist = a.get("artist") or _nav(a, "contributors", "edges", 0, "node")
    return {
        "id": a.get("id"),
        "title": a.get("title") or a.get("display_title"),
        "artist": artist.get("name") if isinstance(artist, dict) else artist,
        "nb_tracks": a.get("nb_tracks") or a.get("tracks_count"),
        "release_date": a.get("release_date"),
        "link": a.get("link")
        or (a.get("url", {}) or {}).get("web_url")
        or f"https://www.deezer.com/album/{a.get('id')}",
    }


def _playlist(p: dict) -> dict:
    if not p:
        return p
    owner = p.get("owner")
    return {
        "id": p.get("id"),
        "title": p.get("title"),
        "description": p.get("description"),
        "nb_tracks": p.get("estimated_tracks_count") or p.get("nb_tracks"),
        "owner": owner.get("name") if isinstance(owner, dict) else owner,
        "link": p.get("link") or f"https://www.deezer.com/playlist/{p.get('id')}",
    }


# ─── Tool definitions ────────────────────────────────────────────────────────

TOOLS = [
    # Profile
    Tool(
        name="get_me",
        description="Get your Deezer profile.",
        input_schema={"type": "object", "properties": {}},
    ),
    # Search
    Tool(
        name="search",
        description="Search Deezer for tracks, albums, artists, playlists.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "tracks_first": {"type": "integer", "description": "Max tracks (default 10)"},
                "albums_first": {"type": "integer", "description": "Max albums (default 10)"},
                "artists_first": {"type": "integer", "description": "Max artists (default 10)"},
                "playlists_first": {"type": "integer", "description": "Max playlists (default 10)"},
            },
            "required": ["query"],
        },
    ),
    # Browse
    Tool(
        name="get_track",
        description="Get track details by ID (includes lyrics).",
        input_schema={
            "type": "object",
            "properties": {"track_id": {"type": "string"}},
            "required": ["track_id"],
        },
    ),
    Tool(
        name="get_artist",
        description="Get artist details with bio, top tracks, albums.",
        input_schema={
            "type": "object",
            "properties": {"artist_id": {"type": "string"}},
            "required": ["artist_id"],
        },
    ),
    Tool(
        name="get_album",
        description="Get album details with full tracklist.",
        input_schema={
            "type": "object",
            "properties": {"album_id": {"type": "string"}},
            "required": ["album_id"],
        },
    ),
    Tool(
        name="get_playlist",
        description="Get playlist details with tracks.",
        input_schema={
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string"},
                "tracks_first": {"type": "integer", "description": "Max tracks (default 50)"},
            },
            "required": ["playlist_id"],
        },
    ),
    # Discovery
    Tool(
        name="get_charts",
        description="Get Deezer charts by country (FR, US, etc).",
        input_schema={
            "type": "object",
            "properties": {
                "country_code": {"type": "string", "description": "Country code (e.g. FR, US, DE)"},
                "tracks_first": {"type": "integer", "description": "Max tracks (default 10)"},
            },
        },
    ),
    Tool(
        name="get_similar_tracks",
        description="Tracks similar to a given track.",
        input_schema={
            "type": "object",
            "properties": {
                "track_id": {"type": "string"},
                "nb": {"type": "integer", "default": 10},
            },
            "required": ["track_id"],
        },
    ),
    Tool(
        name="get_similar_artists",
        description="Artists similar to a given artist.",
        input_schema={
            "type": "object",
            "properties": {
                "artist_id": {"type": "string"},
                "first": {"type": "integer", "default": 10},
            },
            "required": ["artist_id"],
        },
    ),
    Tool(
        name="get_flow",
        description="Get your personal Deezer Flow (auto-generated mix).",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_recommendations",
        description="Personalized recommendations.",
        input_schema={
            "type": "object",
            "properties": {"playlists_first": {"type": "integer"}},
        },
    ),
    Tool(
        name="get_recently_played",
        description="Your recently played tracks.",
        input_schema={
            "type": "object",
            "properties": {"first": {"type": "integer", "default": 20}},
        },
    ),
    Tool(
        name="get_user_charts",
        description="Your personal top tracks/artists/albums.",
        input_schema={
            "type": "object",
            "properties": {"tracks_first": {"type": "integer"}},
        },
    ),
    # Favorites
    Tool(
        name="get_favorite_tracks",
        description="Your liked/favorite tracks.",
        input_schema={
            "type": "object",
            "properties": {"first": {"type": "integer", "default": 50}},
        },
    ),
    Tool(
        name="get_favorite_albums",
        description="Your favorite albums.",
        input_schema={
            "type": "object",
            "properties": {"first": {"type": "integer", "default": 50}},
        },
    ),
    Tool(
        name="get_favorite_artists",
        description="Your followed artists.",
        input_schema={
            "type": "object",
            "properties": {"first": {"type": "integer", "default": 50}},
        },
    ),
    Tool(
        name="get_favorite_playlists",
        description="Your liked playlists.",
        input_schema={
            "type": "object",
            "properties": {"first": {"type": "integer", "default": 50}},
        },
    ),
    Tool(
        name="add_track_to_favorite",
        description="Like a track.",
        input_schema={
            "type": "object",
            "properties": {"track_id": {"type": "string"}},
            "required": ["track_id"],
        },
    ),
    Tool(
        name="remove_track_from_favorite",
        description="Unlike a track.",
        input_schema={
            "type": "object",
            "properties": {"track_id": {"type": "string"}},
            "required": ["track_id"],
        },
    ),
    Tool(
        name="add_album_to_favorite",
        description="Like an album.",
        input_schema={
            "type": "object",
            "properties": {"album_id": {"type": "string"}},
            "required": ["album_id"],
        },
    ),
    Tool(
        name="remove_album_from_favorite",
        description="Unlike an album.",
        input_schema={
            "type": "object",
            "properties": {"album_id": {"type": "string"}},
            "required": ["album_id"],
        },
    ),
    Tool(
        name="add_artist_to_favorite",
        description="Follow an artist.",
        input_schema={
            "type": "object",
            "properties": {"artist_id": {"type": "string"}},
            "required": ["artist_id"],
        },
    ),
    Tool(
        name="remove_artist_from_favorite",
        description="Unfollow an artist.",
        input_schema={
            "type": "object",
            "properties": {"artist_id": {"type": "string"}},
            "required": ["artist_id"],
        },
    ),
    # Playlists
    Tool(
        name="get_user_playlists",
        description="List all your playlists.",
        input_schema={
            "type": "object",
            "properties": {"first": {"type": "integer", "default": 50}},
        },
    ),
    Tool(
        name="create_playlist",
        description="Create a new playlist.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "is_private": {"type": "boolean", "default": False},
                "is_collaborative": {"type": "boolean", "default": False},
            },
            "required": ["title"],
        },
    ),
    Tool(
        name="update_playlist",
        description="Update playlist title/description.",
        input_schema={
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["playlist_id"],
        },
    ),
    Tool(
        name="delete_playlist",
        description="Delete a playlist.",
        input_schema={
            "type": "object",
            "properties": {"playlist_id": {"type": "string"}},
            "required": ["playlist_id"],
        },
    ),
    Tool(
        name="add_tracks_to_playlist",
        description="Add tracks to a playlist.",
        input_schema={
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string"},
                "track_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["playlist_id", "track_ids"],
        },
    ),
    Tool(
        name="remove_tracks_from_playlist",
        description="Remove tracks from a playlist.",
        input_schema={
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string"},
                "track_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["playlist_id", "track_ids"],
        },
    ),
]


# ─── Server ──────────────────────────────────────────────────────────────────

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def _safe_error_text(exc: Exception) -> str:
    """Format an exception without exposing the active Deezer session cookie."""
    message = str(exc)
    arl = os.environ.get("DEEZER_ARL", "").strip()
    if arl:
        message = message.replace(arl, "[REDACTED]")
    return f"{type(exc).__name__}: {message}"


async def _handle_list_tools(
    _ctx: ServerRequestContext,
    _params: PaginatedRequestParams | None,
) -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


async def _handle_call_tool(
    _ctx: ServerRequestContext,
    params: CallToolRequestParams,
) -> CallToolResult:
    arguments = params.arguments or {}
    tool = TOOLS_BY_NAME.get(params.name)
    if tool is None:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {params.name}")],
            is_error=True,
        )

    try:
        validate(instance=arguments, schema=tool.input_schema)
        result = await _dispatch(params.name, arguments)
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False, indent=2, default=str),
                )
            ],
            structured_content=result,
            is_error=False,
        )
    except ValidationError as exc:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Invalid arguments for {params.name}: {exc.message}",
                )
            ],
            is_error=True,
        )
    except Exception as exc:
        return CallToolResult(
            content=[TextContent(type="text", text=_safe_error_text(exc))],
            is_error=True,
        )


def create_server() -> Server:
    return Server(
        "mcp-deezer",
        version=__version__,
        description="Unofficial Deezer MCP server",
        on_list_tools=_handle_list_tools,
        on_call_tool=_handle_call_tool,
    )


async def _dispatch(name: str, args: dict) -> Any:
    c = await _get_client()

    # ── Profile ──
    if name == "get_me":
        return _to_dict(await c.get_me())

    # ── Search ──
    if name == "search":
        r = await c.search(
            query=args["query"],
            tracks_first=args.get("tracks_first", 10),
            albums_first=args.get("albums_first", 10),
            artists_first=args.get("artists_first", 10),
            playlists_first=args.get("playlists_first", 10),
        )
        d = _to_dict(r)
        results = d.get("results", d)
        return {
            "tracks": [_track(t) for t in _edges(_nav(results, "tracks"))],
            "albums": [_album(a) for a in _edges(_nav(results, "albums"))],
            "artists": [_artist(a) for a in _edges(_nav(results, "artists"))],
            "playlists": [_playlist(p) for p in _edges(_nav(results, "playlists"))],
        }

    # ── Browse ──
    if name == "get_track":
        return _to_dict(await c.get_track(track_id=args["track_id"]))

    if name == "get_artist":
        return _to_dict(await c.get_artist(artist_id=args["artist_id"]))

    if name == "get_album":
        return _to_dict(await c.get_album(album_id=args["album_id"]))

    if name == "get_playlist":
        r = await c.get_playlist(
            playlist_id=args["playlist_id"], tracks_first=args.get("tracks_first", 50)
        )
        d = _to_dict(r)
        playlist = d.get("playlist", d)
        return {
            **_playlist(playlist),
            "tracks": [_track(t) for t in _edges(_nav(playlist, "tracks"))],
        }

    # ── Discovery ──
    if name == "get_charts":
        r = await c.get_charts(country_code=args.get("country_code"))
        d = _to_dict(r)
        # Path: data.country.tracks (with country_code) or data.tracks (global)
        country = d.get("country", d)
        tracks_data = _nav(country, "tracks") or _nav(d, "tracks")
        return [_track(t) for t in _edges(tracks_data)]

    if name == "get_similar_tracks":
        r = await c.get_similar_tracks(track_id=args["track_id"], nb=args.get("nb", 10))
        d = _to_dict(r)
        tracks = (
            _edges(_nav(d, "track", "similarTracks"))
            or _edges(_nav(d, "similarTracks"))
            or _edges(_nav(d, "similar_tracks", "tracks"))
        )
        return [_track(t) for t in tracks]

    if name == "get_similar_artists":
        r = await c.get_similar_artists(artist_id=args["artist_id"], first=args.get("first", 10))
        d = _to_dict(r)
        artists = (
            _edges(_nav(d, "artist", "relatedArtists"))
            or _edges(_nav(d, "relatedArtists"))
            or _edges(_nav(d, "similar_artists", "artists"))
        )
        return [_artist(a) for a in artists]

    if name == "get_flow":
        r = await c.get_flow()
        d = _to_dict(r)
        tracks = _edges(_nav(d, "me", "flowTracks")) or _edges(d)
        return [_track(t) for t in tracks]

    if name == "get_recommendations":
        return _to_dict(await c.get_recommendations(playlists_first=args.get("playlists_first")))

    if name == "get_recently_played":
        r = await c.get_recently_played(first=args.get("first", 20))
        d = _to_dict(r)
        # Path: data.recently_played.edges[].node (track object)
        items = _edges(_nav(d, "recently_played"))
        # Each item might be a track directly or have nested track
        result = []
        for item in items:
            if isinstance(item, dict):
                # Try extracting track from nested structure
                t = item.get("track", item)
                result.append(_track(t))
        return result

    if name == "get_user_charts":
        return _to_dict(await c.get_user_charts(tracks_first=args.get("tracks_first")))

    # ── Favorites ──
    if name == "get_favorite_tracks":
        r = await c.get_favorite_tracks(first=args.get("first", 50))
        d = _to_dict(r)
        # Path: data.user_favorites.tracks.edges[].node
        tracks = _edges(_nav(d, "user_favorites", "tracks"))
        return [_track(t) for t in tracks]

    if name == "get_favorite_albums":
        r = await c.get_favorite_albums(first=args.get("first", 50))
        d = _to_dict(r)
        albums = _edges(_nav(d, "user_favorites", "albums")) or _edges(_nav(d, "me", "albums"))
        return [_album(a) for a in albums]

    if name == "get_favorite_artists":
        r = await c.get_favorite_artists(first=args.get("first", 50))
        d = _to_dict(r)
        artists = _edges(_nav(d, "user_favorites", "artists")) or _edges(_nav(d, "me", "artists"))
        return [_artist(a) for a in artists]

    if name == "get_favorite_playlists":
        r = await c.get_favorite_playlists(first=args.get("first", 50))
        d = _to_dict(r)
        playlists = _edges(_nav(d, "user_favorites", "playlists")) or _edges(
            _nav(d, "me", "playlists")
        )
        return [_playlist(p) for p in playlists]

    if name == "add_track_to_favorite":
        await c.add_track_to_favorite(track_id=args["track_id"])
        return {"success": True, "action": "liked", "track_id": args["track_id"]}

    if name == "remove_track_from_favorite":
        await c.remove_track_from_favorite(track_id=args["track_id"])
        return {"success": True, "action": "unliked", "track_id": args["track_id"]}

    if name == "add_album_to_favorite":
        await c.add_album_to_favorite(album_id=args["album_id"])
        return {"success": True, "action": "liked", "album_id": args["album_id"]}

    if name == "remove_album_from_favorite":
        await c.remove_album_from_favorite(album_id=args["album_id"])
        return {"success": True, "action": "unliked", "album_id": args["album_id"]}

    if name == "add_artist_to_favorite":
        await c.add_artist_to_favorite(artist_id=args["artist_id"])
        return {"success": True, "action": "followed", "artist_id": args["artist_id"]}

    if name == "remove_artist_from_favorite":
        await c.remove_artist_from_favorite(artist_id=args["artist_id"])
        return {"success": True, "action": "unfollowed", "artist_id": args["artist_id"]}

    # ── Playlists ──
    if name == "get_user_playlists":
        r = await c.get_user_playlists(first=args.get("first", 50))
        d = _to_dict(r)
        playlists = _edges(_nav(d, "playlists")) or _edges(_nav(d, "me", "playlists"))
        return [_playlist(p) for p in playlists]

    if name == "create_playlist":
        r = await c.create_playlist(
            title=args["title"],
            description=args.get("description"),
            is_private=args.get("is_private", False),
            is_collaborative=args.get("is_collaborative", False),
        )
        d = _to_dict(r)
        pl = _nav(d, "playlist") or d
        return {"success": True, "action": "created", "playlist": _playlist(pl)}

    if name == "update_playlist":
        await c.update_playlist(
            playlist_id=args["playlist_id"],
            title=args.get("title"),
            description=args.get("description"),
        )
        return {"success": True, "action": "updated", "playlist_id": args["playlist_id"]}

    if name == "delete_playlist":
        await c.delete_playlist(playlist_id=args["playlist_id"])
        return {"success": True, "action": "deleted", "playlist_id": args["playlist_id"]}

    if name == "add_tracks_to_playlist":
        await c.add_tracks_to_playlist(playlist_id=args["playlist_id"], track_ids=args["track_ids"])
        return {
            "success": True,
            "action": "added",
            "count": len(args["track_ids"]),
            "playlist_id": args["playlist_id"],
        }

    if name == "remove_tracks_from_playlist":
        await c.remove_tracks_from_playlist(
            playlist_id=args["playlist_id"], track_ids=args["track_ids"]
        )
        return {
            "success": True,
            "action": "removed",
            "count": len(args["track_ids"]),
            "playlist_id": args["playlist_id"],
        }

    raise ValueError(f"Unknown tool: {name}")


# ─── Entry point ─────────────────────────────────────────────────────────────


async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
