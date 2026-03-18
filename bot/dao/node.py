from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.node import Node


class NodeDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_active(self) -> list[Node]:
        result = await self.session.execute(
            select(Node).where(Node.is_active.is_(True)).order_by(Node.id)
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[Node]:
        result = await self.session.execute(select(Node).order_by(Node.id))
        return list(result.scalars().all())

    async def set_active(self, node: Node, active: bool) -> None:
        node.is_active = active
        await self.session.commit()

    async def get_by_id(self, node_id: int) -> Node | None:
        result = await self.session.execute(
            select(Node).where(Node.id == node_id)
        )
        return result.scalar_one_or_none()

    async def get_by_panel_id(self, panel_id: int) -> Node | None:
        result = await self.session.execute(
            select(Node).where(Node.panel_id == panel_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        panel_id: int,
        name: str,
        host: str,
        flag: str | None,
        agent_port: int | None = None,
    ) -> Node:
        node = await self.get_by_panel_id(panel_id)
        if node:
            node.name = name
            node.host = host
            node.flag = flag
            node.agent_port = agent_port
        else:
            node = Node(
                panel_id=panel_id, name=name, host=host,
                flag=flag, agent_port=agent_port,
            )
            self.session.add(node)
        await self.session.commit()
        await self.session.refresh(node)
        return node
