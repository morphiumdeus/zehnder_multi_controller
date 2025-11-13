"""Constants for Zehnder Multi Controller integration."""

DOMAIN = "zehnder_multi_controller"

# Basic mapping for some known params to HA entity types and units
PARAM_MAPPINGS = {
    "temperature": {"entity": "climate", "unit": "°C"},
    "setpoint": {"entity": "number", "unit": "°C"},
    "power": {"entity": "switch"},
    "fan": {"entity": "number"},
}
"""Constants for the Zehnder Multi Controller (Rainmaker) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zehnder_multi_controller"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.CLIMATE,
]

# Default polling interval in seconds
DEFAULT_SCAN_INTERVAL = 30

PARAM_MAPPINGS: dict[str, dict[str, str]] = {
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
