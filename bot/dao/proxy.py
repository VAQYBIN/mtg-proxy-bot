from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models.proxy import Proxy


class ProxyDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_proxies(self, user_id: int) -> list[Proxy]:
        result = await self.session.execute(
            select(Proxy)
            .where(Proxy.user_id == user_id, Proxy.is_active == True)
            .options(joinedload(Proxy.node))
            .order_by(Proxy.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, proxy_id: int) -> Proxy | None:
        result = await self.session.execute(
            select(Proxy)
            .where(Proxy.id == proxy_id)
            .options(joinedload(Proxy.node))
        )
        return result.scalar_one_or_none()

    async def get_user_proxy_on_node(self, user_id: int, node_id: int) -> Proxy | None:
        result = await self.session.execute(
            select(Proxy).where(
                Proxy.user_id == user_id,
                Proxy.node_id == node_id,
                Proxy.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        node_id: int,
        mtg_username: str,
        link: str,
        port: int,
        secret: str,
        expires_at: datetime | None = None,
        traffic_limit_gb: float | None = None,
    ) -> Proxy:
        proxy = Proxy(
            user_id=user_id,
            node_id=node_id,
            mtg_username=mtg_username,
            link=link,
            port=port,
            secret=secret,
            expires_at=expires_at,
            traffic_limit_gb=traffic_limit_gb,
        )
        self.session.add(proxy)
        await self.session.commit()
        await self.session.refresh(proxy)
        return proxy

    async def delete(self, proxy: Proxy) -> None:
        proxy.is_active = False
        await self.session.commit()
