import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import AdminBroadcastCancelCallback, AdminBroadcastConfirmCallback
from bot.dao import UserDAO
from bot.filters import AdminFilter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

PROGRESS_UPDATE_EVERY = 10


class BroadcastStates(StatesGroup):
    waiting_text = State()
    waiting_confirm = State()


# ── Фоновая задача рассылки ────────────────────────────────────────────────────

async def _do_broadcast(
    bot: Bot,
    admin_chat_id: int,
    progress_msg_id: int,
    text: str,
    user_ids: list[int],
) -> None:
    total = len(user_ids)
    sent = 0
    failed = 0

    def _progress_text(done: bool = False) -> str:
        if done:
            return (
                f"📢 <b>Рассылка завершена!</b>\n\n"
                f"✅ <b>Отправлено:</b> {sent}\n"
                f"❌ <b>Ошибок:</b> {failed}\n"
                f"👥 <b>Всего:</b> {total}"
            )
        return (
            f"📢 <b>Рассылка в процессе...</b>\n\n"
            f"✅ <b>Отправлено:</b> {sent}\n"
            f"❌ <b>Ошибок:</b> {failed}\n"
            f"⏳ <b>Осталось:</b> {total - sent - failed}"
        )

    for i, tg_id in enumerate(user_ids):
        try:
            await bot.send_message(chat_id=tg_id, text=text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        if (i + 1) % PROGRESS_UPDATE_EVERY == 0:
            try:
                await bot.edit_message_text(
                    chat_id=admin_chat_id,
                    message_id=progress_msg_id,
                    text=_progress_text(),
                    parse_mode="HTML",
                )
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.05)

    try:
        await bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=progress_msg_id,
            text=_progress_text(done=True),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:main")],
            ]),
        )
    except TelegramBadRequest:
        logger.exception("Не удалось обновить финальный прогресс рассылки")


# ── Хендлеры ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def handle_broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_text)
    await state.update_data(broadcast_prompt_msg_id=call.message.message_id)
    await call.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВведите текст сообщения (поддерживается HTML):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin:main")],
        ]),
    )
    await call.answer()


@router.message(BroadcastStates.waiting_text)
async def handle_broadcast_text(message: Message, state: FSMContext) -> None:
    text = message.text
    fsm_data = await state.get_data()
    prompt_msg_id = fsm_data.get("broadcast_prompt_msg_id")

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    preview_text = (
        f"📋 <b>Предпросмотр рассылки:</b>\n"
        f"{'─' * 20}\n"
        f"{text}"
    )
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Отправить всем",
            callback_data=AdminBroadcastConfirmCallback().pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=AdminBroadcastCancelCallback().pack(),
        ),
    ]])

    async def _send_preview(txt: str, kb: InlineKeyboardMarkup) -> None:
        if prompt_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=txt,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.answer(txt, parse_mode="HTML", reply_markup=kb)

    try:
        await _send_preview(preview_text, confirm_keyboard)
    except TelegramBadRequest as e:
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin:main")],
        ])
        await _send_preview(
            f"❌ <b>Ошибка HTML-разметки:</b>\n<code>{e.message}</code>\n\nИсправьте текст и отправьте снова:",
            error_keyboard,
        )
        return

    await state.set_state(BroadcastStates.waiting_confirm)
    await state.update_data(broadcast_text=text)


@router.callback_query(
    AdminBroadcastConfirmCallback.filter(),
    StateFilter(BroadcastStates.waiting_confirm),
)
async def handle_broadcast_confirm(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    fsm_data = await state.get_data()
    text = fsm_data["broadcast_text"]
    await state.clear()

    user_ids = await UserDAO(session).get_all_ids()
    total = len(user_ids)

    await call.message.edit_text(
        f"📢 <b>Рассылка в процессе...</b>\n\n"
        f"✅ <b>Отправлено:</b> 0\n"
        f"❌ <b>Ошибок:</b> 0\n"
        f"⏳ <b>Осталось:</b> {total}",
        parse_mode="HTML",
    )
    await call.answer()

    asyncio.create_task(_do_broadcast(
        bot=call.bot,
        admin_chat_id=call.message.chat.id,
        progress_msg_id=call.message.message_id,
        text=text,
        user_ids=user_ids,
    ))


@router.callback_query(
    AdminBroadcastCancelCallback.filter(),
    StateFilter(BroadcastStates.waiting_confirm),
)
async def handle_broadcast_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "❌ Рассылка отменена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="admin:main")],
        ]),
    )
    await call.answer()
