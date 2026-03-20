import base64

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
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
async def handle_start(
    message: Message, session: AsyncSession, command: CommandObject
) -> None:
    dao = UserDAO(session)
    user, is_new = await dao.get_or_create(message.from_user)

    if is_new and command.args and command.args.startswith("r"):
        try:
            payload = command.args[1:]
            padded = payload + "=" * (-len(payload) % 4)
            referrer_tg_id = int(base64.urlsafe_b64decode(padded).decode())
            if referrer_tg_id != message.from_user.id:
                referrer = await dao.get_by_telegram_id(referrer_tg_id)
                if referrer:
                    user.referred_by_id = referrer.id
                    await session.commit()
        except (ValueError, Exception):
            pass

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
