from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import FAQViewCallback
from bot.dao import FAQItemDAO

router = Router()


def _faq_list_keyboard(items) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{item.question[:60]}",
            callback_data=FAQViewCallback(faq_id=item.id).pack(),
        )]
        for item in items
    ]
    buttons.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="faq:back_menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "faq:list")
async def handle_faq_list(call: CallbackQuery, session: AsyncSession) -> None:
    items = await FAQItemDAO(session).get_all()
    if not items:
        await call.answer("FAQ пока пуст.", show_alert=True)
        return

    await call.message.edit_text(
        "❓ <b>FAQ</b>\n\nВыберите вопрос:",
        parse_mode="HTML",
        reply_markup=_faq_list_keyboard(items),
    )
    await call.answer()


@router.callback_query(FAQViewCallback.filter())
async def handle_faq_view(
    call: CallbackQuery,
    callback_data: FAQViewCallback,
    session: AsyncSession,
) -> None:
    item = await FAQItemDAO(session).get_by_id(callback_data.faq_id)
    if not item:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    text = f"❓ <b>{item.question}</b>\n\n{item.answer}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к FAQ", callback_data="faq:list")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await call.answer()
