from __future__ import annotations

import asyncio
import json

import pytest

from mcp_deezer import catalog
from mcp_deezer.errors import ToolError
from tests.fakes import (
    FakeClient,
    album_payload,
    artist_payload,
    connection,
    playlist_payload,
    track_payload,
)


def call(tool: str, client: FakeClient, **args) -> dict:
    return asyncio.run(catalog.REGISTRY[tool].handler(client, args))


def test_search_returns_only_the_requested_category():
    client = FakeClient({"search": {"results": {"tracks": connection([track_payload()])}}})

    result = call("search", client, query="daft punk", kind="track")

    assert list(result) == ["tracks"]
    assert result["tracks"]["count"] == 1
    assert result["tracks"]["items"][0] == {
        "id": "3135556",
        "title": "One More Time",
        "artist": "Daft Punk",
        "album": "Discovery",
        "duration": 320,
    }
    assert client.calls_of("search") == [{"query": "daft punk", "tracks_first": 20}]


def test_search_all_categories():
    payload = {
        "results": {
            "tracks": connection([track_payload()]),
            "albums": connection([album_payload()]),
            "artists": connection([artist_payload()]),
            "playlists": connection([playlist_payload()]),
        }
    }
    client = FakeClient({"search": payload})

    result = call("search", client, query="daft punk")

    assert set(result) == {"tracks", "albums", "artists", "playlists"}
    assert result["albums"]["items"][0]["artist"] == "Daft Punk"
    assert client.calls_of("search")[0]["tracks_first"] == 20


def test_search_rejects_blank_query():
    with pytest.raises(ToolError):
        call("search", FakeClient(), query="   ")


def test_similar_tracks_are_read_from_the_right_field():
    client = FakeClient(
        {
            "get_similar_tracks": {
                "recommended_tracks": [track_payload(), track_payload("2", "Aerodynamic")]
            }
        }
    )

    result = call("get_similar_tracks", client, track_id="3135556")

    assert result["count"] == 2
    assert [item["title"] for item in result["items"]] == ["One More Time", "Aerodynamic"]
    assert client.calls_of("get_similar_tracks")[0]["nb"] == 10


def test_flow_uses_flow_tracks_and_never_invents_links():
    client = FakeClient({"get_flow": {"flow": {"id": "flow", "tracks": [track_payload()]}}})

    result = call("get_flow", client, limit=5)

    assert result["count"] == 1
    assert "deezer.com" not in json.dumps(result)


def test_flow_missing_is_an_error_not_an_empty_list():
    with pytest.raises(ToolError):
        call("get_flow", FakeClient({"get_flow": {"flow": None}}))


def test_recently_played_maps_containers_instead_of_fake_tracks():
    client = FakeClient(
        {
            "get_recently_played": {
                "recently_played": connection(
                    [{"typename__": "Artist", "id": "27", "name": "Daft Punk"}]
                )
            }
        }
    )

    result = call("get_recently_played", client)

    assert result["items"] == [{"type": "Artist", "id": "27", "title": "Daft Punk"}]


def test_favorites_carry_the_next_cursor():
    client = FakeClient(
        {
            "get_favorite_tracks": {
                "user_favorites": {"tracks": connection([track_payload()], next_page="cursor-2")}
            }
        }
    )

    result = call("get_favorites", client, kind="track")

    assert result["next_cursor"] == "cursor-2"
    assert result["count"] == 1
    assert client.calls_of("get_favorite_tracks") == [{"first": 50}]


def test_favorites_forward_the_cursor():
    client = FakeClient({"get_favorite_albums": {"user_favorites": {"albums": connection([])}}})

    call("get_favorites", client, kind="album", cursor="abc")

    assert client.calls_of("get_favorite_albums") == [{"first": 50, "after": "abc"}]


def test_user_playlists_are_formatted():
    client = FakeClient({"get_user_playlists": {"playlists": connection([playlist_payload()])}})

    result = call("get_playlists", client)

    assert result["items"][0]["owner"] == "Starx"
    assert result["items"][0]["tracks_count"] == 42


def test_album_includes_a_page_of_tracks():
    client = FakeClient(
        {
            "get_album": {
                **album_payload(),
                "tracks": connection([track_payload()], next_page="next"),
            }
        }
    )

    result = call("get_album", client, album_id="302127", limit=5)

    assert result["title"] == "Discovery"
    assert result["tracks"]["count"] == 1
    assert result["tracks"]["next_cursor"] == "next"
    assert client.calls_of("get_album") == [{"album_id": "302127", "tracks_first": 5}]


