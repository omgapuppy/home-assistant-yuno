from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from custom_components.yuno_energy.yuno_api.client import (
    AuthConfig,
    LoginResult,
    UsageResult,
    YunoApiClient,
    YunoApiError,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, object]]] = []

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> FakeResponse:
        self.requests.append(("POST", url, {"headers": headers, "json": json}))
        payload = json_fixture("login_response.json")
        return FakeResponse(200, payload)

    async def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        self.requests.append(("GET", url, {"headers": headers}))
        payload = json_fixture("electricity_usage.json")
        return FakeResponse(200, payload)


def json_fixture(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((Path(__file__).parent / "fixtures" / name).read_text()),
    )


@pytest.mark.asyncio
async def test_login_posts_encrypted_credentials_with_static_headers() -> None:
    session = FakeSession()
    client = YunoApiClient(session=session)
    auth = AuthConfig(
        encrypted_email="encrypted-email",
        encrypted_password="encrypted-password",
        basic_authorization="Basic fixture",
        origin_id="64",
        login_signature="login-signature",
        usage_signature="usage-signature",
    )

    result = await client.login(auth)

    assert result == LoginResult(session_token="fixture-session-token")
    assert session.requests == [
        (
            "POST",
            "https://appbillpay.yunoenergy.ie:2015/api/login",
            {
                "headers": {
                    "Accept": "application/json",
                    "Accept-Language": "en-IE,en;q=0.9",
                    "Authorization": "Basic fixture",
                    "Content-Type": "application/json",
                    "User-Agent": "YunoEnergyHomeAssistant/0.1",
                    "X-Http-originid": "64",
                    "X-Http-signature": "login-signature",
                },
                "json": {
                    "email": "encrypted-email",
                    "password": "encrypted-password",
                    "isPersistent": True,
                },
            },
        )
    ]


@pytest.mark.asyncio
async def test_usage_request_sends_session_token_and_parses_hourly_arrays() -> None:
    session = FakeSession()
    client = YunoApiClient(session=session)
    auth = AuthConfig(
        encrypted_email="encrypted-email",
        encrypted_password="encrypted-password",
        basic_authorization="Basic fixture",
        origin_id="64",
        login_signature="login-signature",
        usage_signature="usage-signature",
    )

    result = await client.get_electricity_usage(auth, session_token="fixture-session")

    assert isinstance(result, UsageResult)
    assert len(result.hourly) == 1
    assert result.hourly[0].date.isoformat() == "2026-05-26"
    assert result.hourly[0].usage_kwh[0] == 0.11
    assert result.hourly[0].usage_kwh[-1] == 0.34
    assert result.hourly[0].read_type == "Actual"
    assert session.requests[0] == (
        "GET",
        "https://appbillpay.yunoenergy.ie:2015/api/bill/electricityUsage",
        {
            "headers": {
                "Accept": "application/json",
                "Accept-Language": "en-IE,en;q=0.9",
                "Authorization": "Basic fixture",
                "Content-Type": "application/json",
                "User-Agent": "YunoEnergyHomeAssistant/0.1",
                "X-Http-originid": "64",
                "X-Http-sessionToken": "fixture-session",
                "X-Http-signature": "usage-signature",
            }
        },
    )


@pytest.mark.asyncio
async def test_raises_auth_error_for_unauthorized_response() -> None:
    class UnauthorizedSession(FakeSession):
        async def post(
            self,
            url: str,
            *,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            return FakeResponse(401, {"message": "unauthorized"})

    client = YunoApiClient(session=UnauthorizedSession())
    auth = AuthConfig(
        encrypted_email="encrypted-email",
        encrypted_password="encrypted-password",
        basic_authorization="Basic fixture",
        origin_id="64",
        login_signature="login-signature",
        usage_signature="usage-signature",
    )

    with pytest.raises(YunoApiError, match="authentication failed"):
        await client.login(auth)
