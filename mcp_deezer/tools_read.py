"""Read-only tools: search, browse, discovery, favorites, history."""

from __future__ import annotations

from typing import Any

from .catalog import CURSOR, ID, LIMIT, OBJECT, PAGE, object_schema, register
from .client import call
from .errors import ToolError
from .formats import (
    album,
    artist,
    bio_text,
    edges,
    get,
    history_item,
    lyrics,
    page,
    page_from,
    playlist,
    track,
    track_detail,
)
from .params import choice, limit_of, require_id

KIND_SECTIONS = {
    "track": "tracks",
    "album": "albums",
    "artist": "artists",
    "playlist": "playlists",
}

FORMATTERS = {
    "tracks": track,
    "albums": album,
    "artists": artist,
    "playlists": playlist,
}

FAVORITES = {
    "track": ("get_favorite_tracks", "tracks", track),
    "album": ("get_favorite_albums", "albums", album),
    "artist": ("get_favorite_artists", "artists", artist),
    "playlist": ("get_favorite_playlists", "playlists", playlist),
}


@register(
    name="get_me",
    title="Who am I",
    description=(
        "Your Deezer user id. The Pipe API exposes only `id` here; "
        "use get_playlists / get_favorites for account content."
    ),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema=object_schema(id={"type": "string"}),
    idempotent=True,
)
async def get_me(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    profile = await call(client.get_me)
    if profile is None:
        raise ToolError("Deezer returned no profile for this session (ARL may be expired).")
    return {"id": str(get(profile, "id", ""))}


@register(
    name="search",
    title="Search Deezer",
    description=(
        "Search tracks, albums, artists and playlists. Prefer a single `kind`: "
        "cheaper and more precise than `all`."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "description": "Title, artist..."},
            "kind": {
                "type": "string",
                "enum": ["all", "track", "album", "artist", "playlist"],
                "default": "all",
            },
            "limit": LIMIT,
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    output_schema=OBJECT,
    idempotent=True,
)
async def search(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args["query"]).strip()
    if not query:
        raise ToolError("`query` must not be empty.")
    kind = choice(args, "kind", ("all", *KIND_SECTIONS), "all")
    limit = limit_of(args)
    wanted = list(KIND_SECTIONS.values()) if kind == "all" else [KIND_SECTIONS[kind]]

    # Only ask for the categories we return: an unset `first` keeps Deezer's default,
    # while passing 0 would rely on the API accepting empty pages (it is not tested).
    firsts: dict[str, Any] = {f"{section}_first": limit for section in wanted}
    result = await call(client.search, query=query, **firsts)
    results = get(result, "results")
    if results is None:
        raise ToolError("Deezer returned no search result for this query.")
    return {
        section: page_from(get(results, section), FORMATTERS[section], limit=limit)
        for section in wanted
    }


@register(
    name="get_track",
    title="Get a track",
    description=(
        "Track details (ISRC, release date, popularity). Lyrics are excluded by default: "
        "set `include_lyrics` or call get_lyrics."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "track_id": ID,
            "include_lyrics": {
                "type": "boolean",
                "default": False,
                "description": "Also return the lyrics text (heavy).",
            },
        },
        "required": ["track_id"],
        "additionalProperties": False,
    },
    output_schema=object_schema(
        id={"type": "string"},
        title={"type": "string"},
        artist={"type": ["string", "null"]},
        lyrics={"type": "object"},
    ),
    idempotent=True,
)
async def get_track(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    track_id = require_id(args, "track_id")
    result = await call(client.get_track, track_id=track_id)
    if result is None:
        raise ToolError(f"Track {track_id} not found.")
    payload = track_detail(result)
    if args.get("include_lyrics"):
        text = lyrics(get(result, "lyrics"))
        if text:
            payload["lyrics"] = text
    return payload


@register(
    name="get_lyrics",
    title="Get track lyrics",
    description="Lyrics text and credits for one track. Fails cleanly when Deezer has no lyrics.",
    input_schema={
        "type": "object",
        "properties": {"track_id": ID},
        "required": ["track_id"],
        "additionalProperties": False,
    },
    output_schema=object_schema(
        track_id={"type": "string"},
        title={"type": ["string", "null"]},
        text={"type": "string"},
    ),
    idempotent=True,
)
async def get_lyrics(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    track_id = require_id(args, "track_id")
    result = await call(client.get_track, track_id=track_id)
    if result is None:
        raise ToolError(f"Track {track_id} not found.")
    text = lyrics(get(result, "lyrics"))
    if text is None:
        raise ToolError(f"Deezer has no lyrics for track {track_id}.")
    return {"track_id": track_id, "title": get(result, "title"), **text}


@register(
    name="get_artist",
    title="Get an artist",
    description=(
        "Artist details with optional top tracks, albums and bio; "
        "each section pages with its own cursor."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "artist_id": ID,
            "limit": LIMIT,
            "include_top_tracks": {"type": "boolean", "default": True},
            "include_albums": {"type": "boolean", "default": True},
            "include_bio": {
                "type": "boolean",
                "default": False,
                "description": "Include the bio (truncated).",
            },
            "tracks_cursor": CURSOR,
            "albums_cursor": CURSOR,
        },
        "required": ["artist_id"],
        "additionalProperties": False,
    },
    output_schema=object_schema(
        id={"type": "string"},
        name={"type": "string"},
        top_tracks=PAGE,
        albums=PAGE,
        bio={"type": "string"},
    ),
    idempotent=True,
)
async def get_artist(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    artist_id = require_id(args, "artist_id")
    limit = limit_of(args)
    include_tracks = bool(args.get("include_top_tracks", True))
    include_albums = bool(args.get("include_albums", True))

    kwargs: dict[str, Any] = {"artist_id": artist_id}
    if include_tracks:
        kwargs["top_tracks_first"] = limit
        if args.get("tracks_cursor"):
            kwargs["top_tracks_after"] = str(args["tracks_cursor"])
    if include_albums:
        kwargs["albums_first"] = limit
        if args.get("albums_cursor"):
            kwargs["albums_after"] = str(args["albums_cursor"])

    result = await call(client.get_artist, **kwargs)
    if result is None:
        raise ToolError(f"Artist {artist_id} not found.")

    payload = artist(result)
    if include_tracks:
        payload["top_tracks"] = page_from(get(result, "top_tracks"), track, limit=limit)
    if include_albums:
        payload["albums"] = page_from(get(result, "albums"), album, limit=limit)
    if args.get("include_bio"):
        text = bio_text(get(result, "bio"))
        if text:
            payload["bio"] = text
    return payload


@register(
    name="get_album",
    title="Get an album",
    description="Album details with its tracklist (pageable with `cursor`).",
    input_schema={
        "type": "object",
        "properties": {"album_id": ID, "limit": LIMIT, "cursor": CURSOR},
        "required": ["album_id"],
        "additionalProperties": False,
    },
    output_schema=object_schema(id={"type": "string"}, title={"type": "string"}, tracks=PAGE),
    idempotent=True,
)
async def get_album(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    album_id = require_id(args, "album_id")
    limit = limit_of(args)
    kwargs: dict[str, Any] = {"album_id": album_id, "tracks_first": limit}
    if args.get("cursor"):
        kwargs["tracks_after"] = str(args["cursor"])
    result = await call(client.get_album, **kwargs)
    if result is None:
        raise ToolError(f"Album {album_id} not found.")
    payload = album(result)
    payload["tracks"] = page_from(get(result, "tracks"), track, limit=limit)
    return payload


@register(
    name="get_playlist",
    title="Get a playlist",
    description="Playlist details with its tracks (pageable with `cursor`).",
    input_schema={
        "type": "object",
        "properties": {"playlist_id": ID, "limit": LIMIT, "cursor": CURSOR},
        "required": ["playlist_id"],
        "additionalProperties": False,
    },
    output_schema=object_schema(id={"type": "string"}, title={"type": "string"}, tracks=PAGE),
    idempotent=True,
)
async def get_playlist(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    playlist_id = require_id(args, "playlist_id")
    limit = limit_of(args)
    kwargs: dict[str, Any] = {"playlist_id": playlist_id, "tracks_first": limit}
    if args.get("cursor"):
        kwargs["tracks_after"] = str(args["cursor"])
    result = await call(client.get_playlist, **kwargs)
    if result is None:
        raise ToolError(f"Playlist {playlist_id} not found.")
    payload = playlist(result)
    payload["tracks"] = page_from(get(result, "tracks"), track, limit=limit)
    return payload


@register(
    name="get_charts",
    title="Deezer charts",
    description="Public charts for a country, or worldwide without `country_code`.",
    input_schema={
        "type": "object",
        "properties": {
            "country_code": {
                "type": "string",
                "pattern": "^[A-Za-z]{2}$",
                "description": "ISO 3166-1 alpha-2 code (FR, US...); omit for worldwide.",
            },
            "kind": {
                "type": "string",
                "enum": list(KIND_SECTIONS),
                "default": "track",
                "description": "Chart category.",
            },
            "limit": LIMIT,
        },
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_charts(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    country = str(args.get("country_code", "")).strip().upper() or None
    kind = choice(args, "kind", KIND_SECTIONS, "track")
    limit = limit_of(args)
    section = KIND_SECTIONS[kind]

    firsts: dict[str, Any] = {f"{section}_first": limit}
    result = await call(client.get_charts, country_code=country, **firsts)
    chart = get(result, "country")
    if chart is None:
        raise ToolError(
            "Deezer returned no chart for this country code. "
            "Try another code, or omit `country_code`."
        )
    return page_from(get(chart, section), FORMATTERS[section], limit=limit)


@register(
    name="get_similar_tracks",
    title="Tracks similar to one track",
    description="Tracks Deezer considers similar to a given track.",
    input_schema={
        "type": "object",
        "properties": {"track_id": ID, "limit": LIMIT},
        "required": ["track_id"],
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_similar_tracks(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    track_id = require_id(args, "track_id")
    limit = limit_of(args, 10)
    result = await call(client.get_similar_tracks, track_id=track_id, nb=limit)
    if result is None:
        raise ToolError(f"Track {track_id} not found.")
    items = [track(node) for node in edges(get(result, "recommended_tracks"))][:limit]
    return page(items)


@register(
    name="get_similar_artists",
    title="Artists similar to one artist",
    description="Artists related to a given artist.",
    input_schema={
        "type": "object",
        "properties": {"artist_id": ID, "limit": LIMIT},
        "required": ["artist_id"],
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_similar_artists(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    artist_id = require_id(args, "artist_id")
    limit = limit_of(args, 10)
    result = await call(client.get_similar_artists, artist_id=artist_id, first=limit)
    if result is None:
        raise ToolError(f"Artist {artist_id} not found.")
    return page_from(get(result, "related_artist"), artist, limit=limit)


@register(
    name="get_flow",
    title="Personal Flow",
    description="Your personal Flow (auto-generated mix).",
    input_schema={
        "type": "object",
        "properties": {"limit": LIMIT},
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_flow(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    limit = limit_of(args, 30)
    result = await call(client.get_flow)
    flow = get(result, "flow")
    if flow is None:
        raise ToolError("Deezer Flow is not available for this account.")
    items = [track(node) for node in edges(get(flow, "tracks"))][:limit]
    return page(items)


@register(
    name="get_recommendations",
    title="Personal recommendations",
    description=(
        "Your personalized home: recommended playlists, artist playlists, "
        "new releases, artists and hot tracks."
    ),
    input_schema={
        "type": "object",
        "properties": {"limit": LIMIT},
        "additionalProperties": False,
    },
    output_schema=object_schema(
        playlists=PAGE,
        artist_playlists=PAGE,
        new_releases=PAGE,
        artists=PAGE,
        hot_tracks=PAGE,
    ),
    idempotent=True,
)
async def get_recommendations(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    limit = limit_of(args)
    result = await call(
        client.get_recommendations,
        playlists_first=limit,
        artist_playlists_first=limit,
        new_releases_first=limit,
        artists_first=limit,
        hot_tracks_limit=limit,
    )
    recommendations = get(result, "recommendations")
    if recommendations is None:
        raise ToolError("Deezer returned no recommendations for this account.")
    payload = {
        "playlists": page_from(get(recommendations, "playlists"), playlist, limit=limit),
        "artist_playlists": page_from(
            get(recommendations, "artist_playlists"), playlist, limit=limit
        ),
        "new_releases": page_from(get(recommendations, "new_releases"), album, limit=limit),
        "artists": page_from(get(recommendations, "artists"), artist, limit=limit),
    }
    hot_tracks = edges(get(recommendations, "hot_tracks"))
    if hot_tracks:
        payload["hot_tracks"] = page([track(node) for node in hot_tracks][:limit])
    return payload


@register(
    name="get_recently_played",
    title="Recently played",
    description=(
        "What you played recently: Deezer stores the container (album, playlist, "
        "artist, Flow), not the track. Use get_album/get_playlist for its tracks."
    ),
    input_schema={
        "type": "object",
        "properties": {"limit": LIMIT},
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_recently_played(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    limit = limit_of(args)
    result = await call(client.get_recently_played, first=limit)
    return page_from(get(result, "recently_played"), history_item, limit=limit)


@register(
    name="get_user_charts",
    title="Your top tracks/artists/albums",
    description="Your personal charts for one category.",
    input_schema={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["track", "artist", "album"],
                "default": "track",
            },
            "limit": LIMIT,
        },
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_user_charts(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    kind = choice(args, "kind", ("track", "artist", "album"), "track")
    limit = limit_of(args)
    section = KIND_SECTIONS[kind]
    firsts: dict[str, Any] = {f"{section}_first": limit}
    result = await call(client.get_user_charts, **firsts)
    charts = get(result, "charts")
    if charts is None:
        raise ToolError("Deezer returned no personal charts for this account.")
    return page_from(get(charts, section), FORMATTERS[section], limit=limit)


@register(
    name="get_favorites",
    title="Your favorites",
    description=(
        "Your liked tracks, albums, artists or playlists, one `kind` per call. "
        "Page with `cursor` (a previous `next_cursor`)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": list(FAVORITES),
                "default": "track",
                "description": "Category to list.",
            },
            "limit": LIMIT,
            "cursor": CURSOR,
        },
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_favorites(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    kind = choice(args, "kind", FAVORITES, "track")
    limit = limit_of(args, 50)
    method_name, section, formatter = FAVORITES[kind]
    kwargs: dict[str, Any] = {"first": limit}
    if args.get("cursor"):
        kwargs["after"] = str(args["cursor"])
    result = await call(getattr(client, method_name), **kwargs)
    favorites = get(result, "user_favorites")
    if favorites is None:
        raise ToolError("Deezer returned no favorites for this account.")
    return page_from(get(favorites, section), formatter, limit=limit)


@register(
    name="get_playlists",
    title="Your playlists",
    description="All playlists of the account, pageable with `cursor`.",
    input_schema={
        "type": "object",
        "properties": {"limit": LIMIT, "cursor": CURSOR},
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_playlists(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    limit = limit_of(args, 50)
    kwargs: dict[str, Any] = {"first": limit}
    if args.get("cursor"):
        kwargs["after"] = str(args["cursor"])
    result = await call(client.get_user_playlists, **kwargs)
    return page_from(get(result, "playlists"), playlist, limit=limit)
