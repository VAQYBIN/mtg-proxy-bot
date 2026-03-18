import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.database import dispose_engine
from bot.handlers import router
from bot.middleware import BanMiddleware, DbSessionMiddleware, ThrottlingMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.BOT_TOKEN)
    bot_info = await bot.get_me()

    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(BanMiddleware())
    dp.update.middleware(ThrottlingMiddleware())
    dp.include_router(router)

    try:
        await dp.start_polling(bot, bot_username=bot_info.username)
    finally:
        await dispose_engine()
        await bot.session.close()
        from bot.services.admin_panel import admin_panel
        await admin_panel.close()


if __name__ == "__main__":
    asyncio.run(main())
