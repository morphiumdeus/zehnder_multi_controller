from __future__ import annotations

from datetime import timedelta
from homeassistant.const import Platform

"""Constants for Zehnder Multi Controller integration."""


DOMAIN = "zehnder_multi_controller"
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Default polling interval in seconds
DEFAULT_SCAN_INTERVAL = 30

# Basic mapping for some known params to HA entity types and units
PARAM_MAPPINGS: dict[str, dict[str, str]] = {
    "temperature": {"entity": "climate", "unit": "°C"},
    "setpoint": {"entity": "number", "unit": "°C"},
    "power": {"entity": "switch"},
    "fan": {"entity": "number"},
    "temp": {"entity": "sensor", "device_class": "temperature", "unit": "°C"},
    "temp_setpoint": {"entity": "number", "device_class": "temperature", "unit": "°C"},
    "humidity": {"entity": "sensor", "device_class": "humidity", "unit": "%"},
    "fan_speed": {"entity": "sensor", "unit": ""},
    "temperature_setpoint": {
        "entity": "number",
        "device_class": "temperature",
        "unit": "°C",
    },
    "on": {"entity": "switch", "icon": "mdi:power"},
    "is_on": {"entity": "switch", "icon": "mdi:power"},
    "enabled": {"entity": "switch", "icon": "mdi:check"},
    "relay": {"entity": "switch", "icon": "mdi:light-switch"},
}
