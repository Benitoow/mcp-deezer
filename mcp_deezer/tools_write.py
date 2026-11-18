"""Write tools: favorites and playlist mutations.

Every mutation is verified against the value Deezer actually returns — v1 answered
``success: true`` even when the API had refused the change.
"""

from __future__ import annotations

from typing import Any

from .catalog import ID, ack_schema, register
from .client import call
from .config import WRITE_BATCH
from .errors import ToolError
from .formats import get, playlist
from .params import choice, clean_ids, require_id

FAVORITE_METHODS = {
    ("track", "add"): ("add_track_to_favorite", "track_id"),
    ("track", "remove"): ("remove_track_from_favorite", "track_id"),
    ("album", "add"): ("add_album_to_favorite", "album_id"),
    ("album", "remove"): ("remove_album_from_favorite", "album_id"),
    ("artist", "add"): ("add_artist_to_favorite", "artist_id"),
    ("artist", "remove"): ("remove_artist_from_favorite", "artist_id"),
    ("playlist", "add"): ("add_playlist_to_favorite", "playlist_id"),
    ("playlist", "remove"): ("remove_playlist_from_favorite", "playlist_id"),
}

TRACK_ID_LIST = {
    "type": "array",
    "items": {"type": "string", "pattern": "^[0-9]+$"},
    "minItems": 1,
    "maxItems": 100,
    "description": "Deezer track ids, batched internally.",
}


async def _apply_track_edit(
    client: Any, playlist_id: str, track_ids: list[str], action: str
) -> dict[str, Any]:
    """Add or remove tracks in batches, reporting what Deezer really applied."""
    updated: list[str] = []
    rejected: list[str] = []
    batches = [track_ids[i : i + WRITE_BATCH] for i in range(0, len(track_ids), WRITE_BATCH)]

    for batch in batches:
        if action == "add":
            result = await call(
                client.add_tracks_to_playlist,
                playlist_id=playlist_id,
                track_ids=batch,
                write=True,
            )
            applied_raw = get(result, "added_track_ids")
            if applied_raw is None:
                # `PlaylistAddTracksError` variant: Deezer refused the whole batch.
                rejected.extend(batch)
                continue
        else:
            result = await call(
                client.remove_tracks_from_playlist,
                playlist_id=playlist_id,
                track_ids=batch,
                write=True,
            )
            applied_raw = get(result, "removed_track_ids")

        applied = [str(item) for item in (applied_raw or [])]
        updated.extend(applied)
        applied_set = set(applied)
        rejected.extend(track_id for track_id in batch if track_id not in applied_set)

    if not updated:
        raise ToolError(
            "Deezer changed nothing: none of these track ids were "
            + ("accepted" if action == "add" else "present")
            + " in that playlist. Check that the playlist belongs to this account and that the "
            "tracks are available in your country."
        )
    return {
        "success": not rejected,
        "action": action,
        "playlist_id": playlist_id,
        "updated": updated,
        "rejected": rejected,
        "count": len(updated),
    }


