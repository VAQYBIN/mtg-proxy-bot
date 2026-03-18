from aiogram import Router

from bot.handlers.admin.broadcast import router as broadcast_router
from bot.handlers.admin.dashboard import router as dashboard_router
from bot.handlers.admin.users import router as users_router

router = Router()
router.include_router(users_router)
router.include_router(dashboard_router)
router.include_router(broadcast_router)

__all__ = ["router"]
