"""Zehnder Multi Controller integration (custom_component copy for HACS)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Zehnder Multi Controller config entry.

    Creates the API object, data coordinator and forwards platform setups.
    """
    data = entry.data
    host = data.get("host")
    username = data.get("username")
    password = data.get("password")

    # Import API and coordinator lazily to avoid requiring optional
    # dependencies (like `rainmaker-http`) at import time when the
    # config flow UI is loaded
    from .api import RainmakerAPI
    from .coordinator import RainmakerCoordinator

    api = RainmakerAPI(hass, host, username, password)
    try:
        await api.async_connect()
    except Exception as err:
        _LOGGER.debug("Failed to connect to Rainmaker: %s", err)
        raise ConfigEntryNotReady from err

    coordinator = RainmakerCoordinator(hass, api, entry)
    # Fetch initial data so platforms have data when they are first added
    await coordinator.async_config_entry_first_refresh()

    # Store runtime-only references
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
        # Remove runtime references if they exist
        domain_data = hass.data.get(DOMAIN)
        if domain_data and entry.entry_id in domain_data:
            domain_data.pop(entry.entry_id)
    return unload_ok
