import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from bot.callbacks import (
    AdminNodeSyncCallback,
    AdminNodeToggleCallback,
    AdminNodeViewCallback,
    AdminUserListCallback,
)
from bot.dao import NodeDAO, ProxyDAO, UserDAO
from bot.filters import AdminFilter
from bot.models.node import Node
from bot.services.admin_panel import admin_panel
from bot.utils.flags import flag_emoji

router = Router()
router.callback_query.filter(AdminFilter())


# ── Утилиты ───────────────────────────────────────────────────────────────────

def _status_icon(online: bool | None) -> str:
    if online is True:
        return "🟢"
    if online is False:
        return "🔴"
    return "⚪"


def _dashboard_keyboard(nodes: list[Node]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{'✅' if n.is_active else '❌'} {flag_emoji(n.flag)} {n.name}",
            callback_data=AdminNodeViewCallback(node_id=n.id).pack(),
        )]
        for n in nodes
    ]
    buttons.append([InlineKeyboardButton(
        text="🔄 Синхронизировать ноды",
        callback_data=AdminNodeSyncCallback().pack(),
    )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _node_detail_keyboard(node: Node) -> InlineKeyboardMarkup:
    toggle_text = "🟢 Активировать" if not node.is_active else "🔴 Деактивировать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=toggle_text,
            callback_data=AdminNodeToggleCallback(node_id=node.id).pack(),
        )],
        [InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=AdminNodeViewCallback(node_id=node.id).pack(),
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:dashboard")],
    ])


def _node_detail_text(
    node: Node,
    summary: dict | None,
    node_traffic: dict | None = None,
) -> str:
    lines = [
        f"🌐 <b>{flag_emoji(node.flag)} {node.name}</b>",
        f"🖥 <b>Хост</b>: <code>{node.host}</code>",
        f"📌 <b>Статус в боте</b>: {'✅ Активна' if node.is_active else '❌ Деактивирована'}",
        "",
    ]

    if summary is None:
        lines.append("⚪ Данные панели недоступны.")
        return "\n".join(lines)

    node_online: bool = summary.get("online", False)
    lines.append(f"⚡ <b>Статус ноды</b>: {_status_icon(node_online)} {'онлайн' if node_online else 'оффлайн'}")

    users: list[dict] = summary.get("users") or []
    if users:
        online_users = sum(1 for u in users if (u.get("connections") or 0) > 0)
        total_connections = sum(u.get("connections") or 0 for u in users)
        lines.append(f"👤 <b>Пользователей онлайн</b>: {online_users} / {len(users)}")
        lines.append(f"📱 <b>Активных подключений</b>: {total_connections}")

    # Трафик: предпочитаем данные из /traffic (прямой SSH), fallback — из summary
    traffic: dict = node_traffic or summary.get("traffic") or {}
    if traffic:
        total_rx = sum(
            _parse_traffic(v.get("rx", "0"))
            for v in traffic.values() if isinstance(v, dict)
        )
        total_tx = sum(
            _parse_traffic(v.get("tx", "0"))
            for v in traffic.values() if isinstance(v, dict)
        )
        if total_rx or total_tx:
            lines.append(f"📊 <b>Трафик</b>: ↓ {_bytes_human(total_rx)} / ↑ {_bytes_human(total_tx)}")

    return "\n".join(lines)


def _bytes_human(b: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} ТБ"


def _parse_traffic(value: str) -> float:
    """Парсит строку трафика вида '1.25MB' или '512B' в байты. '—' → 0."""
    suffixes = {"tb": 1024**4, "gb": 1024**3, "mb": 1024**2, "kb": 1024, "b": 1}
    s = value.strip().lower()
    for suffix, mult in suffixes.items():
        if s.endswith(suffix):
            try:
                return float(s[: -len(suffix)]) * mult
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# ── Хендлеры ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:dashboard")
async def handle_dashboard(call: CallbackQuery, session: AsyncSession) -> None:
    nodes = await NodeDAO(session).get_all()
    total_users = await UserDAO(session).count_all()
    total_proxies = await ProxyDAO(session).count_active()
    active_nodes = sum(1 for n in nodes if n.is_active)

    text = (
        f"🖥 <b>Дашборд</b>\n\n"
        f"👥 <b>Пользователей:</b> {total_users}\n"
        f"🔌 <b>Активных прокси:</b> {total_proxies}\n"
        f"🌐 <b>Нод:</b> {len(nodes)} (✅ {active_nodes} активных)\n\n"
        f"Выберите ноду для подробностей:"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_dashboard_keyboard(nodes),
    )
    await call.answer()


