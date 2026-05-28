"""Helpers for reading Yuno config entry data."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_BASIC_AUTHORIZATION,
    CONF_BASIC_PASSWORD,
    CONF_BASIC_USERNAME,
    CONF_ENCRYPTED_EMAIL,
    CONF_ENCRYPTED_PASSWORD,
    CONF_LOGIN_SIGNATURE,
    CONF_ORIGIN_ID,
    CONF_SESSION_TOKEN,
    CONF_USAGE_SIGNATURE,
    DEFAULT_ORIGIN_ID,
)
from .yuno_api.client import AuthConfig


def auth_config_from_data(data: dict[str, Any]) -> AuthConfig:
    """Build AuthConfig from config entry data."""
    basic_authorization = _string_value(data, CONF_BASIC_AUTHORIZATION)
    if basic_authorization:
        if not basic_authorization.lower().startswith("basic "):
            basic_authorization = f"Basic {basic_authorization}"
        return AuthConfig(
            encrypted_email=_string_value(data, CONF_ENCRYPTED_EMAIL),
            encrypted_password=_string_value(data, CONF_ENCRYPTED_PASSWORD),
            basic_authorization=basic_authorization,
            origin_id=_string_value(data, CONF_ORIGIN_ID) or DEFAULT_ORIGIN_ID,
            login_signature=_string_value(data, CONF_LOGIN_SIGNATURE),
            usage_signature=_string_value(data, CONF_USAGE_SIGNATURE),
        )
    return AuthConfig.from_basic_credentials(
        encrypted_email=_string_value(data, CONF_ENCRYPTED_EMAIL),
        encrypted_password=_string_value(data, CONF_ENCRYPTED_PASSWORD),
        basic_username=_string_value(data, CONF_BASIC_USERNAME),
        basic_password=_string_value(data, CONF_BASIC_PASSWORD),
        origin_id=_string_value(data, CONF_ORIGIN_ID) or DEFAULT_ORIGIN_ID,
        login_signature=_string_value(data, CONF_LOGIN_SIGNATURE),
        usage_signature=_string_value(data, CONF_USAGE_SIGNATURE),
    )


def has_basic_auth(data: dict[str, Any]) -> bool:
    """Return whether Basic auth can be built."""
    return bool(
        _string_value(data, CONF_BASIC_AUTHORIZATION)
        or (
            _string_value(data, CONF_BASIC_USERNAME)
            and _string_value(data, CONF_BASIC_PASSWORD)
        )
    )


def has_login_credentials(data: dict[str, Any]) -> bool:
    """Return whether replay-login fields are present."""
    return bool(
        _string_value(data, CONF_ENCRYPTED_EMAIL)
        and _string_value(data, CONF_ENCRYPTED_PASSWORD)
        and _string_value(data, CONF_LOGIN_SIGNATURE)
    )


def session_token_from_data(data: dict[str, Any]) -> str:
    """Return the configured app session token, if present."""
    return _string_value(data, CONF_SESSION_TOKEN)


def _string_value(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return str(value).strip() if value is not None else ""