def test_missing_album_is_a_clean_error():
    with pytest.raises(ToolError, match="not found"):
        call("get_album", FakeClient({"get_album": None}), album_id="1")


def test_artist_sections_can_be_disabled():
    client = FakeClient(
        {
            "get_artist": {
                **artist_payload(),
                "top_tracks": connection([track_payload()]),
                "albums": connection([album_payload()]),
                "bio": {"full": "A" * 1300},
            }
        }
    )

    result = call(
        "get_artist",
        client,
        artist_id="27",
        include_top_tracks=False,
        include_albums=False,
        include_bio=True,
    )

    assert "top_tracks" not in result
    assert "albums" not in result
    assert result["bio"].endswith("…")
    assert len(result["bio"]) == 1201
    assert client.calls_of("get_artist") == [{"artist_id": "27"}]


def test_artist_sections_are_requested_when_enabled():
    client = FakeClient(
        {
            "get_artist": {
                **artist_payload(),
                "top_tracks": connection([track_payload()]),
                "albums": connection([album_payload()]),
            }
        }
    )

    result = call("get_artist", client, artist_id="27", limit=3)

    assert result["top_tracks"]["count"] == 1
    assert result["albums"]["count"] == 1
    assert client.calls_of("get_artist") == [
        {"artist_id": "27", "top_tracks_first": 3, "albums_first": 3}
    ]


def test_track_detail_excludes_lyrics_by_default():
    payload = {**track_payload(), "lyrics": {"text": "One more time..."}}
    client = FakeClient({"get_track": payload})

    result = call("get_track", client, track_id="3135556")

    assert "lyrics" not in result
    assert result["isrc"] == "GBDUW0000059"
    assert result["deezer_url"] == "https://www.deezer.com/track/3135556"


def test_track_detail_can_include_lyrics():
    payload = {**track_payload(), "lyrics": {"text": "One more time...", "writers": "DP"}}
    client = FakeClient({"get_track": payload})

    result = call("get_track", client, track_id="3135556", include_lyrics=True)

    assert result["lyrics"]["text"] == "One more time..."
    assert result["lyrics"]["writers"] == "DP"


def test_get_lyrics_fails_cleanly_when_absent():
    client = FakeClient({"get_track": track_payload()})

    with pytest.raises(ToolError, match="no lyrics"):
        call("get_lyrics", client, track_id="1")


def test_get_lyrics_returns_credit_block():
    client = FakeClient(
        {"get_track": {**track_payload(), "lyrics": {"text": "  Hello  ", "copyright": "c"}}}
    )

    result = call("get_lyrics", client, track_id="1")

    assert result["text"] == "Hello"
    assert result["copyright"] == "c"


def test_charts_read_the_country_section():
    client = FakeClient({"get_charts": {"country": {"tracks": connection([track_payload()])}}})

    result = call("get_charts", client, country_code="fr", kind="track")

    assert result["count"] == 1
    assert client.calls_of("get_charts") == [{"country_code": "FR", "tracks_first": 20}]


def test_charts_without_a_country_is_a_clean_error():
    with pytest.raises(ToolError, match="no chart"):
        call("get_charts", FakeClient({"get_charts": {"country": None}}))


def test_user_charts_select_the_category():
    client = FakeClient(
        {"get_user_charts": {"charts": {"artists": connection([artist_payload()])}}}
    )

    result = call("get_user_charts", client, kind="artist")

    assert result["items"][0]["name"] == "Daft Punk"
    assert client.calls_of("get_user_charts") == [{"artists_first": 20}]


def test_recommendations_expose_every_section():
    client = FakeClient(
        {
            "get_recommendations": {
                "recommendations": {
                    "playlists": connection([playlist_payload()]),
                    "artist_playlists": connection([]),
                    "new_releases": connection([album_payload()]),
                    "artists": connection([artist_payload()]),
                    "hot_tracks": [track_payload()],
                }
            }
        }
    )

    result = call("get_recommendations", client)

    assert set(result) == {"playlists", "artist_playlists", "new_releases", "artists", "hot_tracks"}
    assert result["hot_tracks"]["count"] == 1
    assert client.calls_of("get_recommendations")[0]["hot_tracks_limit"] == 20


def test_non_numeric_id_is_rejected_before_any_call():
    client = FakeClient()

    with pytest.raises(ToolError, match="numeric id"):
        call("get_track", client, track_id="https://www.deezer.com/track/1")

    assert client.calls == []


def test_limits_are_clamped():
    client = FakeClient({"get_flow": {"flow": {"tracks": []}}})

    call("get_flow", client, limit=999)

    assert client.calls == [("get_flow", {})]
