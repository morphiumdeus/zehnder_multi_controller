from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .api import (
            RainmakerAPI,
            RainmakerConnectionError,
            RainmakerAuthError,
        )


_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "https://api.rainmaker.espressif.com/v1/"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    api = RainmakerAPI(hass, data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
    await api.async_connect()

    return {"title": "Name of the device"}


class ZehnderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zehnder Multi Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step.

        Validate credentials using `validate_input`. Provide specific user-facing
        errors for authentication or connectivity failures and fall back to a
        generic unknown error for anything else.
        """

        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(data_schema=STEP_USER_DATA_SCHEMA, errors=errors)

        try:
            info = await validate_input(self.hass, user_input)
        except RainmakerAuthError:
            errors["base"] = "auth"
        except RainmakerConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected exception during config flow validation")
            errors["base"] = "unknown"
        else:
            # Use a stable, specific unique id (host + username) so multiple
            # accounts pointing to the same host can be distinguished.
            host = (user_input.get(CONF_HOST) or "").rstrip("/")
            username = user_input.get(CONF_USERNAME) or ""
            unique_id = f"{host}|{username}" if username else host
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        # If we reach here, validation failed — redisplay form with errors
        return self.async_show_form(data_schema=STEP_USER_DATA_SCHEMA, errors=errors)
