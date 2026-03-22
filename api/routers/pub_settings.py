from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from bot.dao.site_setting import BRAND_LOGO_URL, BRAND_NAME, SiteSettingDAO

router = APIRouter(tags=["settings"])


class PublicSettingsResponse(BaseModel):
    brand_name: str
    brand_logo_url: str


@router.get("/api/settings", response_model=PublicSettingsResponse)
async def get_public_settings(session: AsyncSession = Depends(get_session)):
    """Публичные настройки бренда — без авторизации."""
    dao = SiteSettingDAO(session)
    data = await dao.get_many([BRAND_NAME, BRAND_LOGO_URL])
    return PublicSettingsResponse(
        brand_name=data[BRAND_NAME] or "",
        brand_logo_url=data[BRAND_LOGO_URL] or "",
    )
