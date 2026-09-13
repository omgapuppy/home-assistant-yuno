"""Config flow for Yuno Energy."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .config_data import (
    account_data_from_input,
    auth_config_from_data,
    has_basic_auth,
    has_login_credentials,
    session_token_from_data,
)
from .const import (
    AUTH_MODE_ACCOUNT,
    CONF_AUTH_MODE,
    CONF_BASIC_AUTHORIZATION,
    CONF_BASIC_PASSWORD,
    CONF_BASIC_USERNAME,
    CONF_EMAIL,
    CONF_ENCRYPTED_EMAIL,
    CONF_ENCRYPTED_PASSWORD,
    CONF_LOGIN_SIGNATURE,
    CONF_ORIGIN_ID,
    CONF_PASSWORD,
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


def _manual_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
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


def _account_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_SCAN_INTERVAL_MINUTES, default=defaults.get(CONF_SCAN_INTERVAL_MINUTES, 360)
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)),
        }
    )


class YunoEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Set up account login or keep using existing manually supplied values."""

    VERSION = 1

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
        """Choose how to sign in."""
        return self.async_show_menu(step_id="user", menu_options=["account", "manual"])

    async def async_step_account(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Sign in with the owner's email and password."""
        return await self._async_credentials_form("account", True, user_input)

    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Use existing session tokens or generated/captured login fields."""
        return await self._async_credentials_form("manual", False, user_input)

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Show a form; do not immediately retry the rejected saved credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Replace credentials while preserving the config entry and statistics."""
        entry = self._existing_entry()
        if entry is None:
            return self.async_abort(reason="unknown")
        account_mode = entry.data.get(CONF_AUTH_MODE) == AUTH_MODE_ACCOUNT
        step_id = "reauth_confirm" if account_mode else "reauth_manual"
        return await self._async_credentials_form(step_id, account_mode, user_input)

    async def async_step_reauth_manual(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Replace manually supplied credentials."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow an existing entry to switch to account login."""
        if self._existing_entry() is None:
            return self.async_abort(reason="unknown")
        return self.async_show_menu(step_id="reconfigure", menu_options=["account", "manual"])

    def _existing_entry(self) -> config_entries.ConfigEntry | None:
        entry_id = self.context.get("entry_id")
        return (
            self.hass.config_entries.async_get_entry(entry_id)
            if isinstance(entry_id, str)
            else None
        )

    async def _async_credentials_form(
        self,
        step_id: str,
        account_mode: bool,
        user_input: dict[str, Any] | None,
    ) -> config_entries.ConfigFlowResult:
        entry = self._existing_entry()
        defaults = dict(entry.data) if entry else {}
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                data = account_data_from_input(user_input) if account_mode else dict(user_input)
            except ValueError:
                errors = {"base": "invalid_credentials"}
            else:
                errors, placeholders = await self._validate_input(data)
                if not errors:
                    if self.context.get("source") in {"reauth", "reconfigure"}:
                        if entry is None:
                            return self.async_abort(reason="unknown")
                        reason = (
                            "reauth_successful"
                            if self.context.get("source") == "reauth"
                            else "reconfigure_successful"
                        )
                        return self.async_update_reload_and_abort(entry, data=data, reason=reason)
                    await self.async_set_unique_id(DOMAIN)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Yuno Energy", data=data)
        schema = _account_schema if account_mode else _manual_schema
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema(user_input or defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _validate_input(
        self,
        data: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, str]]:
        if not has_basic_auth(data):
            return {"base": "missing_basic_auth"}, {}
        if not session_token_from_data(data) and not has_login_credentials(data):
            return {"base": "missing_login_or_session"}, {}
        client = YunoApiClient(session=AiohttpSessionAdapter(async_get_clientsession(self.hass)))
        try:
            _, token = await client.get_authenticated_usage(
                auth_config_from_data(data),
                session_token=session_token_from_data(data),
                allow_login=has_login_credentials(data),
            )
        except (YunoApiError, TimeoutError, OSError) as err:
            detail = diagnostic_message_from_exception(err)
            _LOGGER.warning("Yuno validation failed: %s", detail)
            return {"base": error_key_from_exception(err)}, {"detail": detail}
        data[CONF_SESSION_TOKEN] = token
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
