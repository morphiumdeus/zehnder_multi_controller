"""Number platform for Zehnder Multi Controller (Rainmaker)."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PARAM_MAPPINGS

_LOGGER = logging.getLogger(__name__)


class RainmakerParamNumber(CoordinatorEntity, NumberEntity):
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
        self._mapping = PARAM_MAPPINGS.get(param.lower(), {})

        props = self._mapping.get("properties", {})
        self._attr_min_value = props.get("min")
        self._attr_max_value = props.get("max")
        self._attr_step = props.get("step")

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
    def device_info(self) -> dict:
        nodeid = self._node.get("nodeid")
        return DeviceInfo(
            identifiers={(DOMAIN, nodeid)},
            name=self._node.get("name") or nodeid,
            manufacturer="ESP RainMaker",
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(lambda: None)
        try:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].api.async_set_param(self._node.get("nodeid"), self._param, value)
        except Exception:  # pragma: no cover - surface errors to logs
            _LOGGER.exception(
                "Error setting param %s on node %s", self._param, self._node
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
    for node in coordinator.data or []:
        params = node.get("params", {})
        params_meta = node.get("params_meta", {})
        for param, value in params.items():
            mapping = PARAM_MAPPINGS.get(param.lower()) or {}
            if mapping.get("entity") != "number":
                continue

            meta = params_meta.get(param, {})
            props = meta.get("properties", []) or []
            if props and "read" not in props:
                continue

            entities.append(
                RainmakerParamNumber(coordinator, entry.entry_id, node, param)
            )

    async_add_entities(entities, True)
