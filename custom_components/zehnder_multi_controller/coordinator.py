"""Coordinator for Zehnder Multi Controller (Rainmaker)."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant

from .api import RainmakerAPI

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)


class RainmakerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: RainmakerAPI, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="rainmaker",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self.entry = entry

    async def _async_update_data(self):
        try:
            nodes = await self.api.async_get_nodes()
            return nodes
        except Exception as err:  # pragma: no cover - let upstream handle retries
            raise UpdateFailed from err


"""Coordinator for the Zehnder Multi Controller integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import RainmakerAPI
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class RainmakerCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Rainmaker nodes and params."""

    def __init__(self, hass: HomeAssistant, api: RainmakerAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="zehnder_multi_controller",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            if not getattr(self.api, "is_connected", False):
                _LOGGER.debug("API not connected, attempting reconnect")
                if getattr(self.api, "async_connect", None):
                    await self.api.async_connect()

            try:
                nodes = await self.api.async_get_nodes()
            except Exception as err:  # first attempt failed, try reconnect once
                _LOGGER.debug("First nodes fetch failed: %s; attempting reconnect", err)
                try:
                    await self.api.async_connect()
                    nodes = await self.api.async_get_nodes()
                except Exception as err2:
                    _LOGGER.debug("Reconnect+refetch failed: %s", err2)
                    raise UpdateFailed(err2) from err2

            def _data_complete(nodes_list: list[dict[str, Any]] | None) -> bool:
                if not nodes_list:
                    return False
                for n in nodes_list:
                    if not isinstance(n, dict):
                        return False
                    if not n.get("params"):
                        return False
                return True

            if not _data_complete(nodes):
                _LOGGER.debug("Node data incomplete, attempting a reconnect+refetch")
                try:
                    await self.api.async_connect()
                    nodes2 = await self.api.async_get_nodes()
                    if _data_complete(nodes2):
                        return nodes2
                    _LOGGER.debug("Data still incomplete after reconnect")
                    raise UpdateFailed("Incomplete node data after reconnect")
                except Exception as err3:
                    _LOGGER.debug("Reconnect attempt failed: %s", err3)
                    raise UpdateFailed(err3) from err3

            return nodes
        except Exception as err:
            raise UpdateFailed(err) from err
