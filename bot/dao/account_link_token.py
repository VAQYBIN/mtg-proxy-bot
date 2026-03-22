import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.account_link_token import AccountLinkToken

TOKEN_TTL_MINUTES = 15


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class AccountLinkTokenDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: int) -> AccountLinkToken:
        token = AccountLinkToken(
            user_id=user_id,
            code=_generate_code(),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=TOKEN_TTL_MINUTES),
        )
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def get_active_by_code(self, code: str) -> AccountLinkToken | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(AccountLinkToken).where(
                AccountLinkToken.code == code.upper(),
                AccountLinkToken.used_at.is_(None),
                AccountLinkToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: AccountLinkToken) -> None:
        token.used_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def invalidate_pending(self, user_id: int) -> None:
        """Аннулировать все активные токены пользователя."""
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(AccountLinkToken)
            .where(
                AccountLinkToken.user_id == user_id,
                AccountLinkToken.used_at.is_(None),
                AccountLinkToken.expires_at > now,
            )
            .values(used_at=now)
        )
        await self.session.commit()
