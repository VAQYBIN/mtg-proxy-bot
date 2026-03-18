from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.config import settings
from bot.dao import UserDAO


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = data.get("event_from_user")
        if not from_user:
            return await handler(event, data)

        # Пропускаем админов
        if from_user.id in settings.ADMIN_IDS:
            return await handler(event, data)

        session = data["session"]
        user = await UserDAO(session).get_by_telegram_id(from_user.id)

        if user and user.is_banned:
            update: Update = event
            if update.message:
                await update.message.answer(
                    "⚠️ Доступ к боту заблокирован.\n\n"
                    "Обратитесь к администратору для уточнения причины."
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "⚠️ Доступ к боту заблокирован.\n\n"
                    "Обратитесь к администратору для уточнения причины.",
                    show_alert=True
                )
            return

        return await handler(event, data)
