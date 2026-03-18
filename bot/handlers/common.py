from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.dao import UserDAO

router = Router()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Получить прокси", callback_data="proxy:get")],
        [InlineKeyboardButton(text="📋 Мои прокси", callback_data="proxy:list")],
    ])


@router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    dao = UserDAO(session)
    user, is_new = await dao.get_or_create(message.from_user)

    if is_new:
        text = f"Добро пожаловать, {user.first_name}!\n\nЯ помогу тебе настроить MTProto прокси."
    else:
        text = f"С возвращением, {user.first_name}!"

    await message.answer(text, reply_markup=main_menu_keyboard())
