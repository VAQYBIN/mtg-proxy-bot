from aiogram.types import User as TelegramUser
from sqlalchemy import func, or_, select
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

    async def get_all(self, offset: int = 0, limit: int = 10) -> list[User]:
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def search(self, query: str, offset: int = 0, limit: int = 10) -> list[User]:
        tg_id: int | None = None
        try:
            tg_id = int(query)
        except ValueError:
            pass

        if tg_id is not None:
            condition = User.telegram_id == tg_id
        else:
            like = f"%{query.lstrip('@').lower()}%"
            condition = func.lower(User.username).like(like)

        result = await self.session.execute(
            select(User).where(condition).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_search(self, query: str) -> int:
        tg_id: int | None = None
        try:
            tg_id = int(query)
        except ValueError:
            pass

        if tg_id is not None:
            condition = User.telegram_id == tg_id
        else:
            like = f"%{query.lstrip('@').lower()}%"
            condition = func.lower(User.username).like(like)

        result = await self.session.execute(
            select(func.count()).select_from(User).where(condition)
        )
        return result.scalar_one()

    async def get_all_ids(self) -> list[int]:
        result = await self.session.execute(
            select(User.telegram_id).where(User.is_banned == False)
        )
        return list(result.scalars().all())

    async def set_banned(self, user: User, banned: bool) -> None:
        user.is_banned = banned
        await self.session.commit()

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()
