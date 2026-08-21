# Contributing to mcp-deezer

Thanks for your interest in contributing!

## Getting Started

```bash
git clone https://github.com/Benitoow/mcp-deezer.git
cd mcp-deezer
pip install -e ".[dev]"
```

Never place a real `DEEZER_ARL` value in a tracked file. See
[SECURITY.md](SECURITY.md) for credential-handling guidance.

## Development

### Running locally

```bash
# Set your ARL
export DEEZER_ARL="your_arl_cookie"

# Run the server
python -m mcp_deezer.server
```

### Testing

```bash
# Fast unit tests (no Deezer account required)
python -m pytest

# End-to-end MCP discovery, plus optional live API checks when DEEZER_ARL is set
python test_server.py
```

### Quality checks

```bash
ruff check .
ruff format --check .
python -m build
python -m twine check dist/*
```

All checks also run in GitHub Actions on Python 3.12 and 3.13 for Linux and Windows.

## Adding New Tools

1. Add the tool definition to the `TOOLS` list in `server.py`
2. Add the handler in `_dispatch()`
3. Use the `_edges()`, `_nav()`, `_track()`, `_artist()`, `_album()`, `_playlist()` helpers
4. Test with the MCP test script

### GraphQL Response Patterns

Deezer's GraphQL API uses edges/node pagination:

```python
# Response structure
{"data": {"key": {"edges": [{"node": {...}}, ...]}}}

# Extract with
items = _edges(_nav(data, "key"))
```

## Code Style

- Python 3.12+ (type hints with `|` syntax)
- Async everywhere
- Keep tools compact — one tool = one clear action
- Format output with `_track()`, `_artist()`, `_album()`, `_playlist()` helpers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
