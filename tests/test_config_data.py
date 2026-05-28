from __future__ import annotations

from custom_components.yuno_energy.config_data import (
    auth_config_from_data,
    has_login_credentials,
    session_token_from_data,
)
from custom_components.yuno_energy.const import (
    CONF_BASIC_AUTHORIZATION,
    CONF_ENCRYPTED_EMAIL,
    CONF_ENCRYPTED_PASSWORD,
    CONF_LOGIN_SIGNATURE,
    CONF_ORIGIN_ID,
    CONF_SESSION_TOKEN,
    CONF_USAGE_SIGNATURE,
)


def test_session_token_can_be_supplied_without_login_credentials() -> None:
    data = {
        CONF_BASIC_AUTHORIZATION: "Basic fixture",
        CONF_ORIGIN_ID: "64",
        CONF_USAGE_SIGNATURE: "usage-signature",
        CONF_SESSION_TOKEN: "session-token",
    }

    auth = auth_config_from_data(data)

    assert auth.encrypted_email == ""
    assert auth.encrypted_password == ""
    assert auth.login_signature == ""
    assert auth.usage_signature == "usage-signature"
    assert session_token_from_data(data) == "session-token"
    assert not has_login_credentials(data)


def test_login_credentials_are_available_when_all_login_fields_are_present() -> None:
    data = {
        CONF_ENCRYPTED_EMAIL: "encrypted-email",
        CONF_ENCRYPTED_PASSWORD: "encrypted-password",
        CONF_LOGIN_SIGNATURE: "login-signature",
    }

    assert has_login_credentials(data)
