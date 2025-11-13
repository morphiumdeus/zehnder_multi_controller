from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PARAM_MAPPINGS

"""Sensor platform for Zehnder Multi Controller (Rainmaker)."""


_LOGGER = logging.getLogger(__name__)


class RainmakerParamSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        node: dict[str, Any],
        param: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node = node
        self._param = param
        self._attr_name = f"{node.get('name') or node.get('nodeid')} {param}"
        self._unique_id = f"{entry_id}_{node.get('nodeid')}_{param}"
        self._mapping = PARAM_MAPPINGS.get(param.lower())

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or []
        for node in data:
            if node.get("nodeid") == self._node.get("nodeid"):
                params = node.get("params", {})
                return params.get(self._param)
        return None

    @property
    def device_class(self) -> str | None:
        if self._mapping and self._mapping.get("entity") == "sensor":
            return self._mapping.get("device_class")
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._mapping and self._mapping.get("entity") == "sensor":
            return self._mapping.get("unit")
        return None

    @property
    def device_info(self) -> dict:
        nodeid = self._node.get("nodeid")
        return DeviceInfo(
            identifiers={(DOMAIN, nodeid)},
            name=self._node.get("name") or nodeid,
            manufacturer="ESP RainMaker",
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        _LOGGER.debug("No entry data for %s, skipping sensor setup", entry.entry_id)
        return

    coordinator: DataUpdateCoordinator = entry_data["coordinator"]

    entities: list[RainmakerParamSensor] = []
    for node in coordinator.data or []:
        params = node.get("params", {})
        for param, value in params.items():
            if isinstance(value, (dict, list)):
                continue

            mapping = PARAM_MAPPINGS.get(param.lower())
            if mapping and mapping.get("entity") in ("switch", "number"):
                continue

            params_meta = node.get("params_meta", {})
            meta = params_meta.get(param, {})
            props = meta.get("properties", []) or []
            if props and "read" not in props:
                continue

            entities.append(
                RainmakerParamSensor(coordinator, entry.entry_id, node, param)
            )

    async_add_entities(entities, True)
