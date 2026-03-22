from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User


class UserDAO:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, tg_user: TelegramUser) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(tg_user.id)
        if user:
            return user, False

        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, True

    async def create_email_user(
        self, email: str, display_name: str | None = None
    ) -> User:
        user = User(email=email, email_verified=True, display_name=display_name)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def link_telegram(self, user: User, tg_user: TelegramUser) -> User:
        """Привязать Telegram-аккаунт к существующему пользователю."""
        user.telegram_id = tg_user.id
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def link_email(self, user: User, email: str) -> User:
        """Привязать email к существующему Telegram-пользователю."""
        user.email = email
        user.email_verified = True
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def merge_into(self, source: User, target: User) -> User:
        """Перенести прокси и рефералов из source в target, затем удалить source.

        Используется когда у обоих аккаунтов есть данные.
        target — более старый аккаунт (остаётся основным).
        """
        from bot.models.proxy import Proxy
        from sqlalchemy import update

        await self.session.execute(
            update(Proxy).where(Proxy.user_id == source.id).values(user_id=target.id)
        )
        await self.session.execute(
            update(User)
            .where(User.referred_by_id == source.id)
            .values(referred_by_id=target.id)
        )
        await self.session.delete(source)
        await self.session.commit()
        await self.session.refresh(target)
        return target

    async def get_all(self, offset: int = 0, limit: int = 10) -> list[User]:
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def search(self, query: str) -> User | None:
        tg_id: int | None = None
        try:
            tg_id = int(query)
        except ValueError:
            pass

        if tg_id is not None:
            condition = User.telegram_id == tg_id
        else:
            condition = func.lower(User.username) == query.lstrip('@').lower()

        result = await self.session.execute(select(User).where(condition))
        return result.scalar_one_or_none()

    async def get_all_ids(self) -> list[int]:
        """Вернуть telegram_id незабаненных пользователей с привязанным Telegram."""
        result = await self.session.execute(
            select(User.telegram_id).where(
                User.is_banned.is_(False),
                User.telegram_id.is_not(None),
            )
        )
        return list(result.scalars().all())

    async def set_banned(self, user: User, banned: bool) -> None:
        user.is_banned = banned
        await self.session.commit()

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()
