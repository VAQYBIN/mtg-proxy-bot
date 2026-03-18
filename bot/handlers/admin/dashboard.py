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
    agent_online: bool,
    agent_metrics: dict | None,
) -> str:
    lines = [
        f"🌐 <b>{flag_emoji(node.flag)} {node.name}</b>",
        f"🖥 <b>Хост</b>: <code>{node.host}</code>",
        f"📌 <b>Статус в боте</b>: {'✅ Активна' if node.is_active else '❌ Деактивирована'}",
        "",
    ]

    if not node.agent_port:
        lines.append("ℹ️ MTG Agent не настроен для этой ноды.")
        return "\n".join(lines)

    lines.append(f"⚡ <b>Агент</b>: {_status_icon(agent_online)} {'онлайн' if agent_online else 'оффлайн'}")

    if agent_online and agent_metrics:
        containers: list[dict] = agent_metrics.get("containers") or []
        running = sum(1 for c in containers if c.get("running"))
        online_users = sum(1 for c in containers if c.get("is_online"))
        total_rx = sum(
            c["traffic"]["rx_bytes"] for c in containers
            if isinstance(c.get("traffic"), dict) and isinstance(c["traffic"].get("rx_bytes"), int)
        )
        total_tx = sum(
            c["traffic"]["tx_bytes"] for c in containers
            if isinstance(c.get("traffic"), dict) and isinstance(c["traffic"].get("tx_bytes"), int)
        )
        lines.append(f"📦 <b>Контейнеров запущено</b>: {running}")
        lines.append(f"👤 <b>Онлайн пользователей</b>: {online_users}")
        if total_rx or total_tx:
            lines.append(f"📊 <b>Трафик</b>: ↓ {_bytes_human(total_rx)} / ↑ {_bytes_human(total_tx)}")

    return "\n".join(lines)


def _bytes_human(b: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} ТБ"


# ── Хендлеры ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:dashboard")
async def handle_dashboard(call: CallbackQuery, session: AsyncSession) -> None:
    nodes = await NodeDAO(session).get_all()
    total_users = await UserDAO(session).count_all()
    total_proxies = await ProxyDAO(session).count_active()
    active_nodes = sum(1 for n in nodes if n.is_active)

    text = (
        f"🖥 <b>Дашборд</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"🔌 Активных прокси: <b>{total_proxies}</b>\n"
        f"🌐 Нод: <b>{len(nodes)}</b> (✅ {active_nodes} активных)\n\n"
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

    agent_online = False
    agent_metrics: dict | None = None
    if node.agent_port:
        try:
            agent_metrics = await admin_panel.get_agent_metrics(node.host, node.agent_port)
            agent_online = True
        except Exception:
            logger.exception("Ошибка при получении метрик агента node=%s", node.name)

    try:
        await call.message.edit_text(
            _node_detail_text(node, agent_online, agent_metrics),
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

    agent_online = False
    agent_metrics: dict | None = None
    if node.agent_port:
        try:
            agent_metrics = await admin_panel.get_agent_metrics(node.host, node.agent_port)
            agent_online = True
        except Exception:
            logger.exception("Ошибка при получении метрик агента node=%s после toggle", node.name)

    await call.message.edit_text(
        _node_detail_text(node, agent_online, agent_metrics),
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
