"""Config flow for Yuno Energy."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_data import (
    auth_config_from_data,
    has_basic_auth,
    has_login_credentials,
    session_token_from_data,
)
from .const import (
    CONF_BASIC_AUTHORIZATION,
    CONF_BASIC_PASSWORD,
    CONF_BASIC_USERNAME,
    CONF_ENCRYPTED_EMAIL,
    CONF_ENCRYPTED_PASSWORD,
    CONF_LOGIN_SIGNATURE,
    CONF_ORIGIN_ID,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_SESSION_TOKEN,
    CONF_USAGE_SIGNATURE,
    DEFAULT_ORIGIN_ID,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .flow_errors import diagnostic_message_from_exception, error_key_from_exception
from .yuno_api.client import AiohttpSessionAdapter, YunoApiClient, YunoApiError

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_USAGE_SIGNATURE,
                default=defaults.get(CONF_USAGE_SIGNATURE, ""),
            ): str,
            vol.Optional(
                CONF_SESSION_TOKEN,
                default=defaults.get(CONF_SESSION_TOKEN, ""),
            ): str,
            vol.Optional(
                CONF_ENCRYPTED_EMAIL,
                default=defaults.get(CONF_ENCRYPTED_EMAIL, ""),
            ): str,
            vol.Optional(
                CONF_ENCRYPTED_PASSWORD,
                default=defaults.get(CONF_ENCRYPTED_PASSWORD, ""),
            ): str,
            vol.Optional(
                CONF_BASIC_AUTHORIZATION,
                default=defaults.get(CONF_BASIC_AUTHORIZATION, ""),
            ): str,
            vol.Optional(
                CONF_BASIC_USERNAME,
                default=defaults.get(CONF_BASIC_USERNAME, ""),
            ): str,
            vol.Optional(
                CONF_BASIC_PASSWORD,
                default=defaults.get(CONF_BASIC_PASSWORD, ""),
            ): str,
            vol.Required(
                CONF_ORIGIN_ID,
                default=defaults.get(CONF_ORIGIN_ID, DEFAULT_ORIGIN_ID),
            ): str,
            vol.Optional(
                CONF_LOGIN_SIGNATURE,
                default=defaults.get(CONF_LOGIN_SIGNATURE, ""),
            ): str,
            vol.Required(
                CONF_SCAN_INTERVAL_MINUTES,
                default=defaults.get(CONF_SCAN_INTERVAL_MINUTES, 360),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)),
        }
    )


class YunoEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Yuno Energy."""

    VERSION = 1
    __yuno_reauth_entry_id: str | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> YunoEnergyOptionsFlow:
        """Return the options flow."""
        return YunoEnergyOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create a Yuno Energy config entry."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, description_placeholders = await self._validate_input(user_input)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title="Yuno Energy", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication."""
        entry_id = self.context.get("entry_id")
        self.__yuno_reauth_entry_id = entry_id if isinstance(entry_id, str) else None
        return await self.async_step_reauth_confirm(entry_data)

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Update credentials during reauth."""
        if self.__yuno_reauth_entry_id is None:
            return self.async_abort(reason="unknown")
        entry = self.hass.config_entries.async_get_entry(self.__yuno_reauth_entry_id)
        defaults = dict(entry.data) if entry else {}
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, description_placeholders = await self._validate_input(user_input)
            if not errors and entry is not None:
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_user_schema(user_input or defaults),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow reconfiguration of static headers and polling."""
        entry_id = self.context.get("entry_id")
        if not isinstance(entry_id, str):
            return self.async_abort(reason="unknown")
        entry = self.hass.config_entries.async_get_entry(entry_id)
        defaults = dict(entry.data) if entry else {}
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, description_placeholders = await self._validate_input(user_input)
            if not errors and entry is not None:
                return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or defaults),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _validate_input(
        self,
        user_input: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, str]]:
        if not has_basic_auth(user_input):
            return {"base": "missing_basic_auth"}, {}
        if not session_token_from_data(user_input) and not has_login_credentials(user_input):
            return {"base": "missing_login_or_session"}, {}
        client = YunoApiClient(
            session=AiohttpSessionAdapter(async_get_clientsession(self.hass)),
        )
        try:
            auth = auth_config_from_data(user_input)
            if session_token := session_token_from_data(user_input):
                await client.get_electricity_usage(auth, session_token=session_token)
            else:
                await client.login(auth)
        except (YunoApiError, TimeoutError, OSError) as err:
            detail = diagnostic_message_from_exception(err)
            _LOGGER.warning("Yuno validation failed: %s", detail)
            _LOGGER.debug("Yuno login validation failed", exc_info=True)
            return {"base": error_key_from_exception(err)}, {"detail": detail}
        return {}, {}


class YunoEnergyOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Yuno Energy."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Update integration options."""
        data = {**self._entry.data, **self._entry.options}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL_MINUTES,
                        default=data.get(CONF_SCAN_INTERVAL_MINUTES, 360),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)),
                }
            ),
        )
