from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.settings import ProxySettings

_SINGLETON_ID = 1


class ProxySettingsDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> ProxySettings | None:
        result = await self.session.execute(
            select(ProxySettings).where(ProxySettings.id == _SINGLETON_ID)
        )
        return result.scalar_one_or_none()

    async def update(self, **fields) -> ProxySettings:
        obj = await self.get()
        if obj is None:
            obj = ProxySettings(id=_SINGLETON_ID)
            self.session.add(obj)
        for key, value in fields.items():
            setattr(obj, key, value)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
