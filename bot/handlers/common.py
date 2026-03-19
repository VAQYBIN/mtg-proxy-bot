from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.dao import ProxySettingsDAO, UserDAO

router = Router()


def main_menu_keyboard(faq_enabled: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🌐 Получить прокси", callback_data="proxy:get")],
        [InlineKeyboardButton(text="📋 Мои прокси", callback_data="proxy:list")],
    ]
    if faq_enabled:
        buttons.append(
            [InlineKeyboardButton(text="❓ FAQ", callback_data="faq:list")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    dao = UserDAO(session)
    user, is_new = await dao.get_or_create(message.from_user)

    settings = await ProxySettingsDAO(session).get()
    faq_enabled = settings.faq_enabled if settings else False

    if is_new:
        text = (
            f"Добро пожаловать, {user.first_name}!\n\n"
            "Я помогу тебе настроить MTProto прокси."
        )
    else:
        text = f"С возвращением, {user.first_name}!"

    await message.answer(text, reply_markup=main_menu_keyboard(faq_enabled))


@router.callback_query(F.data == "faq:back_menu")
async def handle_faq_back_menu(call: CallbackQuery, session: AsyncSession) -> None:
    settings = await ProxySettingsDAO(session).get()
    faq_enabled = settings.faq_enabled if settings else False
    await call.message.edit_text(
        "Главное меню", reply_markup=main_menu_keyboard(faq_enabled)
    )
    await call.answer()
