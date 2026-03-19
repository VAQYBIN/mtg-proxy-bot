from datetime import datetime, timedelta, timezone

from aiogram import Router
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

from bot.callbacks import (
    AdminProxyEditCallback,
    AdminProxyEditFieldCallback,
    AdminProxyResetTrafficCallback,
    AdminProxyResetTrafficConfirmCallback,
    AdminProxySelectCallback,
    AdminUserViewCallback,
)
from bot.dao import ProxyDAO
from bot.filters import AdminFilter
from bot.models.proxy import Proxy
from bot.services.admin_panel import admin_panel

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

_FIELD_LABELS = {
    "max_devices": "Устройства",
    "traffic_limit_gb": "Трафик (ГБ)",
    "expires_at": "Срок действия",
    "traffic_reset_interval": "Сброс трафика",
}

_RESET_INTERVAL_LABELS = {
    "daily": "ежедневно",
    "monthly": "ежемесячно",
    "yearly": "ежегодно",
}

_FIELD_PROMPTS = {
    "max_devices": (
        "Введите максимальное число устройств (целое ≥ 1).\n"
        "Отправьте <b>0</b> или <b>-</b> для снятия ограничения."
    ),
    "traffic_limit_gb": (
        "Введите лимит трафика в ГБ (число > 0, например <b>100</b> или <b>50.5</b>).\n"
        "Отправьте <b>0</b> или <b>-</b> для снятия ограничения."
    ),
    "expires_at": (
        "Введите дату истечения в формате <b>DD.MM.YYYY</b>\n"
        "или <b>+N</b> для продления на N дней от сегодня.\n\n"
        "Отправьте <b>0</b> или <b>-</b> для снятия ограничения."
    ),
    "traffic_reset_interval": (
        "Введите интервал сброса трафика:\n"
        "<b>daily</b> — ежедневно\n"
        "<b>monthly</b> — ежемесячно\n"
        "<b>yearly</b> — ежегодно\n\n"
        "Отправьте <b>0</b> или <b>-</b> для отключения сброса."
    ),
}


class ProxyEditStates(StatesGroup):
    editing_field = State()


async def _proxy_edit_text(proxy: Proxy) -> str:
    max_devices_live: int | None = None
    traffic_used: str | None = None
    try:
        summary = await admin_panel.get_node_summary(proxy.node.panel_id)
        users = summary.get("users") or []
        entry = next((u for u in users if u["name"] == proxy.mtg_username), None)
        if entry:
            max_devices_live = entry.get("max_devices")
            traffic_info = summary.get("traffic", {}).get(proxy.mtg_username)
            if traffic_info:
                rx = traffic_info.get("rx", "?")
                tx = traffic_info.get("tx", "?")
                traffic_used = f"↓{rx} ↑{tx}"
    except Exception:
        pass

    max_dev_str = str(max_devices_live) if max_devices_live is not None else "?"
    limit_str = (
        f"{proxy.traffic_limit_gb} ГБ" if proxy.traffic_limit_gb is not None else "∞"
    )
    expires_str = (
        proxy.expires_at.strftime("%d.%m.%Y") if proxy.expires_at else "∞"
    )
    node_name = proxy.node.name
    return (
        f"📡 <b>Прокси:</b> <code>{proxy.mtg_username}</code> на ноде {node_name}\n\n"
        f"📱 <b>Макс. устройств:</b> {max_dev_str}\n"
        f"📊 <b>Трафик:</b> {traffic_used or '?'} / {limit_str}\n"
        f"📅 <b>Истекает:</b> {expires_str}\n"
    )


def _proxy_edit_keyboard(proxy_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Устройства",
                callback_data=AdminProxyEditFieldCallback(
                    proxy_id=proxy_id, field="max_devices"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="✏️ Трафик",
                callback_data=AdminProxyEditFieldCallback(
                    proxy_id=proxy_id, field="traffic_limit_gb"
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="✏️ Срок",
                callback_data=AdminProxyEditFieldCallback(
                    proxy_id=proxy_id, field="expires_at"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="✏️ Сброс",
                callback_data=AdminProxyEditFieldCallback(
                    proxy_id=proxy_id, field="traffic_reset_interval"
                ).pack(),
            ),
        ],
        [InlineKeyboardButton(
            text="🔄 Сбросить трафик",
            callback_data=AdminProxyResetTrafficCallback(proxy_id=proxy_id).pack(),
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к пользователю",
            callback_data=AdminUserViewCallback(user_id=user_id).pack(),
        )],
    ])


