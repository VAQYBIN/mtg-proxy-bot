import hashlib
import hmac
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_session
from api.jwt import create_access_token
from bot.config import settings
from bot.dao.account_link_token import AccountLinkTokenDAO
from bot.dao.user import UserDAO
from bot.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["user"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    id: int
    telegram_id: int | None
    username: str | None
    first_name: str | None
    display_name: str | None
    email: str | None
    email_verified: bool
    is_banned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LinkRequestResponse(BaseModel):
    code: str
    expires_at: datetime


class LinkMiniAppRequest(BaseModel):
    init_data: str


class LinkMiniAppResponse(BaseModel):
    user: UserResponse
    access_token: str | None = None  # новый JWT, если user_id изменился


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verify_miniapp(init_data: str) -> dict | None:
    """Проверить подпись Mini App initData (дубль из auth.py для изоляции)."""
    from urllib.parse import parse_qsl

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        return None
    return parsed


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/link/request", response_model=LinkRequestResponse)
async def link_request(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Запросить код для привязки Telegram через бот (/link <код>)."""
    if current_user.telegram_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account already linked to Telegram",
        )

    token_dao = AccountLinkTokenDAO(session)
    await token_dao.invalidate_pending(current_user.id)
    token = await token_dao.create(current_user.id)
    return LinkRequestResponse(code=token.code, expires_at=token.expires_at)


@router.post("/me/link/miniapp", response_model=LinkMiniAppResponse)
async def link_miniapp(
    body: LinkMiniAppRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Привязать Telegram через Mini App initData."""
    parsed = _verify_miniapp(body.init_data)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Mini App data",
        )

    user_data = json.loads(parsed.get("user", "{}"))
    tg_id = user_data.get("id")
    if not tg_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user data in initData",
        )

    if current_user.telegram_id == tg_id:
        # Уже привязан к тому же Telegram-аккаунту
        return LinkMiniAppResponse(
            user=UserResponse.model_validate(current_user)
        )

    if current_user.telegram_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account already linked to a different Telegram account",
        )

    user_dao = UserDAO(session)
    tg_user_db = await user_dao.get_by_telegram_id(tg_id)

    if tg_user_db is None:
        # Простой случай: Telegram-аккаунта в БД нет → просто добавляем
        current_user.telegram_id = tg_id
        current_user.first_name = (
            current_user.first_name or user_data.get("first_name")
        )
        current_user.username = (
            current_user.username or user_data.get("username")
        )
        current_user.language_code = user_data.get("language_code")
        await session.commit()
        await session.refresh(current_user)
        return LinkMiniAppResponse(
            user=UserResponse.model_validate(current_user)
        )

    # Два отдельных аккаунта → merge (старший остаётся основным)
    if tg_user_db.created_at <= current_user.created_at:
        # Telegram-аккаунт старше → оставляем его, current_user удаляем
        if tg_user_db.email is None:
            tg_user_db.email = current_user.email
            tg_user_db.email_verified = current_user.email_verified
            await session.commit()
        merged = await user_dao.merge_into(
            source=current_user, target=tg_user_db
        )
        new_token = create_access_token(merged.id)
        return LinkMiniAppResponse(
            user=UserResponse.model_validate(merged),
            access_token=new_token,
        )
    else:
        # Web-аккаунт старше → оставляем его, добавляем telegram_id
        current_user.telegram_id = tg_id
        current_user.first_name = (
            current_user.first_name or user_data.get("first_name")
        )
        current_user.username = (
            current_user.username or user_data.get("username")
        )
        current_user.language_code = user_data.get("language_code")
        await session.commit()
        merged = await user_dao.merge_into(
            source=tg_user_db, target=current_user
        )
        return LinkMiniAppResponse(
            user=UserResponse.model_validate(merged)
        )
