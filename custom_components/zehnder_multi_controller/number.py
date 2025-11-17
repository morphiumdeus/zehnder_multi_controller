from __future__ import annotations

from typing import Any
import logging
from functools import cached_property

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

"""Number platform for Zehnder Multi Controller (Rainmaker)."""


_LOGGER = logging.getLogger(__name__)


class RainmakerParamNumber(CoordinatorEntity, NumberEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        node_id: str,
        param: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node_id = node_id
        self._param = param
        self._attr_name = f"{node_id} {param}"
        self._unique_id = f"{entry_id}_{node_id}_{param}"
        self._attr_min_value = None
        self._attr_max_value = None
        self._attr_step = None

    @cached_property
    def name(self) -> str | None:
        return self._attr_name

    @cached_property
    def unique_id(self) -> str | None:
        return self._unique_id

    @cached_property
    def native_value(self) -> float | None:
        params = self.coordinator.data.get(self._node_id, {})
        return params.get(self._param, {}).get("value")

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._node_id)},
            name=self._node_id,
            manufacturer="ESP RainMaker",
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(lambda: None)
        try:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].api.async_set_param(self._node_id, self._param, value)
        except Exception:  # pragma: no cover - surface errors to logs
            _LOGGER.exception(
                "Error setting param %s on node %s", self._param, self._node_id
            )
        finally:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        _LOGGER.debug("No entry data for %s, skipping number setup", entry.entry_id)
        return

    coordinator: DataUpdateCoordinator = entry_data["coordinator"]

    entities: list[RainmakerParamNumber] = []
    for node_id, params in coordinator.data.items():
        for param, meta in params.items():
            if "write" in meta.get("properties", []) and meta.get("data_type") != "bool":
                entity = RainmakerParamNumber(coordinator, entry.entry_id, node_id, param)

                # populate number ranges from metadata if present
                bounds = meta.get("bounds", {})
                if isinstance(bounds, dict):
                    entity._attr_min_value = bounds.get("min")
                    entity._attr_max_value = bounds.get("max")
                    entity._attr_step = bounds.get("step")

                entities.append(entity)

    async_add_entities(entities, True)
