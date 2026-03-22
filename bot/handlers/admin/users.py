import math

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
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
    AdminProxySelectCallback,
    AdminUserBanCallback,
    AdminUserDeleteCallback,
    AdminUserDeleteConfirmCallback,
    AdminUserListCallback,
    AdminUserViewCallback,
)
from bot.dao import ProxyDAO, UserDAO
from bot.filters import AdminFilter
from bot.models.user import User
from bot.services.admin_panel import admin_panel

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

PAGE_SIZE = 10


class AdminStates(StatesGroup):
    search_query = State()
    send_message_text = State()
    send_message_preview = State()


# ── Утилиты ───────────────────────────────────────────────────────────────────

def _user_label(user: User) -> str:
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    suffix = f"@{user.username}" if user.username else str(user.telegram_id)
    return f"{name} ({suffix})" if name else suffix


def _admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👥 Пользователи",
            callback_data=AdminUserListCallback(page=0).pack(),
        )],
        [InlineKeyboardButton(text="🖥 Дашборд", callback_data="admin:dashboard")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(
            text="⚙️ Настройки прокси",
            callback_data="admin:proxy_settings",
        )],
        [InlineKeyboardButton(text="❓ Настроить FAQ", callback_data="admin:faq")],
    ])


def _user_list_keyboard(
    users: list[User], page: int, total: int
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=_user_label(u),
            callback_data=AdminUserViewCallback(user_id=u.id).pack(),
        )]
        for u in users
    ]

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=AdminUserListCallback(page=page - 1).pack(),
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}", callback_data="noop"
    ))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=AdminUserListCallback(page=page + 1).pack(),
        ))
    buttons.append(nav)

    buttons.append([InlineKeyboardButton(
        text="🔍 Поиск",
        callback_data="admin:users:search",
    )])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _user_card_text(
    user: User,
    proxy_count: int,
    proxy_device_limits: list[tuple[str, int | None]] | None = None,
) -> str:
    """proxy_device_limits: список (node_name, max_devices) для каждого прокси."""
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    username = f"@{user.username}" if user.username else "—"
    status = "🚫 Заблокирован" if user.is_banned else "✅ Активен"
    lines = [
        "<b>Карточка пользователя</b>\n",
        f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>",
        f"👤 <b>Имя:</b> <code>{name or '—'}</code>",
        f"🔗 <b>Username:</b> <code>{username}</code>",
        f"📅 <b>Регистрация:</b> "
        f"<code>{user.created_at.strftime('%d.%m.%Y %H:%M')}</code>",
        f"🔌 <b>Кол-во прокси:</b> <code>{proxy_count}</code>",
        f"⚡ <b>Статус:</b> {status}",
    ]
    if proxy_device_limits:
        lines.append("\n📱 <b>Лимит устройств по нодам:</b>")
        for node_name, max_dev in proxy_device_limits:
            lim = str(max_dev) if max_dev is not None else "∞"
            lines.append(f"  • {node_name}: <code>{lim}</code>")
    return "\n".join(lines)


def _user_card_keyboard(
    user: User,
    back_page: int,
    back_query: str,
    proxies=None,
) -> InlineKeyboardMarkup:
    ban_text = "✅ Разблокировать" if user.is_banned else "🚫 Заблокировать"
    buttons = [
        [InlineKeyboardButton(
            text=ban_text,
            callback_data=AdminUserBanCallback(user_id=user.id).pack(),
        )],
        [InlineKeyboardButton(
            text="✉️ Написать сообщение",
            callback_data=f"admin:msg:{user.id}",
        )],
        [InlineKeyboardButton(
            text="👤 Открыть профиль",
            url=f"tg://user?id={user.telegram_id}",
        )],
    ]
    if proxies:
        buttons.append([InlineKeyboardButton(
            text="✏️ Редактировать ограничения прокси",
            callback_data=AdminProxySelectCallback(user_id=user.id).pack(),
        )])
    buttons.append([InlineKeyboardButton(
        text="🗑 Удалить пользователя",
        callback_data=AdminUserDeleteCallback(user_id=user.id).pack(),
    )])
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminUserListCallback(
            page=back_page, query=back_query
        ).pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _delete_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=AdminUserDeleteConfirmCallback(user_id=user_id).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=AdminUserViewCallback(user_id=user_id).pack(),
        ),
    ]])


# ── Хендлеры ──────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def handle_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "⚙️ Панель администратора", reply_markup=_admin_main_keyboard()
    )


@router.callback_query(F.data == "admin:main")
async def handle_admin_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "⚙️ Панель администратора", reply_markup=_admin_main_keyboard()
    )
    await call.answer()


@router.callback_query(F.data == "noop")
async def handle_noop(call: CallbackQuery) -> None:
    await call.answer()


