import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.callbacks import (
    NodeSelectCallback,
    ProxyDeleteCallback,
    ProxyDeleteConfirmCallback,
    ProxyViewCallback,
)
from bot.config import settings
from bot.dao import NodeDAO, ProxyDAO, ProxySettingsDAO, UserDAO
from bot.models.proxy import Proxy
from bot.services.admin_panel import admin_panel
from bot.utils.flags import flag_emoji
from bot.utils.qr import build_qr_bytes

router = Router()


def _tme_link(proxy: Proxy) -> str:
    return (
        f"https://t.me/proxy"
        f"?server={proxy.node.host}"
        f"&port={proxy.port}"
        f"&secret={proxy.secret}"
    )


def _encode_ref(user_telegram_id: int) -> str:
    return base64.urlsafe_b64encode(
        str(user_telegram_id).encode()
    ).rstrip(b"=").decode()


def _share_url(
    bot_username: str,
    user_telegram_id: int,
    proxy_link: str | None = None,
) -> str:
    ref_link = f"t.me/{bot_username}?start=r{_encode_ref(user_telegram_id)}"
    if proxy_link:
        text = (
            "\nПолучи свой бесплатный прокси — работает без регистрации! 🔒\n\n"
            f"Мой прокси для Telegram:\n{proxy_link}"
        )
    else:
        text = "\nПолучи свой прокси для Telegram — работает без регистрации! 🔒"
    if settings.VPN_ADS_ON_SHARE_LINK:
        text += (
            "\n\nТакже если у тебя не грузит YouTube и другие зарубежные сервисы"
            f" — рекомендую {settings.VPN_ADS_ON_SHARE_LINK}"
        )
    return "https://t.me/share/url?" + urlencode({"url": ref_link, "text": text})


def _proxy_detail_keyboard(
    proxy: Proxy,
    bot_username: str,
    user_telegram_id: int,
    proxy_link: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Подключиться", url=proxy.link)],
        [InlineKeyboardButton(
            text="📤 Поделиться",
            url=_share_url(bot_username, user_telegram_id, proxy_link),
        )],
        [InlineKeyboardButton(
            text="🗑 Удалить прокси",
            callback_data=ProxyDeleteCallback(proxy_id=proxy.id).pack(),
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="proxy:list")],
    ])


def _proxy_delete_confirm_keyboard(proxy_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=ProxyDeleteConfirmCallback(proxy_id=proxy_id).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=ProxyViewCallback(proxy_id=proxy_id).pack(),
            ),
        ]
    ])


def _node_list_keyboard(nodes) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{flag_emoji(n.flag)} {n.name}",
            callback_data=NodeSelectCallback(node_id=n.id).pack(),
        )]
        for n in nodes
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _proxy_list_keyboard(proxies: list[Proxy]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{flag_emoji(p.node.flag)} {p.node.name}",
            callback_data=ProxyViewCallback(proxy_id=p.id).pack(),
        )]
        for p in proxies
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _fetch_device_info(proxy: Proxy) -> tuple[int | None, int | None]:
    """Возвращает (connections, max_devices) для прокси из /summary.

    Данные берутся из кеша панели (обновляется каждые 10 сек) — быстро, без
    прямого обращения к агенту. connections — текущие подключения,
    max_devices — лимит (None = ∞).
    """
    try:
        summary = await admin_panel.get_node_summary(proxy.node.panel_id)
        users = summary.get("users") or []
        entry = next((u for u in users if u["name"] == proxy.mtg_username), None)
        if entry:
            return entry.get("connections"), entry.get("max_devices")
    except Exception:
        pass
    return None, None


