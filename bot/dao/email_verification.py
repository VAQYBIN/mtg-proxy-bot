import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.email_verification import EmailVerification

CODE_TTL_MINUTES = 15


def _generate_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class EmailVerificationDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, email: str, user_id: int | None = None
    ) -> EmailVerification:
        ev = EmailVerification(
            email=email.lower(),
            code=_generate_code(),
            token=_generate_token(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
            user_id=user_id,
        )
        self.session.add(ev)
        await self.session.commit()
        await self.session.refresh(ev)
        return ev

    async def get_active_by_code(
        self, email: str, code: str
    ) -> EmailVerification | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(EmailVerification).where(
                EmailVerification.email == email.lower(),
                EmailVerification.code == code,
                EmailVerification.used_at.is_(None),
                EmailVerification.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_token(self, token: str) -> EmailVerification | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(EmailVerification).where(
                EmailVerification.token == token,
                EmailVerification.used_at.is_(None),
                EmailVerification.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, ev: EmailVerification) -> None:
        ev.used_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def invalidate_pending(self, email: str) -> None:
        """Аннулировать все неиспользованные коды для данного email (перед resend)."""
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(EmailVerification)
            .where(
                EmailVerification.email == email.lower(),
                EmailVerification.used_at.is_(None),
                EmailVerification.expires_at > now,
            )
            .values(used_at=now)
        )
        await self.session.commit()
