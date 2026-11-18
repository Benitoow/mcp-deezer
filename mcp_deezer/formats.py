"""Compact projections of Deezer responses.

Everything an agent reads goes through here: one shape per entity, no synthetic
fields (a node that has no Deezer URL simply gets none), and a single object
envelope for lists — MCP ``structuredContent`` must be an object, not an array.

The accessors tolerate both Pydantic models and plain dicts, which is what the
client returns depending on whether a section was dumped already.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

Formatter = Callable[[Any], dict[str, Any]]


def dump(obj: Any) -> Any:
    """Recursively convert Pydantic models into JSON-ready structures."""
    if obj is None:
        return None
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json", exclude_none=True)
    if isinstance(obj, list | tuple):
        return [dump(item) for item in obj]
    if isinstance(obj, dict):
        return {key: dump(value) for key, value in obj.items()}
    return obj


def get(obj: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` from a Pydantic model or a dict, without exploding on None."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def edges(container: Any) -> list[dict[str, Any]]:
    """Return node dicts from a Relay ``edges`` connection, a list, or ``data``/``items``."""
    data = dump(container)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    edge_list = data.get("edges")
    if isinstance(edge_list, list) and edge_list:
        nodes = []
        for edge in edge_list:
            if isinstance(edge, dict):
                node = edge.get("node", edge)
                if isinstance(node, dict):
                    nodes.append(node)
        return nodes
    for key in ("data", "items", "nodes"):
        items = data.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def next_cursor(container: Any) -> str | None:
    """Cursor for the next page, or None when the connection is exhausted."""
    data = dump(container)
    if not isinstance(data, dict):
        return None
    info = data.get("page_info")
    if isinstance(info, dict) and info.get("has_next_page"):
        cursor = info.get("end_cursor")
        return cursor if isinstance(cursor, str) and cursor else None
    return None


def page(
    items: Iterable[dict[str, Any]],
    *,
    next_cursor_: str | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    """The single object envelope used by every list-returning tool."""
    collected = list(items)
    return {
        "items": collected,
        "count": len(collected),
        "total": total,
        "next_cursor": next_cursor_,
    }


def page_from(container: Any, formatter: Formatter, *, limit: int | None = None) -> dict[str, Any]:
    """Build an envelope from a Relay connection (or a plain list of nodes)."""
    items = [formatter(node) for node in edges(container)]
    if limit is not None:
        items = items[:limit]
    return page(items, next_cursor_=next_cursor(container))


def _first_contributor_name(contributors: Any) -> str | None:
    if not isinstance(contributors, dict):
        return None
    node = None
    for edge in contributors.get("edges") or []:
        if isinstance(edge, dict):
            node = edge.get("node")
            if isinstance(node, dict):
                break
    return node.get("name") if isinstance(node, dict) else None


def main_artist(node: dict[str, Any]) -> str | None:
    """Name of the MAIN contributor, falling back to the first one."""
    contributors = node.get("contributors")
    if not isinstance(contributors, dict):
        return None
    for edge in contributors.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        roles = edge.get("roles") or []
        if "MAIN" in roles:
            name = get(edge.get("node"), "name")
            if name:
                return str(name)
    return _first_contributor_name(contributors)


def _album_title(album: Any) -> str | None:
    if not isinstance(album, dict):
        return None
    title = album.get("display_title") or album.get("title")
    return str(title) if title else None


def _present(values: dict[str, Any]) -> dict[str, Any]:
    """Drop null values so the payload stays small and unambiguous."""
    return {
        key: value
        for key, value in values.items()
        if value is not None and value != [] and value != {}
    }


def track(node: Any) -> dict[str, Any]:
    """Compact track: what an agent needs to decide, nothing derived."""
    data = dump(node)
    if not isinstance(data, dict):
        return {}
    result = _present(
        {
            "id": data.get("id"),
            "title": data.get("title"),
            "artist": main_artist(data),
            "album": _album_title(data.get("album")),
            "duration": data.get("duration"),
            "explicit": True if data.get("is_explicit") else None,
        }
    )
    if data.get("is_favorite"):
        result["is_favorite"] = True
    return result


def track_detail(node: Any) -> dict[str, Any]:
    """Everything useful about one track, without the lyrics payload."""
    data = dump(node)
    if not isinstance(data, dict):
        return {}
    result = track(data)
    album = data.get("album")
    track_id = data.get("id")
    details = _present(
        {
            "isrc": data.get("isrc"),
            "release_date": data.get("release_date"),
            "popularity": data.get("popularity"),
            "album_id": album.get("id") if isinstance(album, dict) else None,
            "deezer_url": f"https://www.deezer.com/track/{track_id}" if track_id else None,
        }
    )
    result.update(details)
    return result


def lyrics(node: Any) -> dict[str, Any] | None:
    """Lyrics text and credits; synchronized lines are dropped (too heavy, low value)."""
    data = dump(node)
    if not isinstance(data, dict):
        return None
    text = data.get("text")
    if not text:
        return None
    return _present(
        {
            "text": str(text).strip(),
            "copyright": data.get("copyright"),
            "writers": data.get("writers"),
        }
    )


def artist(node: Any) -> dict[str, Any]:
    data = dump(node)
    if not isinstance(data, dict):
        return {}
    result = _present(
        {
            "id": data.get("id"),
            "name": data.get("name"),
            "fans": data.get("fans_count") or data.get("nb_fan"),
        }
    )
    if data.get("is_favorite"):
        result["is_favorite"] = True
    return result


def album(node: Any) -> dict[str, Any]:
    data = dump(node)
    if not isinstance(data, dict):
        return {}
    result = _present(
        {
            "id": data.get("id"),
            "title": data.get("display_title") or data.get("title"),
            "artist": _first_contributor_name(dump(data.get("contributors"))),
            "tracks_count": data.get("tracks_count") or data.get("nb_tracks"),
            "release_date": data.get("release_date"),
        }
    )
    if data.get("is_favorite"):
        result["is_favorite"] = True
    return result


def playlist(node: Any) -> dict[str, Any]:
    data = dump(node)
    if not isinstance(data, dict):
        return {}
    owner = data.get("owner")
    result = _present(
        {
            "id": data.get("id"),
            "title": data.get("title"),
            "description": data.get("description"),
            "owner": owner.get("name") if isinstance(owner, dict) else owner,
            "tracks_count": data.get("estimated_tracks_count") or data.get("nb_tracks"),
            "duration": data.get("estimated_duration"),
        }
    )
    if data.get("is_private"):
        result["private"] = True
    if data.get("is_collaborative"):
        result["collaborative"] = True
    if data.get("is_favorite"):
        result["is_favorite"] = True
    return result


def history_item(node: Any) -> dict[str, Any]:
    """A recently-played entry: the API stores containers (album, playlist, flow...)."""
    data = dump(node)
    if not isinstance(data, dict):
        return {}
    kind = data.get("typename__") or data.get("__typename") or "unknown"
    title = data.get("display_title") or data.get("title") or data.get("name")
    result = _present({"type": kind, "id": data.get("id"), "title": title})
    if kind in {"Album", "Playlist", "Artist"}:
        artist_name = _first_contributor_name(dump(data.get("contributors")))
        if artist_name:
            result["artist"] = artist_name
    return result


def bio_text(node: Any, *, max_chars: int = 1200) -> str | None:
    """Artist biography, truncated: Deezer ships it as markup of arbitrary length."""
    data = dump(node)
    if not isinstance(data, dict):
        return None
    raw = data.get("full") or data.get("text") or data.get("summary")
    if not raw:
        return None
    text = str(raw).strip()
    return text[:max_chars] + "…" if len(text) > max_chars else text