def _format_proxy_caption(
    proxy: Proxy,
    current_devices: int | None = None,
    max_devices: int | None = None,
) -> str:
    lines = [f"<b>{flag_emoji(proxy.node.flag)} {proxy.node.name}</b>\n"]
    if proxy.expires_at:
        lines.append(f"📅 <b>Действует до:</b> {proxy.expires_at.strftime('%d.%m.%Y')}")
    else:
        lines.append("📅 <b>Срок действия:</b> безлимитный")
    if proxy.traffic_limit_gb:
        lines.append(f"📊 <b>Трафик:</b> {proxy.traffic_limit_gb} ГБ")
    else:
        lines.append("📊 <b>Трафик:</b> безлимитный")

    if current_devices is not None or max_devices is not None:
        cur = str(current_devices) if current_devices is not None else "?"
        lim = str(max_devices) if max_devices is not None else "∞"
        lines.append(f"📱 <b>Устройств:</b> {cur} / {lim}")

    lines.append(f"\n🔗 <code>{_tme_link(proxy)}</code>")
    return "\n".join(lines)


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def _send_proxy_photo(
    message: Message,
    proxy: Proxy,
    bot_username: str,
    user_telegram_id: int,
    current_devices: int | None = None,
    max_devices: int | None = None,
) -> None:
    proxy_link = _tme_link(proxy) if settings.SHARE_PROXY_ON_INVITE_ENABLED else None
    qr_buf = build_qr_bytes(_tme_link(proxy))
    await message.answer_photo(
        photo=BufferedInputFile(qr_buf.read(), filename="qr.png"),
        caption=_format_proxy_caption(proxy, current_devices, max_devices),
        parse_mode="HTML",
        reply_markup=_proxy_detail_keyboard(
            proxy, bot_username, user_telegram_id, proxy_link
        ),
    )


# ── Главное меню ──────────────────────────────────────────────

@router.callback_query(F.data == "menu:main")
async def handle_main_menu(call: CallbackQuery) -> None:
    from bot.handlers.common import main_menu_keyboard
    if call.message.photo:
        await _delete_message(call.message)
        await call.message.answer("Главное меню", reply_markup=main_menu_keyboard())
    else:
        await call.message.edit_text("Главное меню", reply_markup=main_menu_keyboard())
    await call.answer()


# ── Получить прокси ───────────────────────────────────────────

@router.callback_query(F.data == "proxy:get")
async def handle_proxy_get(call: CallbackQuery, session: AsyncSession) -> None:
    user = await UserDAO(session).get_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer("Сначала отправьте /start", show_alert=True)
        return
    all_nodes = await NodeDAO(session).get_all_active()
    user_proxies = await ProxyDAO(session).get_user_proxies(user.id)

    occupied_node_ids = {p.node_id for p in user_proxies}
    available = [n for n in all_nodes if n.id not in occupied_node_ids]

    if not available:
        await call.message.edit_text(
            "⚠️ Вы достигли лимита: у вас уже есть прокси на всех доступных нодах.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
            ]),
        )
        await call.answer()
        return

    await call.message.edit_text(
        "Выберите ноду для подключения:",
        reply_markup=_node_list_keyboard(available),
    )
    await call.answer()


@router.callback_query(NodeSelectCallback.filter())
async def handle_node_select(
    call: CallbackQuery,
    callback_data: NodeSelectCallback,
    session: AsyncSession,
    bot_username: str,
) -> None:
    node_id = callback_data.node_id
    user = await UserDAO(session).get_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer("Сначала отправьте /start", show_alert=True)
        return
    node = await NodeDAO(session).get_by_id(node_id)

    if not node:
        await call.answer("Нода не найдена.", show_alert=True)
        return

    existing = await ProxyDAO(session).get_user_proxy_on_node(user.id, node_id)
    if existing:
        await call.answer("У вас уже есть прокси на этой ноде.", show_alert=True)
        return

    await call.message.edit_text(
        f"⏳ Создаю прокси на ноде {flag_emoji(node.flag)} {node.name}..."
    )
    await call.answer()

    ps = await ProxySettingsDAO(session).get()
    expires_at: datetime | None = None
    if ps and ps.expires_days:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=ps.expires_days)
    traffic_limit_gb: float | None = ps.traffic_limit_gb if ps else None

    mtg_username = f"tg_{call.from_user.id}"
    try:
        data = await admin_panel.create_user(
            node.panel_id,
            mtg_username,
            expires_at=expires_at,
            traffic_limit_gb=traffic_limit_gb,
        )
    except Exception:
        await call.message.edit_text(
            "❌ Не удалось создать прокси. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
            ]),
        )
        return

    proxy = await ProxyDAO(session).create(
        user_id=user.id,
        node_id=node_id,
        mtg_username=mtg_username,
        link=data["link"],
        port=data["port"],
        secret=data["secret"],
        expires_at=expires_at,
        traffic_limit_gb=traffic_limit_gb,
    )

    # Применяем max_devices и traffic_reset_interval через update_user
    if ps and (ps.max_devices is not None or ps.traffic_reset_interval is not None):
        update_fields: dict = {}
        if ps.max_devices is not None:
            update_fields["max_devices"] = ps.max_devices
        if ps.traffic_reset_interval is not None:
            update_fields["traffic_reset_interval"] = ps.traffic_reset_interval
        try:
            await admin_panel.update_user(node.panel_id, mtg_username, **update_fields)
        except Exception:
            pass
    proxy.node = node

    caption = (
        f"✅ <b>Прокси создан!</b>\n\n"
        f"🌐 <b>Нода:</b> {flag_emoji(node.flag)} {node.name}\n\n"
        f"🔗 <b>Ссылка для подключения:</b>\n<code>{_tme_link(proxy)}</code>"
    )
    share_proxy_link = (
        _tme_link(proxy) if settings.SHARE_PROXY_ON_INVITE_ENABLED else None
    )
    qr_buf = build_qr_bytes(_tme_link(proxy))
    await call.message.answer_photo(
        photo=BufferedInputFile(qr_buf.read(), filename="qr.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔌 Подключиться", url=proxy.link)],
            [InlineKeyboardButton(
                text="📤 Поделиться",
                url=_share_url(bot_username, call.from_user.id, share_proxy_link),
            )],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="menu:main")],
        ]),
    )
    await _delete_message(call.message)


