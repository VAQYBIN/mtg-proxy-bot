import logging
from datetime import datetime

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


class AdminPanelClient:
    def __init__(self) -> None:
        self._base_url = settings.ADMIN_PANEL_URL.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "x-auth-token": settings.ADMIN_PANEL_TOKEN,
        }
        self._client = httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(10.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_nodes(self) -> list[dict]:
        r = await self._client.get(f"{self._base_url}/api/nodes")
        r.raise_for_status()
        return r.json()

    async def get_node_users(self, node_id: int) -> list[dict]:
        r = await self._client.get(f"{self._base_url}/api/nodes/{node_id}/users")
        r.raise_for_status()
        return r.json()

    async def create_user(
        self,
        node_id: int,
        name: str,
        expires_at: datetime | None = None,
        traffic_limit_gb: float | None = None,
    ) -> dict:
        body: dict = {"name": name, "note": ""}
        if expires_at:
            body["expires_at"] = expires_at.isoformat()
        if traffic_limit_gb is not None:
            body["traffic_limit_gb"] = traffic_limit_gb

        r = await self._client.post(
            f"{self._base_url}/api/nodes/{node_id}/users",
            json=body,
        )
        r.raise_for_status()
        return r.json()

    async def delete_user(self, node_id: int, name: str) -> bool:
        r = await self._client.delete(
            f"{self._base_url}/api/nodes/{node_id}/users/{name}"
        )
        r.raise_for_status()
        return True

    async def start_user(self, node_id: int, name: str) -> bool:
        r = await self._client.post(
            f"{self._base_url}/api/nodes/{node_id}/users/{name}/start"
        )
        r.raise_for_status()
        return True

    async def stop_user(self, node_id: int, name: str) -> bool:
        r = await self._client.post(
            f"{self._base_url}/api/nodes/{node_id}/users/{name}/stop"
        )
        r.raise_for_status()
        return True

    async def get_status(self) -> list[dict]:
        """GET /api/status — все ноды: {id, name, host, online, containers, online_users}."""
        r = await self._client.get(f"{self._base_url}/api/status")
        r.raise_for_status()
        return r.json()

    async def get_node_traffic(self, node_id: int) -> dict:
        """GET /api/nodes/:id/traffic — трафик всех клиентов ноды {name: {rx, tx}}."""
        r = await self._client.get(f"{self._base_url}/api/nodes/{node_id}/traffic")
        r.raise_for_status()
        return r.json()

    async def get_agent_metrics(self, host: str, port: int) -> dict:
        """GET http://host:port/metrics — метрики контейнеров от MTG Agent."""
        r = await self._client.get(
            f"http://{host}:{port}/metrics",
            headers={"x-agent-token": settings.AGENT_TOKEN},
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()


admin_panel = AdminPanelClient()
