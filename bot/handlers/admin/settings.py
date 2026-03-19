from aiogram import F, Router
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

from bot.callbacks import AdminProxySettingsFieldCallback
from bot.dao import ProxySettingsDAO
from bot.filters import AdminFilter
from bot.models.settings import ProxySettings

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

_FIELD_LABELS = {
    "max_devices": "Устройства",
    "traffic_limit_gb": "Трафик (ГБ)",
    "expires_days": "Срок (дней)",
    "traffic_reset_interval": "Сброс трафика",
}

_RESET_INTERVAL_LABELS = {
    "daily": "ежедневно",
    "monthly": "ежемесячно",
    "yearly": "ежегодно",
}


class ProxySettingsStates(StatesGroup):
    editing_field = State()


def _settings_text(s: ProxySettings | None) -> str:
    if s is None:
        max_dev = traffic = expires = reset = "не задано"
    else:
        max_dev = str(s.max_devices) if s.max_devices is not None else "∞"
        traffic = f"{s.traffic_limit_gb} ГБ" if s.traffic_limit_gb is not None else "∞"
        expires = f"{s.expires_days} дн." if s.expires_days is not None else "∞"
        reset = _RESET_INTERVAL_LABELS.get(
            s.traffic_reset_interval or "", s.traffic_reset_interval or "нет"
        )
    return (
        "⚙️ <b>Настройки прокси по умолчанию</b>\n\n"
        f"📱 Макс. устройств: <b>{max_dev}</b>\n"
        f"📊 Трафик: <b>{traffic}</b>\n"
        f"📅 Срок: <b>{expires}</b>\n"
        f"🔄 Сброс трафика: <b>{reset}</b>"
    )


def _settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Устройства",
                callback_data=AdminProxySettingsFieldCallback(
                    field="max_devices"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="✏️ Трафик",
                callback_data=AdminProxySettingsFieldCallback(
                    field="traffic_limit_gb"
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="✏️ Срок",
                callback_data=AdminProxySettingsFieldCallback(
                    field="expires_days"
                ).pack(),
            ),
            InlineKeyboardButton(
                text="✏️ Сброс",
                callback_data=AdminProxySettingsFieldCallback(
                    field="traffic_reset_interval"
                ).pack(),
            ),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")],
    ])


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:proxy_settings")]
    ])


_FIELD_PROMPTS = {
    "max_devices": (
        "Введите максимальное число устройств (целое ≥ 1).\n"
        "Отправьте <b>0</b> или <b>-</b> для снятия ограничения."
    ),
    "traffic_limit_gb": (
        "Введите лимит трафика в ГБ (число > 0, например <b>100</b> или <b>50.5</b>).\n"
        "Отправьте <b>0</b> или <b>-</b> для снятия ограничения."
    ),
    "expires_days": (
        "Введите срок действия прокси в днях (целое ≥ 1).\n"
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


@router.callback_query(F.data == "admin:proxy_settings")
async def handle_proxy_settings(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    s = await ProxySettingsDAO(session).get()
    await call.message.edit_text(
        _settings_text(s),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(),
    )
    await call.answer()


@router.callback_query(AdminProxySettingsFieldCallback.filter())
async def handle_settings_field_start(
    call: CallbackQuery,
    callback_data: AdminProxySettingsFieldCallback,
    state: FSMContext,
) -> None:
    field = callback_data.field
    prompt = _FIELD_PROMPTS.get(field, "Введите значение:")
    await state.set_state(ProxySettingsStates.editing_field)
    await state.update_data(
        editing_field=field, settings_msg_id=call.message.message_id
    )
    await call.message.edit_text(
        f"✏️ <b>{_FIELD_LABELS[field]}</b>\n\n{prompt}",
        parse_mode="HTML",
        reply_markup=_cancel_keyboard(),
    )
    await call.answer()


@router.message(StateFilter(ProxySettingsStates.editing_field))
async def handle_settings_field_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    fsm_data = await state.get_data()
    field = fsm_data["editing_field"]
    msg_id = fsm_data.get("settings_msg_id")
    text = message.text.strip() if message.text else ""

    value, error = _parse_field(field, text)
    if error:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        if msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=msg_id,
                    text=(
                        f"✏️ <b>{_FIELD_LABELS[field]}</b>\n\n"
                        f"❌ {error}\n\n{_FIELD_PROMPTS[field]}"
                    ),
                    parse_mode="HTML",
                    reply_markup=_cancel_keyboard(),
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(
            f"❌ {error}\n\n{_FIELD_PROMPTS[field]}",
            parse_mode="HTML",
            reply_markup=_cancel_keyboard(),
        )
        return

    await ProxySettingsDAO(session).update(**{field: value})
    await state.clear()

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    s = await ProxySettingsDAO(session).get()
    if msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=_settings_text(s),
                parse_mode="HTML",
                reply_markup=_settings_keyboard(),
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(
        _settings_text(s),
        parse_mode="HTML",
        reply_markup=_settings_keyboard(),
    )


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

    if field == "expires_days":
        try:
            v = int(text)
            if v < 1:
                raise ValueError
            return v, None
        except ValueError:
            return None, "Введите целое число ≥ 1."

    if field == "traffic_reset_interval":
        if text.lower() in ("daily", "monthly", "yearly"):
            return text.lower(), None
        return None, "Допустимые значения: daily, monthly, yearly."

    return None, "Неизвестное поле."
