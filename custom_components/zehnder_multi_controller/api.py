from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from rainmaker_http.client import RainmakerClient

_LOGGER = logging.getLogger(__name__)


class RainmakerError(Exception):
    """Base exception for Rainmaker adapter."""


class RainmakerAuthError(RainmakerError):
    """Raised for authentication related failures."""


class RainmakerConnectionError(RainmakerError, RuntimeError):
    """Raised for network/connectivity failures.

    Subclasses RuntimeError so callers that catch RuntimeError (legacy
    code paths in the config flow) will correctly treat connection
    failures as connectivity errors.
    """


class RainmakerAPI:
    """HTTP adapter for Rainmaker cloud API using `rainmaker-http`.

    This adapter implements the minimal operations used by the
    integration: login, nodes listing, params/config retrieval and batch set.
    """

    def __init__(
        self, hass: Any | None, host: Any, username: Any, password: Any
    ) -> None:
        """Initialize adapter with Home Assistant `hass`, host and creds."""
        self._hass = hass
        self.host = str(host).rstrip("/") + "/" if host is not None else ""
        self.username = str(username) if username is not None else ""
        self.password = str(password) if password is not None else ""
        self._client: RainmakerClient | None = None
        self._connected = False
        # currently, we only support the multicontrol service
        self._service_name: str = "multicontrol"

    async def async_close(self) -> None:
        """Close any resources held by the adapter."""
        if self._client is not None:
            try:
                await self._client.async_close()
            except (
                ClientError,
                RuntimeError,
            ) as err:  # pragma: no cover - defensive cleanup
                _LOGGER.debug("Error closing rainmaker_http client: %s", err)

    async def async_connect(self) -> None:
        """Authenticate against Rainmaker using the PyPI client."""
        try:
            client = RainmakerClient(self.host)
            self._client = client
            await client.async_login(self.username, self.password)
        except ClientError as err:
            _LOGGER.debug("Network error during rainmaker login: %s", err)
            raise RainmakerConnectionError("Network error") from err
        except Exception as err:
            _LOGGER.debug("Authentication/login failed: %s", err)
            raise RainmakerAuthError("Authentication failed") from err

        self._connected = True
        _LOGGER.debug("Rainmaker HTTP client login successful (host=%s)", self.host)

    async def async_get_nodes(self) -> dict[str, Any]:
        """Return a list of normalized nodes with params and params_meta."""
        try:
            assert self._client is not None
            data = await self._client.async_get_nodes(node_detail=True)
        except Exception as err:
            _LOGGER.debug("Failed to fetch nodes: %s", err)
            raise RainmakerConnectionError("Failed to fetch nodes") from err
        if "node_details" not in data:
            raise RainmakerError(f"Wrong data format for nodes: {data}")
        return data

    async def async_set_param(self, node_id: str, param: str, value: Any) -> None:
        if not self._connected:
            raise RainmakerConnectionError("Not connected")

        payload = {self._service_name: {param: value}}

        batch = [{"node_id": node_id, "payload": payload}]
        try:
            assert self._client is not None
            result = await self._client.async_set_params(batch)
        except Exception as err:
            _LOGGER.debug("Failed to set param via rainmaker client: %s", err)
            raise RainmakerError("Failed to set param") from err

        if isinstance(result, list):
            for res in result:
                if res.get("node_id") == node_id and res.get("status") != "success":
                    raise RainmakerError(f"Failed to set param: {res}")

    @property
    def is_connected(self) -> bool:
        return bool(self._connected)
