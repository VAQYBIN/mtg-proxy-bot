import hashlib
import hmac
import logging
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.email_service import send_verification_email
from api.jwt import create_access_token
from bot.config import settings
from bot.dao.email_verification import EmailVerificationDAO
from bot.dao.user import UserDAO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EmailRegisterRequest(BaseModel):
    email: EmailStr


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: str


class TokenVerifyRequest(BaseModel):
    token: str


class TelegramWidgetRequest(BaseModel):
    id: int
    first_name: str
    auth_date: int
    hash: str
    username: str | None = None
    last_name: str | None = None
    photo_url: str | None = None


class TelegramMiniAppRequest(BaseModel):
    init_data: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WIDGET_MAX_AGE_SECONDS = 86400  # 24 часа


def _verify_telegram_widget(data: TelegramWidgetRequest) -> bool:
    """Проверить подпись Telegram Login Widget.

    https://core.telegram.org/widgets/login#checking-authorization
    """
    fields = {
        "id": str(data.id),
        "first_name": data.first_name,
        "auth_date": str(data.auth_date),
    }
    if data.username:
        fields["username"] = data.username
    if data.last_name:
        fields["last_name"] = data.last_name
    if data.photo_url:
        fields["photo_url"] = data.photo_url

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(fields.items())
    )

    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    expected = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, data.hash):
        return False

    # Проверяем свежесть (не старше 24 часов)
    if time.time() - data.auth_date > WIDGET_MAX_AGE_SECONDS:
        return False

    return True


def _verify_telegram_miniapp(init_data: str) -> dict | None:
    """Проверить подпись Mini App initData.

    Возвращает распарсенные данные или None если подпись неверна.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
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
# Email auth endpoints
# ---------------------------------------------------------------------------


@router.post("/email/register", status_code=status.HTTP_202_ACCEPTED)
async def email_register(
    body: EmailRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Запросить код подтверждения на email.

    Всегда возвращает 202 — не раскрываем, зарегистрирован ли email.
    """
    ev_dao = EmailVerificationDAO(session)
    await ev_dao.invalidate_pending(body.email)
    ev = await ev_dao.create(body.email)
    await send_verification_email(body.email, ev.code, ev.token)
    return {"detail": "Verification code sent"}


@router.post("/email/verify", response_model=TokenResponse)
async def email_verify(
    body: EmailVerifyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Подтвердить email кодом и получить JWT."""
    ev_dao = EmailVerificationDAO(session)
    ev = await ev_dao.get_active_by_code(body.email, body.code)
    if ev is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        )

    await ev_dao.mark_used(ev)

    user_dao = UserDAO(session)
    user = await user_dao.get_by_email(body.email)
    if user is None:
        user = await user_dao.create_email_user(body.email)

    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/email/verify", response_model=TokenResponse)
async def email_verify_by_link(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    """Подтвердить email по ссылке из письма (?token=...)."""
    ev_dao = EmailVerificationDAO(session)
    ev = await ev_dao.get_active_by_token(token)
    if ev is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    await ev_dao.mark_used(ev)

    user_dao = UserDAO(session)
    user = await user_dao.get_by_email(ev.email)
    if user is None:
        user = await user_dao.create_email_user(ev.email)

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/email/resend", status_code=status.HTTP_202_ACCEPTED)
async def email_resend(
    body: EmailRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Повторно отправить код подтверждения."""
    ev_dao = EmailVerificationDAO(session)
    await ev_dao.invalidate_pending(body.email)
    ev = await ev_dao.create(body.email)
    await send_verification_email(body.email, ev.code, ev.token)
    return {"detail": "Verification code resent"}


# ---------------------------------------------------------------------------
# Telegram auth endpoints
# ---------------------------------------------------------------------------


@router.post("/telegram/widget", response_model=TokenResponse)
async def telegram_widget(
    body: TelegramWidgetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Авторизация через Telegram Login Widget."""
    if not _verify_telegram_widget(body):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram data",
        )

    user_dao = UserDAO(session)
    user = await user_dao.get_by_telegram_id(body.id)
    if user is None:
        # Создаём нового пользователя через Telegram
        from bot.models.user import User
        user = User(
            telegram_id=body.id,
            first_name=body.first_name,
            last_name=body.last_name,
            username=body.username,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/telegram/miniapp", response_model=TokenResponse)
async def telegram_miniapp(
    body: TelegramMiniAppRequest,
    session: AsyncSession = Depends(get_session),
):
    """Авторизация через Telegram Mini App (initData)."""
    parsed = _verify_telegram_miniapp(body.init_data)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Mini App data",
        )

    import json
    user_data = json.loads(parsed.get("user", "{}"))
    tg_id = user_data.get("id")
    if not tg_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user data in initData",
        )

    user_dao = UserDAO(session)
    user = await user_dao.get_by_telegram_id(tg_id)
    if user is None:
        from bot.models.user import User
        user = User(
            telegram_id=tg_id,
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            username=user_data.get("username"),
            language_code=user_data.get("language_code"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))