@router.callback_query(AdminNodeViewCallback.filter())
async def handle_node_view(
    call: CallbackQuery,
    callback_data: AdminNodeViewCallback,
    session: AsyncSession,
) -> None:
    await call.answer("⏳ Загружаю данные ноды...")

    node = await NodeDAO(session).get_by_id(callback_data.node_id)
    if not node:
        await call.answer("Нода не найдена.", show_alert=True)
        return

    summary: dict | None = None
    node_traffic: dict | None = None
    results = await asyncio.gather(
        admin_panel.get_node_summary(node.panel_id),
        admin_panel.get_node_traffic(node.panel_id),
        return_exceptions=True,
    )
    if not isinstance(results[0], Exception):
        summary = results[0]
    else:
        logger.exception("Ошибка summary node=%s: %s", node.name, results[0])
    if not isinstance(results[1], Exception):
        node_traffic = results[1]
    else:
        logger.warning("Ошибка traffic node=%s: %s", node.name, results[1])

    try:
        await call.message.edit_text(
            _node_detail_text(node, summary, node_traffic),
            parse_mode="HTML",
            reply_markup=_node_detail_keyboard(node),
        )
        await call.answer("✅ Данные обновлены.", show_alert=True)
    except TelegramBadRequest:
        await call.answer("ℹ️ Данные не изменились.", show_alert=True)


@router.callback_query(AdminNodeToggleCallback.filter())
async def handle_node_toggle(
    call: CallbackQuery,
    callback_data: AdminNodeToggleCallback,
    session: AsyncSession,
) -> None:
    dao = NodeDAO(session)
    node = await dao.get_by_id(callback_data.node_id)
    if not node:
        await call.answer("Нода не найдена.", show_alert=True)
        return

    await dao.set_active(node, not node.is_active)
    action = "активирована" if node.is_active else "деактивирована"

    summary: dict | None = None
    node_traffic: dict | None = None
    results = await asyncio.gather(
        admin_panel.get_node_summary(node.panel_id),
        admin_panel.get_node_traffic(node.panel_id),
        return_exceptions=True,
    )
    if not isinstance(results[0], Exception):
        summary = results[0]
    else:
        logger.warning("Ошибка summary node=%s после toggle: %s", node.name, results[0])
    if not isinstance(results[1], Exception):
        node_traffic = results[1]
    else:
        logger.warning("Ошибка traffic node=%s после toggle: %s", node.name, results[1])

    await call.message.edit_text(
        _node_detail_text(node, summary, node_traffic),
        parse_mode="HTML",
        reply_markup=_node_detail_keyboard(node),
    )
    await call.answer(f"✅ Нода {action}.")


@router.callback_query(AdminNodeSyncCallback.filter())
async def handle_node_sync(
    call: CallbackQuery,
    session: AsyncSession,
) -> None:
    await call.answer("⏳ Синхронизирую...")

    try:
        remote_nodes = await admin_panel.get_nodes()
    except Exception:
        await call.answer("❌ Не удалось получить список нод с панели.", show_alert=True)
        return

    dao = NodeDAO(session)
    for n in remote_nodes:
        await dao.upsert(n["id"], n["name"], n["host"], n.get("flag"), n.get("agent_port"))

    nodes = await dao.get_all()
    total_users = await UserDAO(session).count_all()
    total_proxies = await ProxyDAO(session).count_active()
    active_nodes = sum(1 for n in nodes if n.is_active)

    text = (
        f"🖥 <b>Дашборд</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"🔌 Активных прокси: <b>{total_proxies}</b>\n"
        f"🌐 Нод: <b>{len(nodes)}</b> (✅ {active_nodes} активных)\n\n"
        f"✅ Синхронизировано нод: {len(remote_nodes)}\n\n"
        f"Выберите ноду для подробностей:"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_dashboard_keyboard(nodes),
    )
