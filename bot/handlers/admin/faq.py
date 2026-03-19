from aiogram import F, Router
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

from bot.callbacks import (
    AdminFAQAddCallback,
    AdminFAQDeleteCallback,
    AdminFAQDeleteConfirmCallback,
    AdminFAQEditAnswerCallback,
    AdminFAQEditQuestionCallback,
    AdminFAQItemViewCallback,
    AdminFAQMoveCallback,
    AdminFAQToggleCallback,
)
from bot.dao import FAQItemDAO, ProxySettingsDAO
from bot.filters import AdminFilter

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


class AdminFAQStates(StatesGroup):
    waiting_question = State()
    waiting_answer = State()
    editing_question = State()
    editing_answer = State()


def _admin_faq_keyboard(items, faq_enabled: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"📝 {item.question[:60]}",
            callback_data=AdminFAQItemViewCallback(faq_id=item.id).pack(),
        )]
        for item in items
    ]
    toggle_text = "🔘 Выключить" if faq_enabled else "🔘 Включить"
    action_row = [
        InlineKeyboardButton(
            text="➕ Добавить вопрос",
            callback_data=AdminFAQAddCallback().pack(),
        ),
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=AdminFAQToggleCallback().pack(),
        ),
    ]
    buttons.append(action_row)
    if len(items) > 1:
        buttons.append([InlineKeyboardButton(
            text="🔀 Изменить порядок",
            callback_data="admin:faq:sort",
        )])
    buttons.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _sort_keyboard(items) -> InlineKeyboardMarkup:
    buttons = []
    for idx, item in enumerate(items):
        up_btn = InlineKeyboardButton(
            text="⬆️",
            callback_data=AdminFAQMoveCallback(
                faq_id=item.id, direction="up"
            ).pack(),
        ) if idx > 0 else InlineKeyboardButton(text=" ", callback_data="noop")
        down_btn = InlineKeyboardButton(
            text="⬇️",
            callback_data=AdminFAQMoveCallback(
                faq_id=item.id, direction="down"
            ).pack(),
        ) if idx < len(items) - 1 else InlineKeyboardButton(
            text=" ", callback_data="noop"
        )
        buttons.append([
            down_btn,
            InlineKeyboardButton(
                text=f"{idx + 1}. {item.question[:35]}",
                callback_data="noop",
            ),
            up_btn,
        ])
    buttons.append(
        [InlineKeyboardButton(text="✅ Готово", callback_data="admin:faq")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_faq_menu(
    target, session: AsyncSession, edit: bool = True
) -> None:
    settings = await ProxySettingsDAO(session).get()
    faq_enabled = settings.faq_enabled if settings else False
    items = await FAQItemDAO(session).get_all()

    status = "✅ Включён" if faq_enabled else "❌ Выключен"
    text = f"❓ <b>Настройка FAQ</b>\n\nСтатус: {status}"
    if items:
        text += f"\n\nВопросов: {len(items)}"

    keyboard = _admin_faq_keyboard(items, faq_enabled)

    if edit:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "admin:faq")
async def handle_admin_faq(call: CallbackQuery, session: AsyncSession) -> None:
    await _show_faq_menu(call, session)


@router.callback_query(AdminFAQToggleCallback.filter())
async def handle_faq_toggle(
    call: CallbackQuery, session: AsyncSession
) -> None:
    settings_dao = ProxySettingsDAO(session)
    settings = await settings_dao.get()
    current = settings.faq_enabled if settings else False
    await settings_dao.update(faq_enabled=not current)
    await _show_faq_menu(call, session)


@router.callback_query(AdminFAQAddCallback.filter())
async def handle_faq_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFAQStates.waiting_question)
    await state.update_data(faq_prompt_msg_id=call.message.message_id)
    await call.message.edit_text(
        "➕ <b>Новый вопрос</b>\n\nВведите текст вопроса:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin:faq")]
        ]),
    )
    await call.answer()


@router.message(AdminFAQStates.waiting_question)
async def handle_faq_question(message: Message, state: FSMContext) -> None:
    question = message.text.strip()
    await state.update_data(faq_question=question)
    await state.set_state(AdminFAQStates.waiting_answer)

    fsm_data = await state.get_data()
    prompt_msg_id = fsm_data.get("faq_prompt_msg_id")

    try:
        await message.delete()
    except Exception:
        pass

    text = f"➕ <b>Новый вопрос</b>\n\n❓ {question}\n\nТеперь введите ответ:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin:faq")]
    ])

    if prompt_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(AdminFAQStates.waiting_answer)
