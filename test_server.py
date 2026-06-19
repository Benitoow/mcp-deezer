"""Quick verification: server starts, tools discovered, public endpoints work."""
import asyncio
import json
import sys
import os


async def test():
    from mcp.client.stdio import stdio_client
    from mcp import StdioServerParameters, ClientSession

    arl = os.environ.get("DEEZER_ARL", "")
    if not arl:
        print("⚠️  DEEZER_ARL not set — testing tool discovery only (no API calls)")
        env = {**os.environ}
    else:
        env = {**os.environ, "DEEZER_ARL": arl}

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_deezer.server"],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. List tools
            tools = await session.list_tools()
            print(f"✅ {len(tools.tools)} tools discovered:")
            for t in tools.tools:
                print(f"   • {t.name}")
            print()

            if not arl:
                print("Set DEEZER_ARL to run API tests.")
                return

            # 2. Test search
            r = await session.call_tool("search", {"query": "Daft Punk", "tracks_first": 2})
            data = json.loads(r.content[0].text)
            tracks = data.get("tracks", [])
            print(f"✅ search('Daft Punk'): {len(tracks)} tracks")
            for t in tracks:
                print(f"   🎵 {t['title']} — {t['artist']}")
            print()

            # 3. Test playlists
            r = await session.call_tool("get_user_playlists", {})
            playlists = json.loads(r.content[0].text)
            print(f"✅ get_user_playlists: {len(playlists)} playlists")
            for p in playlists:
                print(f"   📋 {p['title']} ({p.get('nb_tracks', '?')} tracks)")
            print()

            print("✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test())
