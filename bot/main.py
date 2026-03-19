import logging

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.handlers import router
from bot.middleware import BanMiddleware, DbSessionMiddleware, ThrottlingMiddleware
from bot.web_server import run_webhook


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(BanMiddleware())
    dp.update.middleware(ThrottlingMiddleware())
    dp.include_router(router)

    run_webhook(bot, dp)


if __name__ == "__main__":
    main()
