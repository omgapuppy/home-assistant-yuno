from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from homeassistant.helpers.json import json_dumps
from test_api_client import FakeResponse, FakeSession

from custom_components.yuno_energy.config_data import account_data_from_input, auth_config_from_data
from custom_components.yuno_energy.yuno_api.auth import AuthConfig, encrypt_credential
from custom_components.yuno_energy.yuno_api.client import (
    YunoApiClient,
    YunoApiError,
    YunoAuthenticationError,
)


def test_encryption_matches_independent_java_vectors() -> None:
    # Generated with Bouncy Castle 1.78.1 bare RSA and cross-checked with
    # SunJCE RSA/ECB/NoPadding. Only synthetic inputs, never account credentials.
    vectors = json.loads((Path(__file__).parent / "fixtures/rsa_no_padding.json").read_text())
    for vector in vectors:
        assert encrypt_credential(vector["plaintext"]) == vector["ciphertext"]


def test_account_storage_discards_plaintext_password_and_rebuilds_auth() -> None:
    data = account_data_from_input({"email": " Offline@EXAMPLE.invalid ", "password": " secret "})
    auth = auth_config_from_data(data)
    assert "password" not in data
    assert " secret " not in repr(data)
    assert " secret " not in repr(auth)
    assert data["email"] == "offline@example.invalid"
    assert auth.encrypted_password == encrypt_credential(" secret ")
    assert auth.origin_id == "63"
    assert auth.login_body is not None
    assert auth == AuthConfig.from_account_credentials("offline@example.invalid", " secret ")


@pytest.mark.parametrize("value", ["€" * 22, "a" * 65])
def test_overlong_credentials_fail_locally(value: str) -> None:
    with pytest.raises(ValueError, match="too long"):
        AuthConfig.from_account_credentials("offline@example.invalid", value)


@pytest.mark.asyncio
async def test_generated_login_matches_home_assistant_serializer() -> None:
    session = FakeSession()
    auth = AuthConfig.from_account_credentials("offline@example.invalid", "synthetic")
    await YunoApiClient(session=session).login(auth)
    request = session.requests[0][2]
    expected = json_dumps(
        {
            "email": auth.encrypted_email,
            "password": auth.encrypted_password,
            "isPersistent": True,
        }
    ).encode()
    assert request["data"] == expected
    assert "json" not in request
    # Calculate independently of AuthConfig, covering whitespace and field order.
    expected_digest = hashlib.sha1(
        (hashlib.sha1(expected).hexdigest() + "mEwg_85Rt").encode()
    ).hexdigest()
    assert auth.login_signature == "63:" + expected_digest


class QueueSession(FakeSession):
    def __init__(self, statuses: list[int], *, login_status: int = 200) -> None:
        super().__init__()
        self.statuses = iter(statuses)
        self.login_status = login_status

    async def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        response = await super().get(url, headers=headers)
        status = next(self.statuses)
        return response if status == 200 else FakeResponse(status, {})

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object] | None = None,
        data: bytes | None = None,
    ) -> FakeResponse:
        response = await super().post(url, headers=headers, json=json, data=data)
        return (
            response
            if self.login_status == 200
            else FakeResponse(
                self.login_status,
                {"errorCode": 1004},
            )
        )


@pytest.mark.asyncio
async def test_expired_session_logs_in_once_and_returns_replacement() -> None:
    session = QueueSession([401, 200])
    client = YunoApiClient(session=session)
    auth = AuthConfig.from_account_credentials("offline@example.invalid", "synthetic")
    _, token = await client.get_authenticated_usage(auth, session_token="expired")
    assert token == "fixture-session-token"
    assert [request[0] for request in session.requests] == ["GET", "POST", "GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500, 502])
async def test_server_errors_do_not_trigger_login(status: int) -> None:
    session = QueueSession([status])
    auth = AuthConfig.from_account_credentials("offline@example.invalid", "synthetic")
    with pytest.raises(YunoApiError):
        await YunoApiClient(session=session).get_authenticated_usage(auth, session_token="valid")
    assert [request[0] for request in session.requests] == ["GET"]


@pytest.mark.asyncio
async def test_invalid_password_stops_after_one_login() -> None:
    session = QueueSession([401], login_status=400)
    auth = AuthConfig.from_account_credentials("offline@example.invalid", "synthetic")
    with pytest.raises(YunoAuthenticationError):
        await YunoApiClient(session=session).get_authenticated_usage(auth, session_token="expired")
    assert [request[0] for request in session.requests] == ["GET", "POST"]


@pytest.mark.asyncio
async def test_new_session_rejection_does_not_loop() -> None:
    session = QueueSession([401, 401])
    auth = AuthConfig.from_account_credentials("offline@example.invalid", "synthetic")
    with pytest.raises(YunoAuthenticationError):
        await YunoApiClient(session=session).get_authenticated_usage(auth, session_token="expired")
    assert [request[0] for request in session.requests] == ["GET", "POST", "GET"]


@pytest.mark.asyncio
async def test_manual_session_only_entry_never_attempts_login() -> None:
    session = QueueSession([401])
    auth = AuthConfig("", "", "Basic fixture", "64", "", "usage-signature")
    with pytest.raises(YunoAuthenticationError):
        await YunoApiClient(session=session).get_authenticated_usage(
            auth,
            session_token="expired",
            allow_login=False,
        )
    assert [request[0] for request in session.requests] == ["GET"]