async def handle_faq_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    answer = message.text.strip()
    fsm_data = await state.get_data()
    question = fsm_data["faq_question"]
    prompt_msg_id = fsm_data.get("faq_prompt_msg_id")
    await state.clear()

    await FAQItemDAO(session).create(question=question, answer=answer)

    try:
        await message.delete()
    except Exception:
        pass

    settings = await ProxySettingsDAO(session).get()
    faq_enabled = settings.faq_enabled if settings else False
    items = await FAQItemDAO(session).get_all()

    status = "✅ Включён" if faq_enabled else "❌ Выключен"
    text = f"❓ <b>Настройка FAQ</b>\n\nСтатус: {status}\n\nВопросов: {len(items)}"
    keyboard = _admin_faq_keyboard(items, faq_enabled)

    if prompt_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(AdminFAQItemViewCallback.filter())
async def handle_faq_item_view(
    call: CallbackQuery,
    callback_data: AdminFAQItemViewCallback,
    session: AsyncSession,
) -> None:
    item = await FAQItemDAO(session).get_by_id(callback_data.faq_id)
    if not item:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    text = f"❓ <b>{item.question}</b>\n\n{item.answer}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Изменить вопрос",
                callback_data=AdminFAQEditQuestionCallback(faq_id=item.id).pack(),
            ),
            InlineKeyboardButton(
                text="✏️ Изменить ответ",
                callback_data=AdminFAQEditAnswerCallback(faq_id=item.id).pack(),
            ),
        ],
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=AdminFAQDeleteCallback(faq_id=item.id).pack(),
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:faq")],
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await call.answer()


@router.callback_query(AdminFAQDeleteCallback.filter())
async def handle_faq_delete(
    call: CallbackQuery,
    callback_data: AdminFAQDeleteCallback,
    session: AsyncSession,
) -> None:
    item = await FAQItemDAO(session).get_by_id(callback_data.faq_id)
    if not item:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=AdminFAQDeleteConfirmCallback(faq_id=item.id).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=AdminFAQItemViewCallback(faq_id=item.id).pack(),
        ),
    ]])
    await call.message.edit_text(
        f"⚠️ Удалить вопрос?\n\n❓ {item.question}",
        reply_markup=keyboard,
    )
    await call.answer()


@router.callback_query(AdminFAQDeleteConfirmCallback.filter())
async def handle_faq_delete_confirm(
    call: CallbackQuery,
    callback_data: AdminFAQDeleteConfirmCallback,
    session: AsyncSession,
) -> None:
    dao = FAQItemDAO(session)
    item = await dao.get_by_id(callback_data.faq_id)
    if not item:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    await dao.delete(item)
    await _show_faq_menu(call, session)


@router.callback_query(AdminFAQEditQuestionCallback.filter())
async def handle_faq_edit_question(
    call: CallbackQuery,
    callback_data: AdminFAQEditQuestionCallback,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    item = await FAQItemDAO(session).get_by_id(callback_data.faq_id)
    if not item:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    await state.set_state(AdminFAQStates.editing_question)
    await state.update_data(
        faq_edit_id=item.id,
        faq_prompt_msg_id=call.message.message_id,
    )
    await call.message.edit_text(
        f"✏️ <b>Редактирование вопроса</b>\n\n"
        f"<b>Текущий вопрос:</b> {item.question}\n\n"
        f"Введите новый текст вопроса:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Отмена",
                callback_data=AdminFAQItemViewCallback(faq_id=item.id).pack(),
            )]
        ]),
    )
    await call.answer()


@router.callback_query(AdminFAQEditAnswerCallback.filter())
async def handle_faq_edit_answer(
    call: CallbackQuery,
    callback_data: AdminFAQEditAnswerCallback,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    item = await FAQItemDAO(session).get_by_id(callback_data.faq_id)
    if not item:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    await state.set_state(AdminFAQStates.editing_answer)
    await state.update_data(
        faq_edit_id=item.id,
        faq_prompt_msg_id=call.message.message_id,
    )
    await call.message.edit_text(
        f"✏️ <b>Редактирование ответа</b>\n\n"
        f"<b>Вопрос:</b> {item.question}\n\n"
        f"<b>Текущий ответ:</b>\n{item.answer}\n\n"
        f"Введите новый текст ответа:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Отмена",
                callback_data=AdminFAQItemViewCallback(faq_id=item.id).pack(),
            )]
        ]),
    )
    await call.answer()