# ── Список пользователей ──────────────────────────────────────────────────────

@router.callback_query(AdminUserListCallback.filter())
async def handle_user_list(
    call: CallbackQuery,
    callback_data: AdminUserListCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    page = callback_data.page

    await state.set_state(None)
    await state.update_data(user_list_page=page, user_list_query="")

    dao = UserDAO(session)
    users = await dao.get_all(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    total = await dao.count_all()
    header = f"👥 Пользователи: {total}"

    text = (
        f"{header}\n\nВыберите пользователя:"
        if users else f"{header}\n\nНичего не найдено."
    )
    await call.message.edit_text(
        text, reply_markup=_user_list_keyboard(users, page, total)
    )
    await call.answer()


# ── Поиск ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:users:search")
async def handle_search_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.search_query)
    await state.update_data(search_prompt_msg_id=call.message.message_id)
    await call.message.edit_text(
        "🔍 Введите username (с @ или без) или Telegram ID:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Отмена",
                callback_data=AdminUserListCallback(page=0).pack(),
            )]
        ]),
    )
    await call.answer()


@router.message(AdminStates.search_query)
async def handle_search_query(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    query = message.text.strip()[:20]
    fsm_data = await state.get_data()
    prompt_msg_id = fsm_data.get("search_prompt_msg_id")

    await state.set_state(None)

    dao = UserDAO(session)
    user = await dao.search(query)

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    async def _edit_or_answer(text: str, keyboard, parse_mode: str | None = None):
        if prompt_msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard,
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(text, parse_mode=parse_mode, reply_markup=keyboard)

    if user is None:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=AdminUserListCallback(page=0).pack(),
            )]
        ])
        await _edit_or_answer(
            "❌ Пользователь не найден, "
            "проверьте корректность ввода и попробуйте ещё раз",
            keyboard,
        )
        return

    await state.update_data(user_list_page=0, user_list_query="")
    proxies = await ProxyDAO(session).get_user_proxies(user.id)
    proxy_device_limits = await _fetch_proxy_device_limits(proxies)
    keyboard = _user_card_keyboard(user, 0, "", proxies)
    await _edit_or_answer(
        _user_card_text(user, len(proxies), proxy_device_limits),
        keyboard,
        parse_mode="HTML",
    )


# ── Карточка пользователя ─────────────────────────────────────────────────────

@router.callback_query(AdminUserViewCallback.filter())
async def handle_user_view(
    call: CallbackQuery,
    callback_data: AdminUserViewCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    user = await UserDAO(session).get_by_id(callback_data.user_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    await state.set_state(None)
    fsm_data = await state.get_data()
    back_page = fsm_data.get("user_list_page", 0)
    back_query = fsm_data.get("user_list_query", "")

    proxies = await ProxyDAO(session).get_user_proxies(user.id)
    proxy_device_limits = await _fetch_proxy_device_limits(proxies)

    await call.message.edit_text(
        _user_card_text(user, len(proxies), proxy_device_limits),
        parse_mode="HTML",
        reply_markup=_user_card_keyboard(user, back_page, back_query, proxies),
    )
    await call.answer()


async def _fetch_proxy_device_limits(proxies) -> list[tuple[str, int | None]]:
    """Получает лимит устройств для каждого прокси из /summary (кеш панели)."""
    result = []
    for proxy in proxies:
        max_devices: int | None = None
        try:
            summary = await admin_panel.get_node_summary(proxy.node.panel_id)
            users = summary.get("users") or []
            entry = next((u for u in users if u["name"] == proxy.mtg_username), None)
            if entry:
                max_devices = entry.get("max_devices")
        except Exception:
            pass
        result.append((proxy.node.name, max_devices))
    return result


# ── Бан / Разбан ──────────────────────────────────────────────────────────────

@router.callback_query(AdminUserBanCallback.filter())
async def handle_user_ban(
    call: CallbackQuery,
    callback_data: AdminUserBanCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    dao = UserDAO(session)
    user = await dao.get_by_id(callback_data.user_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    await dao.set_banned(user, not user.is_banned)
    action = "заблокирован" if user.is_banned else "разблокирован"

    await state.set_state(None)
    fsm_data = await state.get_data()
    back_page = fsm_data.get("user_list_page", 0)
    back_query = fsm_data.get("user_list_query", "")

    proxies = await ProxyDAO(session).get_user_proxies(user.id)
    proxy_device_limits = await _fetch_proxy_device_limits(proxies)

    await call.message.edit_text(
        _user_card_text(user, len(proxies), proxy_device_limits),
        parse_mode="HTML",
        reply_markup=_user_card_keyboard(user, back_page, back_query, proxies),
    )
    await call.answer(f"✅ Пользователь {action}.")


# ── Написать сообщение ────────────────────────────────────────────────────────

@router.callback_query(
    F.data.startswith("admin:msg:") & F.data.regexp(r"^admin:msg:\d+$")
)
async def handle_send_message_start(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    user_id = int(call.data.split(":")[2])
    user = await UserDAO(session).get_by_id(user_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    await state.set_state(AdminStates.send_message_text)
    await state.update_data(
        target_user_db_id=user_id,
        target_telegram_id=user.telegram_id,
        msg_prompt_msg_id=call.message.message_id,
    )
    await call.message.edit_text(
        f"✉️ Сообщение для {_user_label(user)}\n\nВведите текст (поддерживается HTML):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Отмена",
                callback_data=AdminUserViewCallback(user_id=user_id).pack(),
            )]
        ]),
    )
    await call.answer()


@router.message(AdminStates.send_message_text)
async def handle_send_message_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    text = message.text
    fsm_data = await state.get_data()
    target_user_db_id = fsm_data["target_user_db_id"]
    prompt_msg_id = fsm_data.get("msg_prompt_msg_id")

    user = await UserDAO(session).get_by_id(target_user_db_id)

    await state.set_state(AdminStates.send_message_preview)
    await state.update_data(pending_message_text=text)

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    preview_text = (
        f"📋 <b>Предпросмотр</b> — так увидит "
        f"{_user_label(user) if user else 'пользователь'}:\n"
        f"{'─' * 20}\n"
        f"{text}"
    )
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data="admin:msg:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:msg:cancel"),
    ]])

    if prompt_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=preview_text,
                parse_mode="HTML",
                reply_markup=confirm_keyboard,
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(preview_text, parse_mode="HTML", reply_markup=confirm_keyboard)