def _cancel_keyboard(proxy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=AdminProxyEditCallback(proxy_id=proxy_id).pack(),
        )]
    ])


@router.callback_query(AdminProxySelectCallback.filter())
async def handle_proxy_select(
    call: CallbackQuery,
    callback_data: AdminProxySelectCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    proxies = await ProxyDAO(session).get_user_proxies(callback_data.user_id)
    if not proxies:
        await call.answer("У пользователя нет активных прокси.", show_alert=True)
        return

    if len(proxies) == 1:
        # Сразу переходим к редактированию единственного прокси
        proxy = proxies[0]
        text = await _proxy_edit_text(proxy)
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_proxy_edit_keyboard(proxy.id, proxy.user_id),
        )
        await call.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"📡 {p.node.name}",
            callback_data=AdminProxyEditCallback(proxy_id=p.id).pack(),
        )]
        for p in proxies
    ]
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к пользователю",
        callback_data=AdminUserViewCallback(user_id=callback_data.user_id).pack(),
    )])
    await call.message.edit_text(
        "Выберите прокси для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await call.answer()


@router.callback_query(AdminProxyEditCallback.filter())
async def handle_proxy_edit(
    call: CallbackQuery,
    callback_data: AdminProxyEditCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    proxy = await ProxyDAO(session).get_by_id(callback_data.proxy_id)
    if not proxy:
        await call.answer("Прокси не найден.", show_alert=True)
        return

    text = await _proxy_edit_text(proxy)
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_proxy_edit_keyboard(proxy.id, proxy.user_id),
    )
    await call.answer()


@router.callback_query(AdminProxyEditFieldCallback.filter())
async def handle_proxy_edit_field_start(
    call: CallbackQuery,
    callback_data: AdminProxyEditFieldCallback,
    state: FSMContext,
) -> None:
    field = callback_data.field
    prompt = _FIELD_PROMPTS.get(field, "Введите значение:")
    await state.set_state(ProxyEditStates.editing_field)
    await state.update_data(
        proxy_id=callback_data.proxy_id,
        editing_field=field,
        edit_msg_id=call.message.message_id,
    )
    await call.message.edit_text(
        f"✏️ <b>{_FIELD_LABELS[field]}</b>\n\n{prompt}",
        parse_mode="HTML",
        reply_markup=_cancel_keyboard(callback_data.proxy_id),
    )
    await call.answer()


@router.message(StateFilter(ProxyEditStates.editing_field))
async def handle_proxy_edit_field_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    fsm_data = await state.get_data()
    proxy_id = fsm_data["proxy_id"]
    field = fsm_data["editing_field"]
    msg_id = fsm_data.get("edit_msg_id")
    text = message.text.strip() if message.text else ""

    value, error = _parse_field(field, text)
    if error:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        err_text = (
            f"✏️ <b>{_FIELD_LABELS[field]}</b>\n\n"
            f"❌ {error}\n\n{_FIELD_PROMPTS[field]}"
        )
        if msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=msg_id,
                    text=err_text,
                    parse_mode="HTML",
                    reply_markup=_cancel_keyboard(proxy_id),
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(
            err_text, parse_mode="HTML", reply_markup=_cancel_keyboard(proxy_id)
        )
        return

    proxy = await ProxyDAO(session).get_by_id(proxy_id)
    if not proxy:
        await state.clear()
        await message.answer("Прокси не найден.")
        return

    # Применяем на панель
    panel_field = field
    panel_value = value
    if field == "expires_at":
        panel_value = value.isoformat() if value is not None else None
    try:
        await admin_panel.update_user(
            proxy.node.panel_id, proxy.mtg_username, **{panel_field: panel_value}
        )
    except Exception as e:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        err_text = f"❌ Ошибка панели: {e}"
        if msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=msg_id,
                    text=err_text,
                    reply_markup=_cancel_keyboard(proxy_id),
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(err_text, reply_markup=_cancel_keyboard(proxy_id))
        return

    # Обновляем локальные поля, которые хранятся в БД
    db_update = {}
    if field == "expires_at":
        db_update["expires_at"] = value
    elif field == "traffic_limit_gb":
        db_update["traffic_limit_gb"] = value
    if db_update:
        await ProxyDAO(session).update_fields(proxy, **db_update)

    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    # Перерисовываем карточку редактирования
    proxy = await ProxyDAO(session).get_by_id(proxy_id)
    card_text = await _proxy_edit_text(proxy)
    if msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=card_text,
                parse_mode="HTML",
                reply_markup=_proxy_edit_keyboard(proxy.id, proxy.user_id),
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(
        card_text,
        parse_mode="HTML",
        reply_markup=_proxy_edit_keyboard(proxy.id, proxy.user_id),
    )


@router.callback_query(AdminProxyResetTrafficCallback.filter())
async def handle_reset_traffic(
    call: CallbackQuery,
    callback_data: AdminProxyResetTrafficCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    proxy = await ProxyDAO(session).get_by_id(callback_data.proxy_id)
    if not proxy:
        await call.answer("Прокси не найден.", show_alert=True)
        return

    await state.clear()
    await call.message.edit_text(
        f"⚠️ Сбросить трафик для <code>{proxy.mtg_username}</code>?\n\n"
        "Это действие необратимо.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Да, сбросить",
                callback_data=AdminProxyResetTrafficConfirmCallback(
                    proxy_id=proxy.id
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=AdminProxyEditCallback(proxy_id=proxy.id).pack(),
            ),
        ]]),
    )
    await call.answer()


