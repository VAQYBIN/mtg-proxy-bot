import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_session
from bot.dao import NodeDAO, ProxyDAO, ProxySettingsDAO
from bot.models.proxy import Proxy
from bot.models.user import User
from bot.services.admin_panel import admin_panel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["proxies"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NodeResponse(BaseModel):
    id: int
    name: str
    flag: str | None
    host: str

    model_config = {"from_attributes": True}


class ProxyResponse(BaseModel):
    id: int
    node: NodeResponse
    link: str
    port: int
    secret: str
    expires_at: datetime | None
    traffic_limit_gb: float | None
    is_active: bool
    created_at: datetime
    tme_link: str

    model_config = {"from_attributes": True}


class ProxyStatsResponse(BaseModel):
    connections: int | None
    max_devices: int | None
    traffic_rx: str | None
    traffic_tx: str | None


class CreateProxyRequest(BaseModel):
    node_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tme_link(proxy: Proxy) -> str:
    return (
        f"tg://proxy"
        f"?server={proxy.node.host}"
        f"&port={proxy.port}"
        f"&secret={proxy.secret}"
    )


def _mtg_username(user: User) -> str:
    """Формат имени пользователя на MTG-панели.

    Telegram-пользователи: tg_{telegram_id} (совместимо с ботом).
    Web-пользователи без Telegram: web_{user.id}.
    """
    if user.telegram_id is not None:
        return f"tg_{user.telegram_id}"
    return f"web_{user.id}"


def _proxy_to_response(proxy: Proxy) -> ProxyResponse:
    return ProxyResponse(
        id=proxy.id,
        node=NodeResponse.model_validate(proxy.node),
        link=proxy.link,
        port=proxy.port,
        secret=proxy.secret,
        expires_at=proxy.expires_at,
        traffic_limit_gb=proxy.traffic_limit_gb,
        is_active=proxy.is_active,
        created_at=proxy.created_at,
        tme_link=_tme_link(proxy),
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


@router.get("/nodes", response_model=list[NodeResponse])
async def list_nodes(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    nodes = await NodeDAO(session).get_all_active()
    return [NodeResponse.model_validate(n) for n in nodes]


# ---------------------------------------------------------------------------
# Proxies
# ---------------------------------------------------------------------------


@router.get("/proxies", response_model=list[ProxyResponse])
async def list_proxies(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    proxies = await ProxyDAO(session).get_user_proxies(current_user.id)
    return [_proxy_to_response(p) for p in proxies]


@router.post(
    "/proxies",
    response_model=ProxyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_proxy(
    body: CreateProxyRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    node = await NodeDAO(session).get_by_id(body.node_id)
    if node is None or not node.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found or inactive",
        )

    existing = await ProxyDAO(session).get_user_proxy_on_node(
        current_user.id, body.node_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proxy on this node already exists",
        )

    ps = await ProxySettingsDAO(session).get()
    expires_at: datetime | None = None
    if ps and ps.expires_days:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=ps.expires_days)
    traffic_limit_gb: float | None = ps.traffic_limit_gb if ps else None

    mtg_username = _mtg_username(current_user)

    try:
        data = await admin_panel.create_user(
            node.panel_id,
            mtg_username,
            expires_at=expires_at,
            traffic_limit_gb=traffic_limit_gb,
        )
    except Exception as e:
        logger.error("Failed to create user on panel: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create proxy on node",
        )

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

    proxy = await ProxyDAO(session).create(
        user_id=current_user.id,
        node_id=body.node_id,
        mtg_username=mtg_username,
        link=data["link"],
        port=data["port"],
        secret=data["secret"],
        expires_at=expires_at,
        traffic_limit_gb=traffic_limit_gb,
    )
    proxy.node = node
    return _proxy_to_response(proxy)


@router.delete("/proxies/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(
    proxy_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    proxy = await ProxyDAO(session).get_by_id(proxy_id)

    if proxy is None or not proxy.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )
    if proxy.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your proxy",
        )

    try:
        await admin_panel.delete_user(proxy.node.panel_id, proxy.mtg_username)
    except Exception as e:
        logger.warning("Panel delete failed (continuing): %s", e)

    await ProxyDAO(session).delete(proxy)


@router.get("/proxies/{proxy_id}/stats", response_model=ProxyStatsResponse)
async def proxy_stats(
    proxy_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    proxy = await ProxyDAO(session).get_by_id(proxy_id)

    if proxy is None or not proxy.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy not found",
        )
    if proxy.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your proxy",
        )

    connections: int | None = None
    max_devices: int | None = None
    traffic_rx: str | None = None
    traffic_tx: str | None = None

    try:
        summary = await admin_panel.get_node_summary(proxy.node.panel_id)
        users = summary.get("users") or []
        entry = next(
            (u for u in users if u["name"] == proxy.mtg_username), None
        )
        if entry:
            connections = entry.get("connections")
            max_devices = entry.get("max_devices")

        traffic = summary.get("traffic") or {}
        user_traffic = traffic.get(proxy.mtg_username)
        if user_traffic:
            traffic_rx = user_traffic.get("rx")
            traffic_tx = user_traffic.get("tx")
    except Exception as e:
        logger.warning("Could not fetch stats from panel: %s", e)

    return ProxyStatsResponse(
        connections=connections,
        max_devices=max_devices,
        traffic_rx=traffic_rx,
        traffic_tx=traffic_tx,
    )
