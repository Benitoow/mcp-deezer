<div align="center">

# mcp-deezer

**Unofficial Deezer MCP server for AI agents** — search music, manage playlists and favorites,
and reach your personalized discovery through **21 tools**.

[![PyPI](https://img.shields.io/pypi/v/mcp-deezer.svg)](https://pypi.org/project/mcp-deezer/) [![CI](https://github.com/Benitoow/mcp-deezer/actions/workflows/ci.yml/badge.svg)](https://github.com/Benitoow/mcp-deezer/actions/workflows/ci.yml) [![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![License: MIT](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

[Quick start](#quick-start) · [Tools](#tools) · [Configuration](#configuration) · [Troubleshooting](#troubleshooting)

</div>

## Highlights

- **21 tools, fully typed** — every tool ships an `outputSchema` and MCP annotations, so clients
  can validate results and gate the five write tools.
- **One response envelope** — every list answers `{items, count, total, next_cursor}`; paging is a
  `cursor` argument, not a guess.
- **Safe by default** — `DEEZER_READ_ONLY=1` removes the write tools from the catalog entirely.
- **Built for real sessions** — retries with backoff on 429/5xx, actionable errors, and the ARL is
  redacted from every message.

## Why this exists

Deezer [closed their developer portal](https://en.deezercommunity.com/features-feedback-44/api-auth-impossible-80857)
to new applications in 2025. `mcp-deezer` drives Deezer's internal Pipe GraphQL API with your own
authenticated browser session, so there is no developer app to register and no API key to request.

```text
MCP client  ── stdio / JSON-RPC ──▶  mcp-deezer  ── Pipe GraphQL (ARL) ──▶  Deezer
```

> [!NOTE]
> The API is unofficial and can change without notice. This project is not affiliated with or
> endorsed by Deezer.

## Quick start

### 1 · Install

```bash
uvx mcp-deezer          # no persistent install
pipx install mcp-deezer # or a global command
```

### 2 · Get your ARL cookie

This step is manual, in a browser:

1. Go to <https://deezer.com> and log in.
2. Press <kbd>F12</kbd> → **Application** → **Cookies** → `deezer.com`.
3. Copy the value of the cookie named `arl` (~192 hex characters).

> [!CAUTION]
> The ARL is a session credential: anyone who has it can act as your account. Never commit it,
> paste it in an issue, or share it. Prefer `DEEZER_ARL_FILE` over a raw value in a client
> configuration file. See [SECURITY.md](SECURITY.md).

### 3 · Register the server

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": { "DEEZER_ARL": "PASTE_ARL_HERE" }
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add deezer -e DEEZER_ARL=PASTE_ARL_HERE -- uvx mcp-deezer
```

**Cursor** (`.cursor/mcp.json`) and **VS Code / Copilot** (`.vscode/mcp.json`) use the same
`command` / `args` / `env` shape as Claude Desktop; VS Code takes the top-level key `servers`.

**Recommended for anything automated** — keep the cookie out of the config file:

```json
"env": { "DEEZER_ARL_FILE": "/home/you/.config/deezer/arl", "DEEZER_READ_ONLY": "1" }
```

### 4 · Verify

Restart the client and call `get_me`. It answers with your numeric Deezer user id:

```text
get_me → { "id": "1234567890" }
```

An error naming `DEEZER_ARL` means the cookie is missing; an error asking you to refresh it means
the session expired.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DEEZER_ARL` | — | ARL cookie value (required unless `DEEZER_ARL_FILE` is set) |
| `DEEZER_ARL_FILE` | — | Path to a file containing the ARL (read at startup, `chmod 600` recommended) |
| `DEEZER_READ_ONLY` | `0` | `1` hides **and** refuses the 5 write tools |
| `DEEZER_TIMEOUT` | `30` | Per-request timeout in seconds (1–300) |
| `DEEZER_LOG_LEVEL` | `WARNING` | `CRITICAL`, `ERROR`, `WARNING`, `INFO` or `DEBUG` (logs go to stderr) |

## Tools

Every tool is annotated (`readOnlyHint`, `destructiveHint`, `idempotentHint`), validates its
arguments, and returns a structured object.

### Read

| Tool | Purpose |
|---|---|
| `get_me` | Your Deezer user id |
| `search` | Search tracks/albums/artists/playlists, one category at a time with `kind` |
| `get_track` | Track details; lyrics only with `include_lyrics` |
| `get_lyrics` | Lyrics text and credits for one track |
| `get_artist` | Artist + optional top tracks, albums and bio |
| `get_album` | Album + tracklist (pageable) |
| `get_playlist` | Playlist + tracks (pageable) |
| `get_charts` | Country or worldwide charts, one category with `kind` |
| `get_similar_tracks` | Tracks similar to a track |
| `get_similar_artists` | Artists related to an artist |
| `get_flow` | Your personal Flow |
| `get_recommendations` | Recommended playlists, new releases, artists, hot tracks |
| `get_recently_played` | Recently played **containers** (album, playlist, artist, Flow) |
| `get_user_charts` | Your top tracks, artists or albums |
| `get_favorites` | Your liked tracks, albums, artists or playlists (`kind`) |
| `get_playlists` | Your playlists |

### Write

| Tool | Purpose | Notes |
|---|---|---|
| `set_favorite` | Like/unlike a track, album, artist or playlist | idempotent |
| `edit_playlist_tracks` | Add or remove tracks (batched by 50) | reports what Deezer applied and rejected |
| `create_playlist` | Create a playlist, optionally with tracks | one call instead of create + add |
| `update_playlist` | Rename, change description, privacy or collaborative flag | |
| `delete_playlist` | Permanently delete a playlist | requires `confirm: true` |

## Response shape

Every list tool answers with the same object, so clients can validate it and agents can page it:

```json
{
  "items": [{ "id": "3135556", "title": "One More Time", "artist": "Daft Punk", "album": "Discovery", "duration": 320 }],
  "count": 1,
  "total": null,
  "next_cursor": null
}
```

- Pass `next_cursor` back as the `cursor` argument to page.
- Detail tools return a flat object (`get_track`, `get_artist`, `get_playlist`…).
- Failures are `isError` results with an actionable message: how to refresh the ARL, wait out a
  rate limit, or fix the arguments.
- Lyrics, long biographies and track links are opt-in or truncated on purpose: they dominate token
  cost.

<details>
<summary><b>Upgrading from 1.x</b> — tool names changed in 2.0</summary>

| 1.x | 2.x |
|---|---|
| `get_favorite_tracks` / `_albums` / `_artists` / `_playlists` | `get_favorites` with `kind` |
| `add_track_to_favorite`, `remove_track_from_favorite`, … (6 tools) | `set_favorite` with `kind` + `action` |
| `get_user_playlists` | `get_playlists` |
| `add_tracks_to_playlist` / `remove_tracks_from_playlist` | `edit_playlist_tracks` with `action` |
| `get_track` (always included lyrics) | `get_track` + `include_lyrics`, or `get_lyrics` |
| list tools returning an array | every tool returns an object (MCP requirement) |
| `delete_playlist` without confirmation | `delete_playlist` requires `confirm: true` |

</details>

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `DEEZER_ARL is not set` | Set `DEEZER_ARL` or `DEEZER_ARL_FILE`, then restart the MCP client |
| `Deezer session was rejected (ARL expired…)` | Log out/in on deezer.com, copy the new `arl`, restart |
| `Deezer rate limit reached` | Several calls at once; wait a few seconds (reads retry automatically) |
| Empty `items` on a favorites/charts call | The account has no data for that category, or the country code has no chart |
| A write returns `success: false` with `rejected` ids | Deezer refused those tracks (unavailable in your country, or not your playlist) |
| A write returns 403/`is_not_allowed` | The playlist does not belong to the account |
| Nothing appears in the client | Check the MCP log: the server writes to stderr, never to stdout |

## Development

```bash
git clone https://github.com/Benitoow/mcp-deezer.git && cd mcp-deezer
uv venv && uv pip install -e ".[dev]"

ruff check . && ruff format --check .   # lint + format
mypy                                    # strict typing
pytest --cov                            # 120+ tests, no Deezer account required
python scripts/smoke.py                 # real stdio handshake (+ live calls if DEEZER_ARL is set)
```

Layout: `catalog.py` (schemas, annotations, registry), `tools_read.py` / `tools_write.py`
(one handler per tool), `formats.py` (compact projections), `client.py` (client lifecycle + retries),
`errors.py` (redaction, actionable messages), `server.py` (MCP wiring).

Adding a tool is one decorated function: the schema, the annotations, the output schema and the
handler live together, so the advertised surface cannot drift from the implementation.

## Security

The ARL is never written to disk by the server and is redacted from every error message.
`DEEZER_READ_ONLY=1` removes the write tools entirely, which is the recommended setting for
unattended agents. See [SECURITY.md](SECURITY.md).

---

<div align="center">

**MIT licensed** · Not affiliated with, or endorsed by, Deezer

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

</div>
