"""Zehnder Multi Controller integration (custom_component copy for HACS)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import RainmakerAPI
from .coordinator import RainmakerCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    api = RainmakerAPI(
        hass,
        entry.data.get("host"),
        entry.data.get("username"),
        entry.data.get("password"),
    )

    try:
        await api.async_connect()
    except Exception as err:  # pragma: no cover - surface connect issues
        raise ConfigEntryNotReady from err

    coordinator: DataUpdateCoordinator = RainmakerCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # forward platforms
    hass.config_entries.async_setup_platforms(
        entry, ["sensor", "switch", "number", "climate"]
    )  # type: ignore[arg-type]

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "switch", "number", "climate"]
    )  # type: ignore[arg-type]
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


"""The Zehnder Multi Controller integration (Rainmaker).

This integration connects to devices exposed by ESP RainMaker and exposes
their parameters as Home Assistant entities (sensors, switches).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import RainmakerAPI
from .const import DOMAIN, PLATFORMS
from .coordinator import RainmakerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Zehnder Multi Controller config entry.

    Creates the API object, data coordinator and forwards platform setups.
    """
    data = entry.data
    host = data.get("host")
    username = data.get("username")
    password = data.get("password")

    api = RainmakerAPI(hass, host, username, password)
    try:
        await api.async_connect()
    except RuntimeError as err:
        _LOGGER.debug("Failed to connect to Rainmaker: %s", err)
        raise ConfigEntryNotReady from err

    coordinator = RainmakerCoordinator(hass, api)
    # Fetch initial data so platforms have data when they are first added
    await coordinator.async_config_entry_first_refresh()

    # Store runtime-only references on the entry (not persisted)
    entry.runtime_data = {}
    entry.runtime_data["api"] = api
    entry.runtime_data["coordinator"] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Remove runtime references if they exist. Guard against cases
        # where setup failed early and hass.data does not contain our
        # domain or the entry id
        domain_data = hass.data.get(DOMAIN)
        if domain_data and entry.entry_id in domain_data:
            domain_data.pop(entry.entry_id)
    return unload_ok
