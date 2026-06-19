# Contributing to mcp-deezer

Thanks for your interest in contributing!

## Getting Started

```bash
git clone https://github.com/Benitoow/mcp-deezer.git
cd mcp-deezer
pip install -e ".[dev]"
```

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
python test_server.py
```

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
