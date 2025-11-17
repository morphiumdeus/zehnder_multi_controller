from __future__ import annotations

from datetime import timedelta
from typing import Any
from homeassistant.const import Platform

DOMAIN = "zehnder_multi_controller"
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Default polling interval in seconds
DEFAULT_SCAN_INTERVAL = 30