@register(
    name="set_favorite",
    title="Like / unlike something",
    description=("Like or unlike a track, album, artist or playlist."),
    input_schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["track", "album", "artist", "playlist"]},
            "id": ID,
            "action": {"type": "string", "enum": ["add", "remove"], "default": "add"},
        },
        "required": ["kind", "id"],
        "additionalProperties": False,
    },
    output_schema=ack_schema(
        kind={"type": "string"},
        id={"type": "string"},
        is_favorite={"type": ["boolean", "null"]},
    ),
    read_only=False,
    destructive=False,
    idempotent=True,
)
async def set_favorite(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    kind = choice(args, "kind", ("track", "album", "artist", "playlist"), "track")
    action = choice(args, "action", ("add", "remove"), "add")
    identifier = require_id(args, "id")
    method_name, parameter = FAVORITE_METHODS[(kind, action)]

    result = await call(getattr(client, method_name), write=True, **{parameter: identifier})
    payload: dict[str, Any] = {
        "success": True,
        "kind": kind,
        "id": identifier,
        "action": action,
    }
    entity = get(result, kind)
    state = get(entity, "is_favorite")
    if state is not None:
        payload["is_favorite"] = bool(state)
    return payload


@register(
    name="edit_playlist_tracks",
    title="Add / remove tracks in a playlist",
    description=(
        "Add or remove tracks in one of your playlists; batched, and reports what "
        "Deezer applied versus rejected."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "playlist_id": ID,
            "track_ids": TRACK_ID_LIST,
            "action": {"type": "string", "enum": ["add", "remove"], "default": "add"},
        },
        "required": ["playlist_id", "track_ids"],
        "additionalProperties": False,
    },
    output_schema=ack_schema(
        playlist_id={"type": "string"},
        updated={"type": "array", "items": {"type": "string"}},
        rejected={"type": "array", "items": {"type": "string"}},
    ),
    read_only=False,
    destructive=True,
    idempotent=False,
)
async def edit_playlist_tracks(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    playlist_id = require_id(args, "playlist_id")
    action = choice(args, "action", ("add", "remove"), "add")
    track_ids = clean_ids(args.get("track_ids"), "track_ids")
    return await _apply_track_edit(client, playlist_id, track_ids, action)


@register(
    name="create_playlist",
    title="Create a playlist",
    description=("Create a playlist, optionally with initial tracks (one call)."),
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "description": {"type": "string", "maxLength": 2000},
            "private": {"type": "boolean", "default": False},
            "collaborative": {"type": "boolean", "default": False},
            "track_ids": TRACK_ID_LIST,
        },
        "required": ["title"],
        "additionalProperties": False,
    },
    output_schema=ack_schema(playlist={"type": "object"}),
    read_only=False,
    destructive=False,
    idempotent=False,
)
async def create_playlist(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    title = str(args["title"]).strip()
    if not title:
        raise ToolError("`title` must not be empty.")
    created = await call(
        client.create_playlist,
        title=title,
        description=args.get("description"),
        is_private=bool(args.get("private", False)),
        is_collaborative=bool(args.get("collaborative", False)),
        write=True,
    )
    node = get(created, "playlist")
    if node is None:
        raise ToolError("Deezer did not return the created playlist.")
    payload: dict[str, Any] = {"success": True, "playlist": playlist(node)}
    track_ids = clean_ids(args.get("track_ids"), "track_ids")
    if track_ids:
        playlist_id = str(get(node, "id", ""))
        payload.update(await _apply_track_edit(client, playlist_id, track_ids, "add"))
    return payload


@register(
    name="update_playlist",
    title="Update a playlist",
    description="Rename a playlist or change its description, privacy or collaborative flag.",
    input_schema={
        "type": "object",
        "properties": {
            "playlist_id": ID,
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "description": {"type": "string", "maxLength": 2000},
            "private": {"type": "boolean"},
            "collaborative": {"type": "boolean"},
        },
        "required": ["playlist_id"],
        "additionalProperties": False,
    },
    output_schema=ack_schema(
        playlist_id={"type": "string"},
        updated={"type": "array", "items": {"type": "string"}},
    ),
    read_only=False,
    destructive=False,
    idempotent=True,
)
async def update_playlist(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    playlist_id = require_id(args, "playlist_id")
    changes: dict[str, Any] = {}
    if args.get("title") is not None:
        changes["title"] = str(args["title"])
    if args.get("description") is not None:
        changes["description"] = str(args["description"])
    if args.get("private") is not None:
        changes["is_private"] = bool(args["private"])
    if args.get("collaborative") is not None:
        changes["is_collaborative"] = bool(args["collaborative"])
    if not changes:
        raise ToolError(
            "Nothing to update: pass at least one of "
            "`title`, `description`, `private`, `collaborative`."
        )

    await call(client.update_playlist, playlist_id=playlist_id, write=True, **changes)
    return {"success": True, "playlist_id": playlist_id, "updated": sorted(changes)}


@register(
    name="delete_playlist",
    title="Delete a playlist",
    description=(
        "Permanently delete a playlist. Irreversible: requires `confirm: true`, "
        "after the user agreed."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "playlist_id": ID,
            "confirm": {
                "type": "boolean",
                "description": "Must be true (agent safety).",
            },
        },
        "required": ["playlist_id", "confirm"],
        "additionalProperties": False,
    },
    output_schema=ack_schema(playlist_id={"type": "string"}, deleted={"type": "boolean"}),
    read_only=False,
    destructive=True,
    idempotent=False,
)
async def delete_playlist(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    playlist_id = require_id(args, "playlist_id")
    if args.get("confirm") is not True:
        raise ToolError(
            "Refusing to delete: `confirm` must be true, and only after the user "
            "explicitly agreed. Ask the user first, then call again with confirm=true."
        )
    await call(client.delete_playlist, playlist_id=playlist_id, write=True)
    return {"success": True, "action": "deleted", "playlist_id": playlist_id, "deleted": True}
