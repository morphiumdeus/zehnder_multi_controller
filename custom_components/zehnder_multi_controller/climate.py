from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PARAM_MAPPINGS

"""Climate platform for Zehnder Multi Controller (Rainmaker)."""

_LOGGER = logging.getLogger(__name__)


class _FeatureSet(set):
    def __contains__(self, val: Any) -> bool:  # pragma: no cover - trivial wrapper
        return super().__contains__(val)


class RainmakerClimate(CoordinatorEntity, ClimateEntity):
    def __init__(
        self, coordinator: DataUpdateCoordinator, entry_id: str, node: dict[str, Any]
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node = node
        self._attr_name = node.get("name") or node.get("nodeid")
        self._unique_id = f"{entry_id}_{node.get('nodeid')}_climate"

    @property
    def supported_features(self) -> _FeatureSet:
        return _FeatureSet({ClimateEntityFeature.TARGET_TEMPERATURE})

    @property
    def hvac_mode(self) -> HVACMode | None:
        data = self.coordinator.data or []
        for node in data:
            if node.get("nodeid") == self._node.get("nodeid"):
                params = node.get("params", {})
                mode = params.get("mode")
                if mode == "off":
                    return HVACMode.OFF
                return HVACMode.HEAT
        return None

    @property
    def target_temperature(self) -> float | None:
        data = self.coordinator.data or []
        for node in data:
            if node.get("nodeid") == self._node.get("nodeid"):
                params = node.get("params", {})
                return params.get("temperature")
        return None

    @property
    def device_info(self) -> dict:
        nodeid = self._node.get("nodeid")
        return DeviceInfo(
            identifiers={(DOMAIN, nodeid)},
            name=self._node.get("name") or nodeid,
            manufacturer="ESP RainMaker",
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return

        try:
            await self.hass.data[DOMAIN][self._entry_id][
                "coordinator"
            ].api.async_set_param(self._node.get("nodeid"), "temperature", temp)
        except Exception:  # pragma: no cover - surface errors to logs
            _LOGGER.exception(
                "Error setting temperature %s on node %s", temp, self._node
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
        _LOGGER.debug("No entry data for %s, skipping climate setup", entry.entry_id)
        return

    coordinator: DataUpdateCoordinator = entry_data["coordinator"]

    entities: list[RainmakerClimate] = []
    for node in coordinator.data or []:
        params = node.get("params", {})
        # Heuristic: nodes with 'temperature' param map to climate
        if "temperature" in params:
            entities.append(RainmakerClimate(coordinator, entry.entry_id, node))

    async_add_entities(entities, True)


"""Climate platform for Zehnder Multi Controller (Rainmaker)."""

from __future__ import annotations

from typing import Any
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
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


class _FeatureSet(int):
    def __new__(cls, flag_value: int | ClimateEntityFeature) -> "_FeatureSet":
        value = int(flag_value)
        obj = int.__new__(cls, value)
        obj._flag = ClimateEntityFeature(value)
        return obj

    def __contains__(self, item: object) -> bool:
        return isinstance(item, ClimateEntityFeature) and bool(self._flag & item)

    def __iter__(self):
        for feat in ClimateEntityFeature:
            if self._flag & feat:
                yield feat

    def __repr__(self) -> str:  # pragma: no cover - simple repr
        return f"_FeatureSet({int(self)})"


class ZehnderClimate(CoordinatorEntity, ClimateEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        node: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._node = node
        self._nodeid = str(node.get("nodeid"))
        self._attr_name = node.get("name") or self._nodeid

        try:
            self._attr_temperature_unit = coordinator.hass.config.units.temperature_unit
        except AttributeError:
            self._attr_temperature_unit = None

        self._unique_id = f"{entry_id}_{self._nodeid}_climate"
        _LOGGER.debug(
            "Creating ZehnderClimate for node %s (%s)", self._nodeid, self._attr_name
        )

        self._initial_params = dict(node.get("params", {}) or {})
        self._initial_params_meta = dict(node.get("params_meta", {}) or {})

        self._attr_supported_features = self.get_supported_features()

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._nodeid)},
            name=self._attr_name,
            manufacturer="ESP RainMaker",
        )

    @property
    def available(self) -> bool:
        return bool(getattr(self.coordinator.api, "is_connected", False))

    @property
    def current_temperature(self) -> float | None:
        data = self.coordinator.data or []
        for n in data:
            if n.get("nodeid") == self._nodeid:
                params = n.get("params", {})
                for k, v in params.items():
                    if k.lower() == "temp":
                        return v
        return None

    @property
    def target_temperature(self) -> float | None:
        data = self.coordinator.data or []
        for n in data:
            if n.get("nodeid") == self._nodeid:
                params = n.get("params", {})
                for k, v in params.items():
                    if k.lower() == "temp_setpoint":
                        return v
        return None

    @property
    def hvac_modes(self) -> list[str]:
        return [HVACMode.HEAT.value, HVACMode.COOL.value, HVACMode.OFF.value]

    @property
    def hvac_mode(self) -> str | None:
        data = self.coordinator.data or []
        for n in data:
            if n.get("nodeid") == self._nodeid:
                params = n.get("params", {}) or {}
                season = None
                for k, v in params.items():
                    if k.lower() == "season":
                        season = v
                        break
                enabled = None
                for k, v in params.items():
                    if k.lower() == "radiant_enabled":
                        enabled = v
                        break
                if not enabled:
                    return HVACMode.OFF.value
                if season == 1:
                    return HVACMode.HEAT.value
                if season == 2:
                    return HVACMode.COOL.value
        return None

    def get_supported_features(self) -> _FeatureSet:
        features_flag = ClimateEntityFeature(0)
        params = {}
        params_meta = {}

        for n in self.coordinator.data or []:
            if n.get("nodeid") == self._nodeid:
                params = n.get("params", {}) or {}
                params_meta = n.get("params_meta", {}) or {}

                has_temp_setpoint = "temp_setpoint" in params or (
                    "temp_setpoint" in params_meta
                    and "properties" in params_meta["temp_setpoint"]
                    and "write" in params_meta["temp_setpoint"]["properties"]
                )
                if has_temp_setpoint:
                    features_flag |= ClimateEntityFeature.TARGET_TEMPERATURE

                has_fan = "fan_speed" in params or (
                    "fan_speed" in params_meta
                    and "properties" in params_meta["fan_speed"]
                    and "write" in params_meta["fan_speed"]["properties"]
                )
                if has_fan:
                    features_flag |= ClimateEntityFeature.FAN_MODE

        _LOGGER.debug(
            "ZehnderClimate(%s) params keys=%s params_meta_keys=%s -> features=%s",
            self._nodeid,
            list(params.keys()),
            list(params_meta.keys()),
            features_flag,
        )

        return _FeatureSet(features_flag)

    def _handle_coordinator_update(self) -> None:
        try:
            self._attr_supported_features = self.get_supported_features()
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception(
                "Failed to update supported features for %s", self._nodeid
            )
        super()._handle_coordinator_update()

    @property
    def fan_modes(self) -> list[str] | None:
        return ["level_0", "level_1", "level_2", "level_3"]

    @property
    def fan_mode(self) -> str | None:
        data = self.coordinator.data or []
        for n in data:
            if n.get("nodeid") == self._nodeid:
                params = n.get("params", {}) or {}
                val = None
                for k, v in params.items():
                    if k.lower() == "fan_speed":
                        val = v
                        break
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
                self._nodeid, "temp_setpoint", temperature
            )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set temperature on %s", self._nodeid)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        try:
            if hvac_mode == HVACMode.OFF.value:
                await self.coordinator.api.async_set_param(
                    self._nodeid, "radiant_enabled", False
                )
            elif hvac_mode == HVACMode.HEAT.value:
                await self.coordinator.api.async_set_param(self._nodeid, "season", 1)
                await self.coordinator.api.async_set_param(
                    self._nodeid, "radiant_enabled", True
                )
            elif hvac_mode == HVACMode.COOL.value:
                await self.coordinator.api.async_set_param(self._nodeid, "season", 2)
                await self.coordinator.api.async_set_param(
                    self._nodeid, "radiant_enabled", True
                )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set hvac mode on %s", self._nodeid)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            if not fan_mode.startswith("level_"):
                return
            level = int(fan_mode.split("_", 1)[1])
            await self.coordinator.api.async_set_param(
                self._nodeid, "fan_speed", int(level)
            )
            await self.coordinator.async_request_refresh()
        except Exception:  # pragma: no cover - runtime dependent
            _LOGGER.exception("Failed to set fan mode on %s", self._nodeid)


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
    for node in coordinator.data or []:
        params = node.get("params", {})
        if "temp" not in params:
            continue

        nodeid = str(node.get("nodeid"))
        unique_id = f"{entry.entry_id}_{nodeid}_climate"

        if registry.async_get_entity_id("climate", DOMAIN, unique_id) is not None:
            _LOGGER.debug(
                "Skipping climate entity for node %s because unique_id %s is already registered",
                nodeid,
                unique_id,
            )
            continue

        entities.append(ZehnderClimate(coordinator, entry.entry_id, node))

    _LOGGER.debug("Adding %s climate entities", len(entities))
    async_add_entities(entities, True)
