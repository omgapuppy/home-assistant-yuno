"""Config flow for Yuno Energy."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASIC_AUTHORIZATION,
    CONF_BASIC_PASSWORD,
    CONF_BASIC_USERNAME,
    CONF_ENCRYPTED_EMAIL,
    CONF_ENCRYPTED_PASSWORD,
    CONF_LOGIN_SIGNATURE,
    CONF_ORIGIN_ID,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_USAGE_SIGNATURE,
    DEFAULT_ORIGIN_ID,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .yuno_api.client import AiohttpSessionAdapter, AuthConfig, YunoApiClient, YunoApiError

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ENCRYPTED_EMAIL,
                default=defaults.get(CONF_ENCRYPTED_EMAIL, ""),
            ): str,
            vol.Required(
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
            vol.Required(
                CONF_LOGIN_SIGNATURE,
                default=defaults.get(CONF_LOGIN_SIGNATURE, ""),
            ): str,
            vol.Required(
                CONF_USAGE_SIGNATURE,
                default=defaults.get(CONF_USAGE_SIGNATURE, ""),
            ): str,
            vol.Required(
                CONF_SCAN_INTERVAL_MINUTES,
                default=defaults.get(CONF_SCAN_INTERVAL_MINUTES, 360),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)),
        }
    )


def auth_config_from_data(data: dict[str, Any]) -> AuthConfig:
    """Build AuthConfig from config entry data."""
    basic_authorization = str(data.get(CONF_BASIC_AUTHORIZATION) or "").strip()
    if basic_authorization:
        if not basic_authorization.lower().startswith("basic "):
            basic_authorization = f"Basic {basic_authorization}"
        return AuthConfig(
            encrypted_email=str(data[CONF_ENCRYPTED_EMAIL]),
            encrypted_password=str(data[CONF_ENCRYPTED_PASSWORD]),
            basic_authorization=basic_authorization,
            origin_id=str(data[CONF_ORIGIN_ID]),
            login_signature=str(data[CONF_LOGIN_SIGNATURE]),
            usage_signature=str(data[CONF_USAGE_SIGNATURE]),
        )
    return AuthConfig.from_basic_credentials(
        encrypted_email=str(data[CONF_ENCRYPTED_EMAIL]),
        encrypted_password=str(data[CONF_ENCRYPTED_PASSWORD]),
        basic_username=str(data[CONF_BASIC_USERNAME]),
        basic_password=str(data[CONF_BASIC_PASSWORD]),
        origin_id=str(data[CONF_ORIGIN_ID]),
        login_signature=str(data[CONF_LOGIN_SIGNATURE]),
        usage_signature=str(data[CONF_USAGE_SIGNATURE]),
    )


class YunoEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Yuno Energy."""

    VERSION = 1
    _reauth_entry_id: str | None = None

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
        if user_input is not None:
            errors = await self._validate_input(user_input)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title="Yuno Energy", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication."""
        entry_id = self.context.get("entry_id")
        self._reauth_entry_id = entry_id if isinstance(entry_id, str) else None
        return await self.async_step_reauth_confirm(entry_data)

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Update credentials during reauth."""
        if self._reauth_entry_id is None:
            return self.async_abort(reason="unknown")
        entry = self.hass.config_entries.async_get_entry(self._reauth_entry_id)
        defaults = dict(entry.data) if entry else {}
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate_input(user_input)
            if not errors and entry is not None:
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_user_schema(user_input or defaults),
            errors=errors,
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
        if user_input is not None:
            errors = await self._validate_input(user_input)
            if not errors and entry is not None:
                return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or defaults),
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        if not user_input.get(CONF_BASIC_AUTHORIZATION) and not (
            user_input.get(CONF_BASIC_USERNAME) and user_input.get(CONF_BASIC_PASSWORD)
        ):
            return {"base": "missing_basic_auth"}
        client = YunoApiClient(
            session=AiohttpSessionAdapter(async_get_clientsession(self.hass)),
        )
        try:
            await client.login(auth_config_from_data(user_input))
        except (YunoApiError, TimeoutError, OSError):
            _LOGGER.debug("Yuno login validation failed", exc_info=True)
            return {"base": "cannot_connect"}
        return {}


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
