"""Config flow for the Bamartech integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_PASSWORD, CONF_USERNAME, DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BamartechConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Bamartech configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step shown in the HA UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]

            # Each username maps to exactly one integration entry.
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            # TODO: validate credentials before accepting the entry, e.g.:
            #
            #   try:
            #       await validate_credentials(self.hass, username, user_input[CONF_PASSWORD])
            #   except CannotConnectError:
            #       errors["base"] = "cannot_connect"
            #   except InvalidAuthError:
            #       errors["base"] = "invalid_auth"
            #   except Exception:
            #       _LOGGER.exception("Unexpected error during validation")
            #       errors["base"] = "unknown"
            #
            # If no errors, fall through and create the entry.

            if not errors:
                return self.async_create_entry(
                    title=f"{username}@{DEFAULT_HOST}:{DEFAULT_PORT}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication if the server rejects our credentials."""
        return await self.async_step_user(user_input)
