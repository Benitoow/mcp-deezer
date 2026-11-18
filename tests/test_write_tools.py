from __future__ import annotations

import asyncio

import pytest

from mcp_deezer import catalog
from mcp_deezer.config import WRITE_BATCH
from mcp_deezer.errors import ToolError
from tests.fakes import FakeClient, playlist_payload, track_payload


def call(tool: str, client: FakeClient, **args) -> dict:
    return asyncio.run(catalog.REGISTRY[tool].handler(client, args))


def test_set_favorite_uses_the_right_mutation_per_kind():
    client = FakeClient(
        {"add_playlist_to_favorite": {"playlist": {"id": "9", "is_favorite": True}}}
    )

    result = call("set_favorite", client, kind="playlist", id="9", action="add")

    assert client.calls == [("add_playlist_to_favorite", {"playlist_id": "9"})]
    assert result == {
        "success": True,
        "kind": "playlist",
        "id": "9",
        "action": "add",
        "is_favorite": True,
    }


def test_set_favorite_remove_uses_the_remove_mutation():
    client = FakeClient({"remove_track_from_favorite": {"track": track_payload()}})

    call("set_favorite", client, kind="track", id="3135556", action="remove")

    assert client.calls == [("remove_track_from_favorite", {"track_id": "3135556"})]


def test_edit_playlist_tracks_reports_what_deezer_applied():
    client = FakeClient({"add_tracks_to_playlist": {"added_track_ids": ["1", "2"]}})

    result = call("edit_playlist_tracks", client, playlist_id="9", track_ids=["1", "2"])

    assert result["updated"] == ["1", "2"]
    assert result["rejected"] == []
    assert result["success"] is True


def test_edit_playlist_tracks_fails_when_deezer_refuses():
    client = FakeClient({"add_tracks_to_playlist": {"is_not_allowed": True}})

    with pytest.raises(ToolError, match="changed nothing"):
        call("edit_playlist_tracks", client, playlist_id="9", track_ids=["1", "2"])


def test_edit_playlist_tracks_reports_partial_additions():
    client = FakeClient({"add_tracks_to_playlist": {"added_track_ids": ["1"]}})

    result = call("edit_playlist_tracks", client, playlist_id="9", track_ids=["1", "2"])

    assert result["success"] is False
    assert result["updated"] == ["1"]
    assert result["rejected"] == ["2"]


def test_edit_playlist_tracks_batches_large_lists():
    def add(**kwargs):
        return {"added_track_ids": list(kwargs["track_ids"])}

    client = FakeClient({"add_tracks_to_playlist": add})
    track_ids = [str(index) for index in range(120)]

    result = call("edit_playlist_tracks", client, playlist_id="9", track_ids=track_ids)

    batches = [
        call_kwargs["track_ids"] for call_kwargs in client.calls_of("add_tracks_to_playlist")
    ]
    assert [len(batch) for batch in batches] == [WRITE_BATCH, WRITE_BATCH, 20]
    assert result["count"] == 120


def test_edit_playlist_tracks_removal_reports_removed_ids():
    client = FakeClient({"remove_tracks_from_playlist": {"removed_track_ids": ["1"]}})

    result = call(
        "edit_playlist_tracks", client, playlist_id="9", track_ids=["1", "2"], action="remove"
    )

    assert result["updated"] == ["1"]
    assert result["rejected"] == ["2"]


def test_create_playlist_adds_initial_tracks_in_one_call():
    client = FakeClient(
        {
            "create_playlist": {"playlist": {"id": "9", "title": "Focus"}},
            "add_tracks_to_playlist": {"added_track_ids": ["1"]},
        }
    )

    result = call("create_playlist", client, title="Focus", track_ids=["1"])

    assert result["playlist"]["title"] == "Focus"
    assert result["updated"] == ["1"]
    assert client.calls_of("create_playlist") == [
        {"title": "Focus", "description": None, "is_private": False, "is_collaborative": False}
    ]


def test_create_playlist_without_tracks_does_not_add_anything():
    client = FakeClient({"create_playlist": {"playlist": {"id": "9", "title": "Focus"}}})

    call("create_playlist", client, title="Focus")

    assert client.calls_of("add_tracks_to_playlist") == []


def test_update_playlist_requires_a_change():
    with pytest.raises(ToolError, match="Nothing to update"):
        call("update_playlist", FakeClient(), playlist_id="9")


def test_update_playlist_sends_only_the_changes():
    client = FakeClient({"update_playlist": {}})

    result = call("update_playlist", client, playlist_id="9", title="New", private=True)

    assert client.calls_of("update_playlist") == [
        {"playlist_id": "9", "title": "New", "is_private": True}
    ]
    assert result["updated"] == ["is_private", "title"]


def test_delete_playlist_requires_explicit_confirmation():
    client = FakeClient()

    with pytest.raises(ToolError, match="confirm"):
        call("delete_playlist", client, playlist_id="9", confirm=False)

    assert client.calls == []


def test_delete_playlist_runs_when_confirmed():
    client = FakeClient({"delete_playlist": {}})

    result = call("delete_playlist", client, playlist_id="9", confirm=True)

    assert client.calls == [("delete_playlist", {"playlist_id": "9"})]
    assert result["deleted"] is True


def test_track_ids_must_be_numeric_and_unique():
    client = FakeClient()

    with pytest.raises(ToolError, match="non-numeric"):
        call("edit_playlist_tracks", client, playlist_id="9", track_ids=["abc"])


def test_duplicate_track_ids_are_collapsed():
    def add(**kwargs):
        return {"added_track_ids": list(kwargs["track_ids"])}

    client = FakeClient({"add_tracks_to_playlist": add})

    result = call("edit_playlist_tracks", client, playlist_id="9", track_ids=["1", "1", "2"])

    assert result["updated"] == ["1", "2"]


def test_playlist_payload_is_not_mutated_by_create():
    client = FakeClient({"create_playlist": {"playlist": playlist_payload()}})

    result = call("create_playlist", client, title="Coding")

    assert result["playlist"]["id"] == "908622995"
