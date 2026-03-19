from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.config import settings
from bot.database import dispose_engine


async def _on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    await dispose_engine()
    from bot.services.admin_panel import admin_panel
    await admin_panel.close()
    await bot.session.close()


def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    async def _on_startup(bot: Bot) -> None:
        bot_info = await bot.get_me()
        dp.workflow_data["bot_username"] = bot_info.username
        await bot.set_webhook(
            f"{settings.WEBHOOK_BASE_URL}{settings.WEBHOOK_PATH}",
            secret_token=settings.WEBHOOK_SECRET,
            drop_pending_updates=True,
        )

    dp.startup.register(_on_startup)
    dp.shutdown.register(_on_shutdown)

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.WEBHOOK_SECRET,
    ).register(app, path=settings.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=settings.WEB_SERVER_HOST, port=settings.WEB_SERVER_PORT)
