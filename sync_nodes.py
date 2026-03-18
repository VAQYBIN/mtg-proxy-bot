import asyncio

from bot.database import async_session_factory
from bot.dao import NodeDAO
from bot.services.admin_panel import admin_panel


async def main():
    nodes = await admin_panel.get_nodes()
    async with async_session_factory() as session:
        dao = NodeDAO(session)
        for n in nodes:
            await dao.upsert(n["id"], n["name"], n["host"], n.get("flag"))
    print(f"Synced {len(nodes)} nodes:")
    for n in nodes:
        print(f"  [{n['id']}] {n['name']} ({n['host']})")


asyncio.run(main())
