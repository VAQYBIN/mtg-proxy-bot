import logging
from datetime import datetime

import httpx
import pyotp

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
        self._totp_session: str | None = None

    def _totp_code(self) -> str:
        """Генерирует текущий 6-значный TOTP-код из секрета."""
        return pyotp.TOTP(settings.ADMIN_PANEL_TOTP_SECRET).now()

    async def _panel_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Выполняет запрос к панели с поддержкой TOTP.

        Если ADMIN_PANEL_TOTP_SECRET задан, добавляет заголовок x-totp-code.
        При 403 (истёкшая сессия) автоматически получает новый TOTP и повторяет.
        Сессионный токен из x-totp-session кешируется на 24ч.
        """
        if not settings.ADMIN_PANEL_TOTP_SECRET:
            return await self._client.request(method, url, **kwargs)

        extra_headers = kwargs.pop("headers", {})
        extra_headers["x-totp-code"] = self._totp_session or self._totp_code()

        r = await self._client.request(method, url, headers=extra_headers, **kwargs)

        # Обновляем сессионный токен, если панель его вернула
        session = r.headers.get("x-totp-session")
        if session:
            self._totp_session = session

        # При 403 — сессия протухла, получаем новый TOTP и повторяем один раз
        if r.status_code == 403:
            self._totp_session = None
            extra_headers["x-totp-code"] = self._totp_code()
            r = await self._client.request(method, url, headers=extra_headers, **kwargs)
            session = r.headers.get("x-totp-session")
            if session:
                self._totp_session = session

        return r

    async def close(self) -> None:
        await self._client.aclose()

    async def get_nodes(self) -> list[dict]:
        r = await self._panel_request("GET", f"{self._base_url}/api/nodes")
        r.raise_for_status()
        return r.json()

    async def get_node_users(self, node_id: int) -> list[dict]:
        r = await self._panel_request(
            "GET", f"{self._base_url}/api/nodes/{node_id}/users"
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

        r = await self._panel_request(
            "POST",
            f"{self._base_url}/api/nodes/{node_id}/users",
            json=body,
        )
        r.raise_for_status()
        return r.json()

    async def delete_user(self, node_id: int, name: str) -> bool:
        r = await self._panel_request(
            "DELETE",
            f"{self._base_url}/api/nodes/{node_id}/users/{name}",
        )
        r.raise_for_status()
        return True

    async def start_user(self, node_id: int, name: str) -> bool:
        r = await self._panel_request(
            "POST",
            f"{self._base_url}/api/nodes/{node_id}/users/{name}/start",
        )
        r.raise_for_status()
        return True

    async def stop_user(self, node_id: int, name: str) -> bool:
        r = await self._panel_request(
            "POST",
            f"{self._base_url}/api/nodes/{node_id}/users/{name}/stop",
        )
        r.raise_for_status()
        return True

    async def get_status(self) -> list[dict]:
        """GET /api/status — все ноды: {id, name, host, online, containers,
        online_users}."""
        r = await self._panel_request("GET", f"{self._base_url}/api/status")
        r.raise_for_status()
        return r.json()

    async def get_node_traffic(self, node_id: int) -> dict:
        """GET /api/nodes/:id/traffic — трафик всех клиентов ноды.

        Возвращает {name: {rx, tx}} где rx/tx — отформатированные строки ("1.25MB"),
        не байты.
        """
        r = await self._panel_request(
            "GET", f"{self._base_url}/api/nodes/{node_id}/traffic"
        )
        r.raise_for_status()
        return r.json()

    async def get_agent_metrics(self, host: str, port: int) -> dict:
        """GET http://host:port/metrics — метрики контейнеров от MTG Agent.

        Возвращает список контейнеров с полями:
        - rx_bytes / tx_bytes — трафик в байтах
        - traffic.rx / traffic.tx — отформатированные строки ("1.25MB")
        - devices — число устройств на контейнер
        - total — всего контейнеров
        - cached_at — метка времени кэша
        """
        r = await self._client.get(
            f"http://{host}:{port}/metrics",
            headers={"x-agent-token": settings.AGENT_TOKEN},
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()

    async def get_node_counts(self) -> dict:
        """GET /api/nodes/counts — количество пользователей по нодам:
        {str(node_id): count}."""
        r = await self._panel_request("GET", f"{self._base_url}/api/nodes/counts")
        r.raise_for_status()
        return r.json()

    async def get_node_summary(self, node_id: int) -> dict:
        """GET /api/nodes/:id/summary — сводка по ноде:
        {online, users[], traffic: {name: {rx, tx}}}."""
        r = await self._panel_request(
            "GET", f"{self._base_url}/api/nodes/{node_id}/summary"
        )
        r.raise_for_status()
        return r.json()

    async def check_node(self, node_id: int) -> dict:
        """GET /api/nodes/:id/check — SSH-проверка доступности ноды:
        {online, error?}."""
        r = await self._panel_request(
            "GET", f"{self._base_url}/api/nodes/{node_id}/check"
        )
        r.raise_for_status()
        return r.json()

    async def check_node_agent(self, node_id: int) -> dict:
        """GET /api/nodes/:id/check-agent — проверка агента через панель:
        {available, reason?}."""
        r = await self._panel_request(
            "GET", f"{self._base_url}/api/nodes/{node_id}/check-agent"
        )
        r.raise_for_status()
        return r.json()

    async def get_agent_version(self, node_id: int) -> dict:
        """GET /api/nodes/:id/agent-version — версия агента:
        {version, available, online}."""
        r = await self._panel_request(
            "GET", f"{self._base_url}/api/nodes/{node_id}/agent-version"
        )
        r.raise_for_status()
        return r.json()


admin_panel = AdminPanelClient()