# ── Мои прокси ────────────────────────────────────────────────

@router.callback_query(F.data == "proxy:list")
async def handle_proxy_list(call: CallbackQuery, session: AsyncSession) -> None:
    user = await UserDAO(session).get_by_telegram_id(call.from_user.id)
    if user is None:
        await call.answer("Сначала отправьте /start", show_alert=True)
        return
    proxies = await ProxyDAO(session).get_user_proxies(user.id)

    text = "У вас пока нет прокси.\n\nНажмите «Получить прокси» чтобы создать." \
        if not proxies else "Ваши прокси — выберите для просмотра:"
    keyboard = (
        _proxy_list_keyboard(proxies) if proxies
        else InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
        ])
    )

    if call.message.photo:
        await _delete_message(call.message)
        await call.message.answer(text, reply_markup=keyboard)
    else:
        await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(ProxyViewCallback.filter())
async def handle_proxy_view(
    call: CallbackQuery,
    callback_data: ProxyViewCallback,
    session: AsyncSession,
    bot_username: str,
) -> None:
    proxy = await ProxyDAO(session).get_by_id(callback_data.proxy_id)

    if not proxy or not proxy.is_active:
        await call.answer("Прокси не найден.", show_alert=True)
        return

    current_devices, max_devices = await _fetch_device_info(proxy)
    await _delete_message(call.message)
    await _send_proxy_photo(
        call.message, proxy, bot_username, call.from_user.id,
        current_devices, max_devices,
    )
    await call.answer()


@router.callback_query(ProxyDeleteCallback.filter())
async def handle_proxy_delete(
    call: CallbackQuery,
    callback_data: ProxyDeleteCallback,
    session: AsyncSession,
) -> None:
    proxy = await ProxyDAO(session).get_by_id(callback_data.proxy_id)
    if not proxy:
        await call.answer("Прокси не найден.", show_alert=True)
        return

    text = (
        f"Вы уверены, что хотите удалить прокси "
        f"{flag_emoji(proxy.node.flag)} {proxy.node.name}?\n\nЭто действие необратимо."
    )
    if call.message.photo:
        await _delete_message(call.message)
        await call.message.answer(
            text, reply_markup=_proxy_delete_confirm_keyboard(proxy.id)
        )
    else:
        await call.message.edit_text(
            text, reply_markup=_proxy_delete_confirm_keyboard(proxy.id)
        )
    await call.answer()


@router.callback_query(ProxyDeleteConfirmCallback.filter())
async def handle_proxy_delete_confirm(
    call: CallbackQuery,
    callback_data: ProxyDeleteConfirmCallback,
    session: AsyncSession,
) -> None:
    proxy = await ProxyDAO(session).get_by_id(callback_data.proxy_id)
    if not proxy:
        await call.answer("Прокси не найден.", show_alert=True)
        return

    try:
        await admin_panel.delete_user(proxy.node.panel_id, proxy.mtg_username)
    except Exception:
        pass

    await ProxyDAO(session).delete(proxy)

    await call.message.edit_text(
        f"✅ Прокси {flag_emoji(proxy.node.flag)} {proxy.node.name} удалён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="menu:main")]
        ]),
    )
    await call.answer()
