from datetime import datetime

import httpx

from bot.config import settings


class AdminPanelClient:
    def __init__(self) -> None:
        self._base_url = settings.ADMIN_PANEL_URL.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "x-auth-token": settings.ADMIN_PANEL_TOKEN,
        }

    async def get_nodes(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self._base_url}/api/nodes", headers=self._headers)
            r.raise_for_status()
            return r.json()

    async def get_node_users(self, node_id: int) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base_url}/api/nodes/{node_id}/users",
                headers=self._headers,
            )
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

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/api/nodes/{node_id}/users",
                headers=self._headers,
                json=body,
            )
            r.raise_for_status()
            return r.json()

    async def delete_user(self, node_id: int, name: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{self._base_url}/api/nodes/{node_id}/users/{name}",
                headers=self._headers,
            )
            r.raise_for_status()
            return True

    async def start_user(self, node_id: int, name: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/api/nodes/{node_id}/users/{name}/start",
                headers=self._headers,
            )
            r.raise_for_status()
            return True

    async def stop_user(self, node_id: int, name: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/api/nodes/{node_id}/users/{name}/stop",
                headers=self._headers,
            )
            r.raise_for_status()
            return True


admin_panel = AdminPanelClient()
