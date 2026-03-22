import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, require_admin
from bot.dao.site_setting import (
    AD_BUTTON_TEXT,
    AD_ENABLED,
    AD_TEXT,
    AD_URL,
    BRAND_LOGO_URL,
    BRAND_NAME,
    SiteSettingDAO,
)
from bot.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

UPLOADS_DIR = Path("/app/uploads")

# Разрешённые MIME-типы для логотипа
_ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/svg+xml",
    "image/webp",
    "image/gif",
}
_MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminSettingsResponse(BaseModel):
    brand_name: str
    brand_logo_url: str
    ad_enabled: bool
    ad_url: str
    ad_text: str
    ad_button_text: str


class AdminSettingsUpdate(BaseModel):
    brand_name: str | None = None
    ad_enabled: bool | None = None
    ad_url: str | None = None
    ad_text: str | None = None
    ad_button_text: str | None = None


class LogoUploadResponse(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


_ALL_SETTINGS_KEYS = [BRAND_NAME, BRAND_LOGO_URL, AD_ENABLED, AD_URL, AD_TEXT, AD_BUTTON_TEXT]


def _build_settings_response(data: dict) -> AdminSettingsResponse:
    return AdminSettingsResponse(
        brand_name=data[BRAND_NAME] or "",
        brand_logo_url=data[BRAND_LOGO_URL] or "",
        ad_enabled=data[AD_ENABLED] == "true",
        ad_url=data[AD_URL] or "",
        ad_text=data[AD_TEXT] or "",
        ad_button_text=data[AD_BUTTON_TEXT] or "Подробнее",
    )


@router.get("/settings", response_model=AdminSettingsResponse)
async def get_admin_settings(
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """Получить текущие настройки (только для администратора)."""
    dao = SiteSettingDAO(session)
    data = await dao.get_many(_ALL_SETTINGS_KEYS)
    return _build_settings_response(data)


@router.put("/settings", response_model=AdminSettingsResponse)
async def update_admin_settings(
    body: AdminSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """Обновить настройки бренда и рекламного баннера."""
    dao = SiteSettingDAO(session)

    if body.brand_name is not None:
        await dao.set(BRAND_NAME, body.brand_name.strip() or None)
    if body.ad_enabled is not None:
        await dao.set(AD_ENABLED, "true" if body.ad_enabled else "")
    if body.ad_url is not None:
        await dao.set(AD_URL, body.ad_url.strip() or None)
    if body.ad_text is not None:
        await dao.set(AD_TEXT, body.ad_text.strip() or None)
    if body.ad_button_text is not None:
        await dao.set(AD_BUTTON_TEXT, body.ad_button_text.strip() or None)

    data = await dao.get_many(_ALL_SETTINGS_KEYS)
    return _build_settings_response(data)


@router.post("/settings/logo", response_model=LogoUploadResponse)
async def upload_logo(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    """Загрузить логотип бренда (PNG / JPEG / SVG / WebP / GIF, до 2 МБ)."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                "Allowed: PNG, JPEG, SVG, WebP, GIF."
            ),
        )

    content = await file.read()
    if len(content) > _MAX_LOGO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File too large. Maximum size is 2 MB.",
        )

    # Определяем расширение по MIME-типу
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/svg+xml": "svg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    ext = ext_map[file.content_type]

    # Удаляем старые версии логотипа перед сохранением нового
    for old_file in UPLOADS_DIR.glob("logo.*"):
        old_file.unlink(missing_ok=True)

    logo_path = UPLOADS_DIR / f"logo.{ext}"
    logo_path.write_bytes(content)

    url = f"/uploads/logo.{ext}"
    dao = SiteSettingDAO(session)
    await dao.set(BRAND_LOGO_URL, url)

    logger.info("Logo uploaded: %s (%d bytes)", logo_path, len(content))
    return LogoUploadResponse(url=url)
