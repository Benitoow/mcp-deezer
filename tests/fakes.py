"""Fake Deezer client and response payloads.

Payloads mirror the ``model_dump(mode="json")`` shape of the real client models
(field names, not GraphQL camelCase). ``tests/test_contract.py`` asserts that the
field names the handlers read still exist on the installed client models, so a
client upgrade that renames a field fails loudly instead of silently returning
empty lists.
"""

from __future__ import annotations

from typing import Any


def track_payload(track_id: str = "3135556", title: str = "One More Time") -> dict:
    return {
        "id": track_id,
        "title": title,
        "duration": 320,
        "isrc": "GBDUW0000059",
        "is_explicit": False,
        "contributors": {
            "edges": [
                {"roles": ["MAIN"], "node": {"id": "27", "name": "Daft Punk"}},
                {"roles": ["FEATURED"], "node": {"id": "28", "name": "Romanthony"}},
            ]
        },
        "album": {"id": "302127", "display_title": "Discovery"},
    }


def artist_payload(artist_id: str = "27", name: str = "Daft Punk") -> dict:
    return {"id": artist_id, "name": name, "fans_count": 3_000_000}


def album_payload(album_id: str = "302127", title: str = "Discovery") -> dict:
    return {
        "id": album_id,
        "display_title": title,
        "tracks_count": 14,
        "release_date": "2001-03-07",
        "contributors": {"edges": [{"node": {"id": "27", "name": "Daft Punk"}}]},
    }


def playlist_payload(playlist_id: str = "908622995", title: str = "Coding") -> dict:
    return {
        "id": playlist_id,
        "title": title,
        "description": "Focus",
        "estimated_tracks_count": 42,
        "estimated_duration": 7200,
        "owner": {"id": "1", "name": "Starx"},
    }


def connection(nodes: list[dict], *, next_page: str | None = None) -> dict:
    info: dict[str, Any] = {"has_next_page": next_page is not None}
    if next_page is not None:
        info["end_cursor"] = next_page
    return {"edges": [{"node": node} for node in nodes], "page_info": info}


class FakeClient:
    """Records calls and returns canned responses (or a callable for dynamic ones)."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = dict(responses or {})
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, name: str):
        async def method(**kwargs):
            self.calls.append((name, kwargs))
            value = self.responses.get(name)
            if isinstance(value, BaseException):
                raise value
            if callable(value):
                return value(**kwargs)
            return value

        return method

    def calls_of(self, name: str) -> list[dict]:
        return [kwargs for called, kwargs in self.calls if called == name]
