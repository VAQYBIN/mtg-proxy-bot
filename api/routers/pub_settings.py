from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from bot.dao.site_setting import (
    AD_BUTTON_TEXT,
    AD_ENABLED,
    AD_TEXT,
    AD_URL,
    BRAND_LOGO_URL,
    BRAND_NAME,
    SiteSettingDAO,
)

router = APIRouter(tags=["settings"])


class PublicSettingsResponse(BaseModel):
    brand_name: str
    brand_logo_url: str
    ad_enabled: bool
    ad_url: str
    ad_text: str
    ad_button_text: str


@router.get("/api/settings", response_model=PublicSettingsResponse)
async def get_public_settings(session: AsyncSession = Depends(get_session)):
    """Публичные настройки сайта — без авторизации."""
    dao = SiteSettingDAO(session)
    data = await dao.get_many([BRAND_NAME, BRAND_LOGO_URL, AD_ENABLED, AD_URL, AD_TEXT, AD_BUTTON_TEXT])
    return PublicSettingsResponse(
        brand_name=data[BRAND_NAME] or "",
        brand_logo_url=data[BRAND_LOGO_URL] or "",
        ad_enabled=data[AD_ENABLED] == "true",
        ad_url=data[AD_URL] or "",
        ad_text=data[AD_TEXT] or "",
        ad_button_text=data[AD_BUTTON_TEXT] or "Подробнее",
    )
