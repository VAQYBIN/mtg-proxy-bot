from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.config import settings


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, cooldown: float = 0.5) -> None:
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._cooldown_ms = int(cooldown * 1000)

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

        key = f"throttle:{from_user.id}"
        allowed = await self._redis.set(key, 1, px=self._cooldown_ms, nx=True)

        if allowed is None:
            update: Update = event
            if update.message:
                await update.message.answer(
                    "⏳ Слишком много запросов. Подождите немного."
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "⏳ Слишком много запросов.",
                    show_alert=False,
                )
            return

        return await handler(event, data)
