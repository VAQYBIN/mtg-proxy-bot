from aiogram import Router

from bot.handlers.common import router as common_router
from bot.handlers.proxy import router as proxy_router

router = Router()
router.include_router(common_router)
router.include_router(proxy_router)

__all__ = ["router"]
