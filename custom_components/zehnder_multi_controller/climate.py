from __future__ import annotations

from typing import Any
import logging
from functools import cached_property

from homeassistant.components.climate import ClimateEntity, HVACMode, ClimateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZehnderClimate(CoordinatorEntity, ClimateEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        node_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node_id = node_id
        self._attr_name = node_id
        self._unique_id = f"{entry_id}_{node_id}_climate"

        try:
            self._attr_temperature_unit = coordinator.hass.config.units.temperature_unit
        except AttributeError:
            self._attr_temperature_unit = "°C"

        _LOGGER.debug(
            "Creating ZehnderClimate for node %s", node_id
        )

        self._attr_supported_features = self.get_supported_features()

    @cached_property
    def unique_id(self) -> str | None:
        return self._unique_id

    @cached_property
    def name(self) -> str | None:
        return self._attr_name

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._node_id)},
            name=self._attr_name,
            manufacturer="ESP RainMaker",
        )

    @cached_property
    def current_temperature(self) -> float | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        for param, meta in node_data.items():
            if param.lower() == "temp":
                return meta.get("value")
        return None

    @cached_property
    def target_temperature(self) -> float | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        for param, meta in node_data.items():
            if param.lower() == "temp_setpoint":
                return meta.get("value")
        return None

    @cached_property
    def hvac_modes(self) -> list[HVACMode]:
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @cached_property
    def hvac_mode(self) -> HVACMode | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        season = None
        enabled = None
        for param, meta in node_data.items():
            if param.lower() == "season":
                season = meta.get("value")
            elif param.lower() == "radiant_enabled":
                enabled = meta.get("value")
        if not enabled:
            return HVACMode.OFF
        if season == 1:
            return HVACMode.HEAT
        if season == 2:
            return HVACMode.COOL
        return None

    def get_supported_features(self) -> ClimateEntityFeature:
        features_flag = ClimateEntityFeature(0)
        node_data = self.coordinator.data.get(self._node_id, {})

        has_temp_setpoint = "temp_setpoint" in node_data and "write" in node_data["temp_setpoint"].get("properties", [])
        if has_temp_setpoint:
            features_flag |= ClimateEntityFeature.TARGET_TEMPERATURE

        has_fan = "fan_speed" in node_data and "write" in node_data["fan_speed"].get("properties", [])
        if has_fan:
            features_flag |= ClimateEntityFeature.FAN_MODE

        _LOGGER.debug(
            "ZehnderClimate(%s) params keys=%s -> features=%s",
            self._node_id,
            list(node_data.keys()),
            features_flag,
        )

        return features_flag

    def _handle_coordinator_update(self) -> None:
        try:
            self._attr_supported_features = self.get_supported_features()
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception(
                "Failed to update supported features for %s", self._node_id
            )
        super()._handle_coordinator_update()

    @cached_property
    def fan_modes(self) -> list[str] | None:
        return ["level_0", "level_1", "level_2", "level_3"]

    @cached_property
    def fan_mode(self) -> str | None:
        node_data = self.coordinator.data.get(self._node_id, {})
        for param, meta in node_data.items():
            if param.lower() == "fan_speed":
                val = meta.get("value")
                if val is None:
                    return None
                return f"level_{int(val)}"
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        try:
            await self.coordinator.api.async_set_param(
                self._node_id, "temp_setpoint", temperature
            )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set temperature on %s", self._node_id)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        try:
            if hvac_mode == HVACMode.OFF.value:
                await self.coordinator.api.async_set_param(
                    self._node_id, "radiant_enabled", False
                )
            elif hvac_mode == HVACMode.HEAT.value:
                await self.coordinator.api.async_set_param(self._node_id, "season", 1)
                await self.coordinator.api.async_set_param(
                    self._node_id, "radiant_enabled", True
                )
            elif hvac_mode == HVACMode.COOL.value:
                await self.coordinator.api.async_set_param(self._node_id, "season", 2)
                await self.coordinator.api.async_set_param(
                    self._node_id, "radiant_enabled", True
                )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set hvac mode on %s", self._node_id)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            if not fan_mode.startswith("level_"):
                return
            level = int(fan_mode.split("_", 1)[1])
            await self.coordinator.api.async_set_param(
                self._node_id, "fan_speed", int(level)
            )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set fan mode on %s", self._node_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not entry_data:
        _LOGGER.debug(
            "No entry data found for %s, aborting climate setup", entry.entry_id
        )
        return
    coordinator = entry_data["coordinator"]

    entities: list[ZehnderClimate] = []
    registry = er.async_get(hass)
    for node_id, params in coordinator.data.items():
        if "temp" not in params:
            continue

        unique_id = f"{entry.entry_id}_{node_id}_climate"

        if registry.async_get_entity_id("climate", DOMAIN, unique_id) is not None:
            _LOGGER.debug(
                "Skipping climate entity for node %s because unique_id %s is already registered",
                node_id,
                unique_id,
            )
            continue

        entities.append(ZehnderClimate(coordinator, entry.entry_id, node_id))

    _LOGGER.debug("Adding %s climate entities", len(entities))
    async_add_entities(entities, True)
