import logging

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


async def send_verification_email(
    email: str, code: str, token: str
) -> None:
    """Отправить письмо с кодом подтверждения.

    Если RESEND_API_KEY не задан — выводит код в лог (режим разработки).
    """
    verify_link = f"{settings.SITE_URL}/verify?token={token}"

    if not settings.RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set. Verification code for %s: %s (link: %s)",
            email, code, verify_link,
        )
        return

    html = (
        f"<p>Ваш код подтверждения: <strong>{code}</strong></p>"
        f"<p>Или перейдите по ссылке: "
        f'<a href="{verify_link}">Подтвердить email</a></p>'
        f"<p>Код действителен 15 минут.</p>"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.EMAIL_FROM,
                "to": [email],
                "subject": "Код подтверждения",
                "html": html,
            },
            timeout=10,
        )
        response.raise_for_status()
