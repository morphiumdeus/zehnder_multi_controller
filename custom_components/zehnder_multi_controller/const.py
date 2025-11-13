from __future__ import annotations

from datetime import timedelta
from typing import Any
from homeassistant.const import Platform

"""Constants for Zehnder Multi Controller integration.

This module intentionally does not contain hard-coded parameter name
mappings. Entity detection must come solely from the device
`get_node_config` metadata and runtime values.
"""


DOMAIN = "zehnder_multi_controller"
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Default polling interval in seconds
DEFAULT_SCAN_INTERVAL = 30


def _meta_has_write(meta: dict | None) -> bool:
    """Return True if metadata indicates a writable parameter."""
    if not meta or not isinstance(meta, dict):
        return False
    props = meta.get("properties")
    # Some devices use a list of strings like ['read', 'write']
    if isinstance(props, (list, tuple)):
        if "write" in props:
            return True
    return False


def detect_param_info(
    param: str, value: object | None, meta: dict | None
) -> dict[str, Any]:
    """Detect the best Home Assistant entity info for a parameter.

    Returns a dict containing at least `entity` with one of `sensor`,
    `number`, or `switch`. Additional keys discovered in the device
    metadata (label, unit, device_class, bounds -> properties) are
    returned when present. This function does NOT assume any other
    parameter names beyond what the device reports.
    """
    # param name (lowercased) is intentionally not used for detection;
    # we rely only on metadata and the runtime value
    _pname = param.lower()

    # Prefer metadata-driven detection. The Zehnder JSON uses keys like
    # `data_type`, `properties` (list), `ui_type`, and `bounds`.
    if meta and isinstance(meta, dict):
        mtype = meta.get("data_type") or meta.get("type")

        if mtype == "bool":
            entity = "switch"
        # Numeric types
        elif mtype in ("int", "float"):
            entity = "number" if _meta_has_write(meta) else "sensor"
        # Strings / arrays -> sensor by default (could be select if options exist)
        else:
            entity = "sensor"

    elif isinstance(value, bool):
        entity = "switch"
    elif isinstance(value, (int, float)):
        entity = "number"
    else:
        entity = "sensor"

    # Start result with detected entity. Only use metadata for
    # supplementary information (label, unit, device_class, properties).
    result: dict[str, Any] = {"entity": entity}

    # If metadata contains a unit or device_class, prefer it
    if meta and isinstance(meta, dict):
        if "name" in meta and meta.get("name"):
            result["label"] = meta.get("name")
        if "bounds" in meta and isinstance(meta.get("bounds"), dict):
            result["properties"] = meta.get("bounds")

        if entity in ["number", "sensor"]:
            if "temp" in meta.get("name").lower():
                result["properties"]["unit"] = "°C"
                result["properties"]["device_class"] = "temperature"

    return result