@router.message(AdminFAQStates.editing_question)
async def handle_faq_new_question(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    new_question = message.text.strip()
    fsm_data = await state.get_data()
    faq_id = fsm_data["faq_edit_id"]
    prompt_msg_id = fsm_data.get("faq_prompt_msg_id")
    await state.clear()

    item = await FAQItemDAO(session).get_by_id(faq_id)
    if item:
        await FAQItemDAO(session).update(item, question=new_question)

    try:
        await message.delete()
    except Exception:
        pass

    if item and prompt_msg_id:
        text = f"❓ <b>{item.question}</b>\n\n{item.answer}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить вопрос",
                    callback_data=AdminFAQEditQuestionCallback(
                        faq_id=item.id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="✏️ Изменить ответ",
                    callback_data=AdminFAQEditAnswerCallback(
                        faq_id=item.id
                    ).pack(),
                ),
            ],
            [InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=AdminFAQDeleteCallback(faq_id=item.id).pack(),
            )],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:faq")],
        ])
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    await message.answer("✅ Вопрос обновлён.")


@router.message(AdminFAQStates.editing_answer)
async def handle_faq_new_answer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    new_answer = message.text.strip()
    fsm_data = await state.get_data()
    faq_id = fsm_data["faq_edit_id"]
    prompt_msg_id = fsm_data.get("faq_prompt_msg_id")
    await state.clear()

    item = await FAQItemDAO(session).get_by_id(faq_id)
    if item:
        await FAQItemDAO(session).update(item, answer=new_answer)

    try:
        await message.delete()
    except Exception:
        pass

    if item and prompt_msg_id:
        text = f"❓ <b>{item.question}</b>\n\n{item.answer}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить вопрос",
                    callback_data=AdminFAQEditQuestionCallback(
                        faq_id=item.id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="✏️ Изменить ответ",
                    callback_data=AdminFAQEditAnswerCallback(
                        faq_id=item.id
                    ).pack(),
                ),
            ],
            [InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=AdminFAQDeleteCallback(faq_id=item.id).pack(),
            )],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:faq")],
        ])
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    await message.answer("✅ Ответ обновлён.")


@router.callback_query(F.data == "admin:faq:sort")
async def handle_faq_sort(call: CallbackQuery, session: AsyncSession) -> None:
    items = await FAQItemDAO(session).get_all()
    if len(items) < 2:
        await call.answer("Нечего сортировать.", show_alert=True)
        return
    await call.message.edit_text(
        "🔀 <b>Изменить порядок</b>\n\nНажмите ⬆️/⬇️ для перемещения:",
        parse_mode="HTML",
        reply_markup=_sort_keyboard(items),
    )
    await call.answer()


@router.callback_query(AdminFAQMoveCallback.filter())
async def handle_faq_move(
    call: CallbackQuery,
    callback_data: AdminFAQMoveCallback,
    session: AsyncSession,
) -> None:
    items = await FAQItemDAO(session).get_all()
    idx = next((i for i, it in enumerate(items) if it.id == callback_data.faq_id), None)
    if idx is None:
        await call.answer("Вопрос не найден.", show_alert=True)
        return

    if callback_data.direction == "up" and idx > 0:
        await FAQItemDAO(session).swap_positions(items[idx], items[idx - 1])
    elif callback_data.direction == "down" and idx < len(items) - 1:
        await FAQItemDAO(session).swap_positions(items[idx], items[idx + 1])
    else:
        await call.answer()
        return

    items = await FAQItemDAO(session).get_all()
    await call.message.edit_text(
        "🔀 <b>Изменить порядок</b>\n\nНажмите ⬇️/⬆️ для перемещения:",
        parse_mode="HTML",
        reply_markup=_sort_keyboard(items),
    )
    await call.answer()


@router.callback_query(
    F.data == "admin:faq",
    StateFilter(
        AdminFAQStates.waiting_question,
        AdminFAQStates.waiting_answer,
        AdminFAQStates.editing_question,
        AdminFAQStates.editing_answer,
    ),
)
async def handle_faq_cancel_fsm(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await _show_faq_menu(call, session)
