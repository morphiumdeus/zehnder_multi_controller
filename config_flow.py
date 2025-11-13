"""Config flow for Zehnder Multi Controller (Rainmaker)."""

from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .api import RainmakerAPI

_LOGGER = logging.getLogger(__name__)


class ZehnderFlowHandler(config_entries.ConfigFlow, domain="zehnder_multi_controller"):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = RainmakerAPI(
                self.hass,
                user_input.get("host"),
                user_input.get("username"),
                user_input.get("password"),
            )
            try:
                await api.async_connect()
            except Exception:  # pragma: no cover - bubble up for UI
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get("host"), data=user_input
                )

        return self.async_show_form(step_id="user", data_schema={}, errors=errors)


"""Config flow for the Zehnder Multi Controller integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .api import RainmakerAPI, RainmakerConnectionError, RainmakerAuthError

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
    try:
        await api.async_connect()
    except RainmakerConnectionError as err:
        raise CannotConnect from err
    except RainmakerAuthError as err:
        raise InvalidAuth from err
    except Exception as err:
        if isinstance(err, (CannotConnect, InvalidAuth)):
            raise
        raise InvalidAuth from err

    return {"title": "Name of the device"}


class ZehnderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zehnder Multi Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                host = user_input.get(CONF_HOST)
                if host:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
