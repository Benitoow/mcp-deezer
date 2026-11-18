"""Launch the server over stdio, verify discovery, and optionally run live read calls.

Usage:  python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Legacy Windows consoles default to a code page that cannot encode every message.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_deezer.server"],
        env={**os.environ},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"[OK] {len(tools.tools)} tools discovered")
            for tool in tools.tools:
                assert tool.annotations is not None, tool.name
                assert tool.output_schema is not None, tool.name
            print("[OK] every tool has annotations and an output schema")

            if not (os.environ.get("DEEZER_ARL") or os.environ.get("DEEZER_ARL_FILE")):
                print("DEEZER_ARL / DEEZER_ARL_FILE not set: discovery only")
                return 0

            read_only_calls = [
                ("get_me", {}),
                ("search", {"query": "Daft Punk", "kind": "track", "limit": 2}),
                ("get_playlists", {"limit": 3}),
            ]
            for name, arguments in read_only_calls:
                result = await session.call_tool(name, arguments)
                if result.is_error:
                    print(f"[FAIL] {name}: {result.content[0].text}")
                    return 1
                payload = result.structured_content
                assert isinstance(payload, dict), f"{name} returned {type(payload).__name__}"
                print(f"[OK] {name}: {json.dumps(payload, ensure_ascii=False)[:120]}")

    print("[OK] smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
