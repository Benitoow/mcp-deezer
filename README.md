# mcp-deezer

> Deezer MCP server for AI agents. 29 tools to search, manage playlists, favorites, and discover music. Works with a free Deezer account. No developer app needed.

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

## Why this exists

Deezer [closed their developer portal](https://en.deezercommunity.com/features-feedback-44/api-auth-impossible-80857) in 2025. No new OAuth apps. No API keys. This server uses your browser session cookie (ARL) instead. Free account, no registration, it just works.

## For AI Agents — Installation Guide

If you are an AI agent reading this to install `mcp-deezer` for a user, follow these steps in order:

### Step 1: Check prerequisites

- Python 3.12+ must be installed (`python3 --version` or `python --version`)
- If not installed, tell the user to install it from https://www.python.org/downloads/

### Step 2: Install the package

```bash
pip install mcp-deezer
```

Or with uvx (no persistent install):

```bash
uvx mcp-deezer
```

### Step 3: Get the user's Deezer ARL cookie

The user must do this manually in their browser:

1. Go to https://deezer.com and log in
2. Press F12 → Application → Cookies → `deezer.com`
3. Find the cookie named `arl` and copy its value (~192 character hex string)

The ARL looks like: `a1b2c3d4e5f6...` (192 hex chars)

### Step 4: Configure the MCP server

Add this to the user's MCP client config. The `DEEZER_ARL` environment variable is **required**.

**Claude Desktop** — `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": {
        "DEEZER_ARL": "PASTE_ARL_HERE"
      }
    }
  }
}
```

**Claude Code** — terminal:
```bash
claude mcp add deezer -e DEEZER_ARL=PASTE_ARL_HERE -- uvx mcp-deezer
```

**Cursor** — `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": {
        "DEEZER_ARL": "PASTE_ARL_HERE"
      }
    }
  }
}
```

**Hermes Agent** — `~/.hermes/config.yaml`:
```yaml
mcp_servers:
  deezer:
    command: uvx
    args: [mcp-deezer]
    env:
      DEEZER_ARL: "PASTE_ARL_HERE"
```

**VS Code / Copilot** — `.vscode/mcp.json`:
```json
{
  "servers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": {
        "DEEZER_ARL": "PASTE_ARL_HERE"
      }
    }
  }
}
```

### Step 5: Restart the MCP client

Tell the user to restart their AI client (Claude Desktop, Cursor, etc.) for the server to load.

### Step 6: Verify

Call `get_me` — it should return the user's Deezer profile ID. If it returns an error about `DEEZER_ARL`, the cookie is missing or expired.

## Available Tools (29)

| Tool | Description | Auth |
|---|---|---|
| `get_me` | User profile | ✅ |
| `search` | Search tracks, albums, artists, playlists | ✅ |
| `get_track` | Track details with lyrics | ✅ |
| `get_artist` | Artist details with bio | ✅ |
| `get_album` | Album details with tracklist | ✅ |
| `get_playlist` | Playlist details with tracks | ✅ |
| `get_charts` | Country charts (FR, US, DE...) | ✅ |
| `get_similar_tracks` | Similar tracks | ✅ |
| `get_similar_artists` | Similar artists | ✅ |
| `get_flow` | Personal Deezer Flow | ✅ |
| `get_recommendations` | Personalized recommendations | ✅ |
| `get_recently_played` | Listening history | ✅ |
| `get_user_charts` | Personal top tracks/artists | ✅ |
| `get_favorite_tracks` | Liked tracks | ✅ |
| `get_favorite_albums` | Liked albums | ✅ |
| `get_favorite_artists` | Followed artists | ✅ |
| `get_favorite_playlists` | Liked playlists | ✅ |
| `add_track_to_favorite` | Like a track | ✅ |
| `remove_track_from_favorite` | Unlike a track | ✅ |
| `add_album_to_favorite` | Like an album | ✅ |
| `remove_album_from_favorite` | Unlike an album | ✅ |
| `add_artist_to_favorite` | Follow an artist | ✅ |
| `remove_artist_from_favorite` | Unfollow an artist | ✅ |
| `get_user_playlists` | List user playlists | ✅ |
| `create_playlist` | Create a playlist | ✅ |
| `update_playlist` | Update playlist title/desc | ✅ |
| `delete_playlist` | Delete a playlist | ✅ |
| `add_tracks_to_playlist` | Add tracks to playlist | ✅ |
| `remove_tracks_from_playlist` | Remove tracks from playlist | ✅ |

## How It Works

```
AI Agent  ←── MCP (stdio) ──→  mcp-deezer  ←── GraphQL ──→  Deezer API
                                    │
                              ARL cookie (your session)
```

Uses [`deezer-python-gql`](https://github.com/music-assistant/deezer-python-gql) — an unofficial client for Deezer's internal GraphQL API. Auth is via the ARL cookie stored in your browser.

## FAQ (for agents)

**Q: The user's ARL stopped working.**
A: Tell them to log out and back in to deezer.com, then grab the new `arl` cookie.

**Q: Does this work with a free Deezer account?**
A: Yes. Unlike Spotify's API, Deezer works with free accounts.

**Q: Is this against Deezer's ToS?**
A: It uses the same API as Deezer's web player. Your account, your data, your session cookie.

**Q: Python 3.12+ is not available.**
A: Install it from https://www.python.org/downloads/ or use `uvx` which manages its own Python.

## License

MIT
