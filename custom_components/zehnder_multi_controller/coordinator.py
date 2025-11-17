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

    def __init__(
        self, hass: HomeAssistant, api: RainmakerAPI, entry: object | None = None
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="zehnder_multi_controller",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.entry = entry

    async def _ensure_connected(self):
        # Ensure API is connected
        if not getattr(self.api, "is_connected", False):
            _LOGGER.debug("API not connected, attempting reconnect")
            await self.api.async_connect()

    async def _async_update_data(self):
        await self._ensure_connected()
        try:
            nodes = await self.api.async_get_nodes()
        except Exception as err:
            raise UpdateFailed(err) from err

        if not ("nodes" in nodes and "node_details" in nodes):
            raise UpdateFailed(f"API response not in the excepted format: {nodes}")

        nodes_dict = {}
        for nd in nodes["node_details"]:
            node_id = nd["id"]
            config_params = nd["config"]["devices"][0]["params"]
            param_vals = nd["params"]["multicontrol"]
            transformed_params = {}
            for param, meta in config_params.items():
                transformed_params[param] = meta.copy()
                transformed_params[param]["value"] = param_vals.get(param)
            nodes_dict[node_id] = transformed_params
        return nodes_dict
