# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2.0.0 — 2026-11-18

This release fixes a class of bugs that made parts of the server silently useless, and reshapes
the tool surface so an agent can actually rely on it. Tool names changed: see *Changed* and the
migration table in the README.

### Fixed

- Ten tools (`get_flow`, `get_favorite_*`, `get_user_playlists`, `get_charts`,
  `get_similar_tracks`, `get_similar_artists`, `get_recently_played`) returned a JSON array in
  `structuredContent`, which the MCP layer rejects with `Handler returned an invalid result`.
  Every tool now answers with an object.
- `get_similar_tracks`, `get_similar_artists` and `get_flow` returned `[]` even when Deezer had
  data: the handlers guessed camelCase paths (`similarTracks`, `me.flowTracks`) that the typed
  client never produces. They now read the documented model fields.
- `add_tracks_to_playlist` reported `success: true` even when Deezer refused the batch
  (`is_not_allowed`). Mutations now report the ids Deezer actually applied and the rejected ones.
- `get_recently_played` mapped albums, playlists and artists onto a track shape, including a
  fabricated `https://www.deezer.com/track/<id>` link. Containers now keep their type.
- `get_me` no longer pretends to return a full profile: the Pipe API only exposes the user id.

### Changed

- Tool surface reduced from 29 to 21 tools: symmetric favorites and playlist mutations are
  merged into `set_favorite` / `edit_playlist_tracks`, and `get_favorite_*` into `get_favorites`.
  Every parameter is now documented and ids are pattern-validated; the catalog costs ~3.7k tokens
  of definitions (against ~1.5k for the terse, ambiguous v1 schemas — the ids had no description
  at all, which is how agents end up passing URLs).
- Every list result uses one envelope: `{items, count, total, next_cursor}`. Pagination is exposed
  through `cursor` on playlists, albums, favorites and artist sections.
- `get_track` no longer embeds lyrics by default; `get_lyrics` is a separate tool.
- `get_artist` sections (top tracks, albums, bio) are opt-in flags; biographies are truncated.
- `search`, `get_charts` and `get_user_charts` take a `kind`, so a call only pays for what it returns.
- `Deezer` ids are validated as numeric strings and result sizes are bounded (`limit` 1–100).

### Added

- MCP annotations on every tool (`readOnlyHint`, `destructiveHint`, `idempotentHint`) and
  `outputSchema`, so clients can gate writes and validate structured results.
- Server `instructions`, documenting id format, the meaning of `next_cursor` and the
  confirmation rule for destructive tools.
- `delete_playlist` requires `confirm: true`; `create_playlist` accepts `track_ids`.
- `DEEZER_READ_ONLY=1` removes the five write tools from `tools/list` and from dispatch.
- `DEEZER_ARL_FILE` (keep the cookie out of client config files) and `DEEZER_TIMEOUT`.
- Retry with exponential backoff for reads on 429/5xx; writes retry only on 429, so a mutation is
  never applied twice.
- Actionable error messages: expired ARL, rate limit, 5xx, invalid arguments.
- HTTP session closed on shutdown (`lifespan`), client creation guarded by a lock, structured
  logging to stderr.
- Tests: 120+ cases covering the wire protocol, the catalog contract, every handler and the retry
  policy; `mypy --strict`; coverage gate in CI.
- `server.json` for the MCP registry, a PyPI trusted-publishing workflow, `pre-commit` config and
  `scripts/smoke.py`.

### Changed (dependencies)

- `mcp>=2.3,<3` (2.0/2.1 rejected array structured content), `deezer-python-gql>=0.24,<0.25`,
  explicit `aiohttp` dependency for the timeout/connector we now provide.

## 1.0.0 — 2026-08-21

- Initial stable release: 29 tools over Deezer's Pipe GraphQL API, ARL authentication,
  MCP Python SDK 2.x handler API, JSON Schema validation, structured tool results.
