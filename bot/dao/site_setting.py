from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.site_setting import SiteSetting

# Известные ключи настроек
BRAND_NAME = "brand_name"
BRAND_LOGO_URL = "brand_logo_url"

DEFAULTS: dict[str, str] = {
    BRAND_NAME: "MTG Proxy",
    BRAND_LOGO_URL: "",
}


class SiteSettingDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> str | None:
        result = await self.session.execute(
            select(SiteSetting).where(SiteSetting.key == key)
        )
        row = result.scalar_one_or_none()
        if row is None or row.value is None:
            return DEFAULTS.get(key)
        return row.value

    async def set(self, key: str, value: str | None) -> None:
        stmt = (
            insert(SiteSetting)
            .values(key=key, value=value)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value, "updated_at": SiteSetting.updated_at},
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        result = await self.session.execute(
            select(SiteSetting).where(SiteSetting.key.in_(keys))
        )
        rows = {row.key: row.value for row in result.scalars()}
        return {
            key: (rows[key] if rows.get(key) is not None else DEFAULTS.get(key))
            for key in keys
        }
