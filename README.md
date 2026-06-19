# mcp-deezer

> **Deezer MCP server** for AI agents — manage your playlists, favorites, search, and discover music. Works even though Deezer closed their developer portal.

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

## Why?

Deezer [closed their developer portal](https://en.deezercommunity.com/features-feedback-44/api-auth-impossible-80857) in 2025 and hasn't reopened it since. No new OAuth apps can be created.

This server uses an **unofficial approach**: your browser session cookie (ARL) + Deezer's internal GraphQL API. No app registration, no OAuth, no API keys.

## Features — 29 tools

| Category | Tools |
|---|---|
| 🔍 **Search** | `search` (tracks, albums, artists, playlists) |
| 🎵 **Browse** | `get_track` (with lyrics), `get_artist`, `get_album`, `get_playlist` |
| 📊 **Discovery** | `get_charts`, `get_similar_tracks`, `get_similar_artists`, `get_flow`, `get_recommendations`, `get_recently_played`, `get_user_charts` |
| ❤️ **Favorites** | `get_favorite_*`, `add/remove_track/album/artist_to_favorite` |
| 📋 **Playlists** | `get_user_playlists`, `create/update/delete_playlist`, `add/remove_tracks_to_playlist` |
| 👤 **Profile** | `get_me` |

## Quick Start

### 1. Get your ARL cookie

1. Go to [deezer.com](https://deezer.com) and **log in**
2. Press `F12` → **Application** → **Cookies** → `deezer.com`
3. Find the cookie named **`arl`** and copy its value (~192 char hex string)

### 2. Install & run

Pick your preferred method:

#### uvx (no install needed)

```bash
uvx --from mcp-deezer mcp-deezer
```

#### pip

```bash
pip install mcp-deezer
mcp-deezer
```

#### From source

```bash
git clone https://github.com/YOUR_USERNAME/mcp-deezer.git
cd mcp-deezer
pip install -e .
mcp-deezer
```

### 3. Configure your MCP client

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": {
        "DEEZER_ARL": "your_arl_cookie_here"
      }
    }
  }
}
```

#### Claude Code

```bash
claude mcp add deezer -e DEEZER_ARL=your_arl_cookie_here -- uvx mcp-deezer
```

#### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": {
        "DEEZER_ARL": "your_arl_cookie_here"
      }
    }
  }
}
```

#### Hermes Agent

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  deezer:
    command: uvx
    args: [mcp-deezer]
    env:
      DEEZER_ARL: "your_arl_cookie_here"
```

#### VS Code (Copilot)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "deezer": {
      "command": "uvx",
      "args": ["mcp-deezer"],
      "env": {
        "DEEZER_ARL": "your_arl_cookie_here"
      }
    }
  }
}
```

## Example Prompts

Once connected, ask your AI agent:

- *"Show me my playlists"*
- *"Create a playlist called 'Workout' and add the top 3 tracks by Ninho"*
- *"Search for French rap and add the first 5 results to my playlist"*
- *"What are the current charts in France?"*
- *"Find tracks similar to Un Poco by Ninho"*
- *"Unlike all tracks from my 'Test' playlist then delete it"*
- *"What's in my listening history?"*

## How It Works

This server uses [`deezer-python-gql`](https://github.com/music-assistant/deezer-python-gql), an unofficial Python client for Deezer's internal GraphQL Pipe API. Authentication is done via the ARL cookie — a session token that Deezer stores in your browser when you log in.

```
┌─────────────┐     MCP (stdio)     ┌──────────────┐     GraphQL      ┌─────────┐
│  AI Agent   │ ◄──────────────────► │  mcp-deezer  │ ◄──────────────► │  Deezer  │
│  (Claude,   │                      │  (this)      │                  │  API     │
│   Hermes...)│                      └──────────────┘                  └─────────┘
└─────────────┘                            ▲
                                           │
                                    ARL cookie (auth)
```

## Security

- **ARL stored in MCP client config** (env var), never in source code
- **No data sent to third parties** — direct connection to Deezer only
- **Session-scoped** — ARL expires if you change your password or log out
- **Local only** — server runs on your machine via stdio

## Requirements

- **Python 3.12+**
- **A Deezer account** (free or premium)
- **ARL cookie** from your browser session

## FAQ

### Is this against Deezer's ToS?

This uses the same API that Deezer's own web player uses. It's your own account, your own data, accessed via your own session cookie. Use at your own discretion.

### My ARL expired / stopped working

Log out and back in to [deezer.com](https://deezer.com), then grab the new ARL cookie.

### Can I use this with a free account?

Yes. Unlike Spotify's API (which requires Premium), Deezer's API works with free accounts.

### Why not use the official Deezer API?

Deezer closed their developer portal in 2025 due to abuse. No new apps can be registered. This is the only way to programmatically access Deezer.

## Development

```bash
git clone https://github.com/YOUR_USERNAME/mcp-deezer.git
cd mcp-deezer
pip install -e ".[dev]"

# Run tests
python test_server.py

# Run the server
python -m mcp_deezer.server
```

## License

MIT — see [LICENSE](LICENSE)

## Credits

- [deezer-python-gql](https://github.com/music-assistant/deezer-python-gql) — unofficial Deezer GraphQL client
- [Model Context Protocol](https://modelcontextprotocol.io/) — the MCP standard
