from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, detect_param_info

"""Switch platform for Zehnder Multi Controller (Rainmaker)."""

_LOGGER = logging.getLogger(__name__)


class RainmakerParamSwitch(CoordinatorEntity, SwitchEntity):
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
        self._mapping: dict | None = None

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or []
        for node in data:
            if node.get("nodeid") == self._node.get("nodeid"):
                params = node.get("params", {})
                return bool(params.get(self._param))
        return None

    @property
    def device_info(self) -> dict:
        nodeid = self._node.get("nodeid")
        return DeviceInfo(
            identifiers={(DOMAIN, nodeid)},
            name=self._node.get("name") or nodeid,
            manufacturer="ESP RainMaker",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].api.async_set_param(self._node.get("nodeid"), self._param, True)
        except Exception:  # pragma: no cover - surface errors to logs
            _LOGGER.exception("Error turning on %s on node %s", self._param, self._node)
        finally:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].api.async_set_param(self._node.get("nodeid"), self._param, False)
        except Exception:  # pragma: no cover - surface errors to logs
            _LOGGER.exception(
                "Error turning off %s on node %s", self._param, self._node
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
        _LOGGER.debug("No entry data for %s, skipping switch setup", entry.entry_id)
        return

    coordinator: DataUpdateCoordinator = entry_data["coordinator"]

    entities: list[RainmakerParamSwitch] = []
    for node in coordinator.data or []:
        params = node.get("params", {})
        params_meta = node.get("params_meta", {})
        for param, value in params.items():
            meta = params_meta.get(param, {})
            info = detect_param_info(param, value, meta)
            if info.get("entity") != "switch":
                continue

            props = meta.get("properties", []) or []
            if props and "read" not in props:
                continue

            entity = RainmakerParamSwitch(coordinator, entry.entry_id, node, param)
            entity._mapping = info
            entities.append(entity)

    async_add_entities(entities, True)