@router.callback_query(
    F.data == "admin:msg:confirm",
    StateFilter(AdminStates.send_message_preview),
)
async def handle_send_message_confirm(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    fsm_data = await state.get_data()
    text = fsm_data["pending_message_text"]
    target_telegram_id = fsm_data["target_telegram_id"]
    target_user_db_id = fsm_data["target_user_db_id"]
    await state.clear()

    try:
        await call.bot.send_message(
            chat_id=target_telegram_id,
            text=text,
            parse_mode="HTML",
        )
        result_text = "✅ Сообщение успешно отправлено."
    except Exception:
        result_text = "❌ Не удалось отправить сообщение."

    await call.message.edit_text(
        result_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ К пользователю",
                callback_data=AdminUserViewCallback(user_id=target_user_db_id).pack(),
            )]
        ]),
    )
    await call.answer()


@router.callback_query(
    F.data == "admin:msg:cancel",
    StateFilter(AdminStates.send_message_preview),
)
async def handle_send_message_cancel(
    call: CallbackQuery,
    state: FSMContext,
) -> None:
    fsm_data = await state.get_data()
    target_user_db_id = fsm_data["target_user_db_id"]
    await state.set_state(None)

    await call.message.edit_text(
        "❌ Отправка отменена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ К пользователю",
                callback_data=AdminUserViewCallback(user_id=target_user_db_id).pack(),
            )]
        ]),
    )
    await call.answer()


# ── Удаление пользователя ─────────────────────────────────────────────────────

@router.callback_query(AdminUserDeleteCallback.filter())
async def handle_user_delete(
    call: CallbackQuery,
    callback_data: AdminUserDeleteCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    user = await UserDAO(session).get_by_id(callback_data.user_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    await state.set_state(None)
    await call.message.edit_text(
        f"⚠️ Вы уверены, что хотите удалить {_user_label(user)}?"
        "\n\nЭто действие необратимо.",
        reply_markup=_delete_confirm_keyboard(user.id),
    )
    await call.answer()


@router.callback_query(AdminUserDeleteConfirmCallback.filter())
async def handle_user_delete_confirm(
    call: CallbackQuery,
    callback_data: AdminUserDeleteConfirmCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    dao = UserDAO(session)
    user = await dao.get_by_id(callback_data.user_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    label = _user_label(user)

    user_proxies = await ProxyDAO(session).get_user_proxies(user.id)
    for proxy in user_proxies:
        try:
            await admin_panel.delete_user(proxy.node.panel_id, proxy.mtg_username)
        except Exception:
            pass

    await dao.delete(user)

    await state.set_state(None)
    fsm_data = await state.get_data()
    back_page = fsm_data.get("user_list_page", 0)
    back_query = fsm_data.get("user_list_query", "")

    await call.message.edit_text(
        f"✅ Пользователь {label} удалён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ К списку",
                callback_data=AdminUserListCallback(
                    page=back_page, query=back_query
                ).pack(),
            )]
        ]),
    )
    await call.answer()
