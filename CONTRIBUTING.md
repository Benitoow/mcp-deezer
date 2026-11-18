# Contributing to mcp-deezer

Thanks for your interest in contributing!

## Getting started

```bash
git clone https://github.com/Benitoow/mcp-deezer.git
cd mcp-deezer
uv venv
uv pip install -e ".[dev]"
pre-commit install   # optional, but CI runs the same checks
```

Never place a real `DEEZER_ARL` value in a tracked file — use `DEEZER_ARL_FILE` if you need one
locally. See [SECURITY.md](SECURITY.md).

## Layout

| Module | Responsibility |
|---|---|
| `mcp_deezer/catalog.py` | JSON Schemas, MCP annotations, tool registry (`@register`) |
| `mcp_deezer/tools_read.py` | Read-only handlers |
| `mcp_deezer/tools_write.py` | Mutating handlers (all report what Deezer actually applied) |
| `mcp_deezer/formats.py` | Compact projections and the `{items, count, total, next_cursor}` envelope |
| `mcp_deezer/client.py` | Client lifecycle, ARL resolution, retry policy |
| `mcp_deezer/errors.py` | `ToolError`, redaction, actionable messages |
| `mcp_deezer/server.py` | MCP wiring (list/call handlers, lifespan, stdio entry point) |

## Adding a tool

One decorated function per tool — schema, annotations, output schema and handler together:

```python
@register(
    name="get_something",
    title="Short human title",
    description="What it returns, when to use it, and any caveat.",
    input_schema={
        "type": "object",
        "properties": {"some_id": ID, "limit": LIMIT},
        "required": ["some_id"],
        "additionalProperties": False,
    },
    output_schema=PAGE,
    idempotent=True,
)
async def get_something(client: Any, args: dict[str, Any]) -> dict[str, Any]:
    result = await call(client.get_something, some_id=require_id(args, "some_id"))
    if result is None:
        raise ToolError("…not found.")  # becomes an isError result, never a crash
    return page_from(get(result, "nodes"), track, limit=limit_of(args))
```

Rules:

- handlers **must** return a JSON object (never a list: `structuredContent` has to be an object);
- read model fields by name (`get(result, "recommended_tracks")`) — never guess camelCase paths;
- when the client returns a union (mutations), branch on the returned fields and report what was
  actually applied;
- bound every list (`limit_of`), and page with `next_cursor` when the client supports `after`;
- raise `ToolError` for expected failures, with a message the agent can act on.

## Tests

```bash
python -m pytest --cov        # no Deezer account needed
mypy                          # strict
ruff check . && ruff format --check .
python scripts/smoke.py       # real stdio handshake (+ live calls when DEEZER_ARL is set)
```

Three test layers matter:

1. `tests/test_transport.py` — real MCP session over in-memory streams (catches protocol-level bugs);
2. `tests/test_contract.py` — every tool returns an object, and every model field a handler reads
   still exists in the installed `deezer-python-gql`;
3. `tests/test_*_tools.py` — one behaviour per handler, against a fake client.

When you upgrade `deezer-python-gql`, run `test_contract.py` first: it fails loudly if a field was
renamed, instead of silently returning empty lists.

## Code style

- Python 3.12+, `from __future__ import annotations`, full type hints (mypy strict).
- Async everywhere upstream; no blocking I/O in handlers.
- Logs go to stderr only — writing to stdout corrupts the stdio transport.
- Keep responses compact: they are paid for twice (text + structured content).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