@router.callback_query(AdminProxyResetTrafficConfirmCallback.filter())
async def handle_reset_traffic_confirm(
    call: CallbackQuery,
    callback_data: AdminProxyResetTrafficConfirmCallback,
    session: AsyncSession,
) -> None:
    proxy = await ProxyDAO(session).get_by_id(callback_data.proxy_id)
    if not proxy:
        await call.answer("Прокси не найден.", show_alert=True)
        return

    try:
        await admin_panel.reset_user_traffic(proxy.node.panel_id, proxy.mtg_username)
    except Exception as e:
        await call.answer(f"❌ Ошибка панели: {e}", show_alert=True)
        return

    text = await _proxy_edit_text(proxy)
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_proxy_edit_keyboard(proxy.id, proxy.user_id),
    )
    await call.answer("✅ Трафик сброшен.")


def _parse_field(field: str, text: str):
    """Возвращает (value, error_str). value=None означает сброс поля."""
    if text in ("0", "-"):
        return None, None

    if field == "max_devices":
        try:
            v = int(text)
            if v < 1:
                raise ValueError
            return v, None
        except ValueError:
            return None, "Введите целое число ≥ 1."

    if field == "traffic_limit_gb":
        try:
            v = float(text.replace(",", "."))
            if v <= 0:
                raise ValueError
            return v, None
        except ValueError:
            return None, "Введите число > 0 (например 100 или 50.5)."

    if field == "expires_at":
        if text.startswith("+"):
            try:
                days = int(text[1:])
                if days < 1:
                    raise ValueError
                return datetime.now(tz=timezone.utc) + timedelta(days=days), None
            except ValueError:
                return None, "После '+' укажите целое число дней ≥ 1."
        try:
            dt = datetime.strptime(text, "%d.%m.%Y").replace(tzinfo=timezone.utc)
            return dt, None
        except ValueError:
            return None, "Формат даты: DD.MM.YYYY или +N дней."

    if field == "traffic_reset_interval":
        if text.lower() in ("daily", "monthly", "yearly"):
            return text.lower(), None
        return None, "Допустимые значения: daily, monthly, yearly."

    return None, "Неизвестное поле."
