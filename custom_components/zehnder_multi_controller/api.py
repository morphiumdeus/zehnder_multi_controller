from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from aiohttp import ClientError

from rainmaker_http.client import RainmakerClient

"""HTTP-only adapter for the Zehnder Multi Controller / Rainmaker API.

This implementation uses the `rainmaker-http` PyPI package to perform
all API requests. It intentionally does not include alternative fallbacks
or the upstream runtime; that logic lives in the PyPI package.
"""

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
        self._service_map: dict[str, str] = {}
        self._param_service_map: dict[str, dict[str, str]] = {}

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

    async def async_get_nodes(self) -> list[dict[str, Any]]:
        """Return a list of normalized nodes with params and params_meta."""
        if not self._connected:
            await self.async_connect()
            if not self._connected:
                raise RainmakerConnectionError("Not connected")

        try:
            assert self._client is not None
            data = await self._client.async_get_nodes()
        except Exception as err:
            _LOGGER.debug("Failed to fetch nodes: %s", err)
            raise RainmakerConnectionError("Failed to fetch nodes") from err

        nodes_out: list[dict[str, Any]] = []

        node_items: list[Any] = []
        if isinstance(data, dict):
            if "nodes" in data and isinstance(data["nodes"], (list, dict)):
                node_items = (
                    data["nodes"]
                    if isinstance(data["nodes"], list)
                    else list(data["nodes"].values())
                )
            else:
                node_items = list(data.values()) if data else []
        elif isinstance(data, list):
            node_items = data

        tasks = [self._fetch_node_details(it) for it in node_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                _LOGGER.debug("Node detail fetch error: %s", r)
                continue
            nodes_out.append(cast(dict[str, Any], r))

        return nodes_out

    def _unwrap_params(self, p: Any) -> tuple[dict[str, Any], str | None]:
        if not isinstance(p, dict):
            return {}, None
        if len(p) == 1:
            key = next(iter(p.keys()))
            only_val = p[key]
            if isinstance(only_val, dict):
                return only_val, key
        return p, None

    async def _fetch_node_details(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            nodeid = item.get("nodeid") or item.get("id") or item.get("node_id")
            name = item.get("name") or item.get("Name") or nodeid
        else:
            nodeid = str(item)
            name = nodeid

        params: dict[str, Any] = {}
        wrapper_name: str | None = None
        params_meta: dict[str, dict[str, Any]] = {}

        try:
            assert self._client is not None
            p = await self._client.async_get_params(nodeid)

            params, wrapper_name = self._unwrap_params(p)
            if wrapper_name:
                self._service_map[str(nodeid)] = wrapper_name
        except RainmakerConnectionError:
            _LOGGER.debug("Failed to fetch params for %s", nodeid)

        if (not name or name == nodeid) and isinstance(params, dict):
            name_from_params = params.get("Name") or params.get("name")
            if name_from_params:
                name = name_from_params

        try:
            assert self._client is not None
            cfg = await self._client.async_get_config(nodeid)
            if isinstance(cfg, dict):
                node_param_map: dict[str, str] = {}
                for device in cfg.get("devices", []) or []:
                    service_name = device.get("name") or device.get("type")
                    for pdef in device.get("params", []) or []:
                        pname = pdef.get("name")
                        if not pname:
                            continue
                        meta: dict[str, Any] = {}
                        props = pdef.get("properties") or []
                        if props:
                            meta["properties"] = props
                        data_type = pdef.get("data_type")
                        if data_type:
                            meta["data_type"] = data_type
                        bounds = pdef.get("bounds") or {}
                        if isinstance(bounds, dict):
                            if "min" in bounds:
                                meta["min"] = bounds.get("min")
                            if "max" in bounds:
                                meta["max"] = bounds.get("max")
                            if "step" in bounds:
                                meta["step"] = bounds.get("step")
                        ui_type = pdef.get("ui_type")
                        if ui_type:
                            meta["ui_type"] = ui_type
                        options = pdef.get("options") or pdef.get("choices")
                        if options:
                            meta["options"] = options
                        params_meta[pname] = meta
                        if service_name:
                            node_param_map[pname] = service_name
                if node_param_map:
                    self._param_service_map[str(nodeid)] = node_param_map
        except RainmakerConnectionError:
            _LOGGER.debug("Failed to fetch config for %s", nodeid)

        return {
            "nodeid": str(nodeid),
            "name": name,
            "params": params,
            "params_meta": params_meta,
        }

    async def async_set_param(self, nodeid: str, param: str, value: Any) -> None:
        if not self._connected:
            raise RainmakerConnectionError("Not connected")

        node_map = self._param_service_map.get(str(nodeid), {})
        service_name = node_map.get(param)
        if service_name:
            payload = {service_name: {param: value}}
        else:
            wrapper = self._service_map.get(str(nodeid))
            if wrapper:
                payload = {wrapper: {param: value}}
            else:
                payload = {param: value}

        batch = [{"node_id": nodeid, "payload": payload}]
        try:
            assert self._client is not None
            result = await self._client.async_set_params(batch)
        except Exception as err:
            _LOGGER.debug("Failed to set param via rainmaker client: %s", err)
            raise RainmakerError("Failed to set param") from err

        if isinstance(result, list):
            for res in result:
                if res.get("node_id") == nodeid and res.get("status") != "success":
                    raise RainmakerError(f"Failed to set param: {res}")

    @property
    def is_connected(self) -> bool:
        return bool(self._connected)
