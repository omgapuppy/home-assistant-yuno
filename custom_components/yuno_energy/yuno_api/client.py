"""Async client for the private Yuno Energy mobile API."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from .models import DailyUsage, HourlyUsageDay


class ResponseProtocol(Protocol):
    """Subset of aiohttp response used by the client."""

    @property
    def status_code(self) -> int:
        """Return HTTP status code."""

    def json(self) -> object:
        """Return decoded JSON."""


class SessionProtocol(Protocol):
    """Subset of an async HTTP session used by the client."""

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> ResponseProtocol:
        """POST a JSON request."""

    async def get(self, url: str, *, headers: dict[str, str]) -> ResponseProtocol:
        """GET a JSON response."""


@dataclass(frozen=True)
class AuthConfig:
    """Secret and static header configuration for Yuno API requests."""

    encrypted_email: str
    encrypted_password: str
    basic_authorization: str
    origin_id: str
    login_signature: str
    usage_signature: str

    @classmethod
    def from_basic_credentials(
        cls,
        *,
        encrypted_email: str,
        encrypted_password: str,
        basic_username: str,
        basic_password: str,
        origin_id: str,
        login_signature: str,
        usage_signature: str,
    ) -> AuthConfig:
        """Build an auth config from Basic username/password fields."""
        raw = f"{basic_username}:{basic_password}".encode()
        return cls(
            encrypted_email=encrypted_email,
            encrypted_password=encrypted_password,
            basic_authorization=f"Basic {base64.b64encode(raw).decode()}",
            origin_id=origin_id,
            login_signature=login_signature,
            usage_signature=usage_signature,
        )


@dataclass(frozen=True)
class LoginResult:
    """Parsed login result."""

    session_token: str


@dataclass(frozen=True)
class UsageResult:
    """Parsed electricity usage result."""

    hourly: list[HourlyUsageDay]
    daily: list[DailyUsage]


class YunoApiError(Exception):
    """Raised when the Yuno API returns an error or unexpected payload."""


class AiohttpSessionAdapter:
    """Adapter that exposes aiohttp's context-manager API as simple methods."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> ResponseProtocol:
        async with self._session.post(url, headers=headers, json=json) as response:
            try:
                payload = await response.json(content_type=None)
            except ValueError:
                payload = None
            return AiohttpResponseAdapter(response.status, payload)

    async def get(self, url: str, *, headers: dict[str, str]) -> ResponseProtocol:
        async with self._session.get(url, headers=headers) as response:
            try:
                payload = await response.json(content_type=None)
            except ValueError:
                payload = None
            return AiohttpResponseAdapter(response.status, payload)


@dataclass(frozen=True)
class AiohttpResponseAdapter:
    """Simple response wrapper for aiohttp results."""

    status_code: int
    payload: object

    def json(self) -> object:
        """Return decoded JSON."""
        return self.payload


class YunoApiClient:
    """Client for the captured Yuno mobile API surface used by the integration."""

    def __init__(
        self,
        *,
        session: SessionProtocol,
        base_url: str = "https://appbillpay.yunoenergy.ie:2015",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def login(self, auth: AuthConfig) -> LoginResult:
        """Log in with encrypted app credentials and return a session token."""
        response = await self._session.post(
            f"{self._base_url}/api/login",
            headers=self._headers(auth, auth.login_signature),
            json={
                "email": auth.encrypted_email,
                "password": auth.encrypted_password,
                "isPersistent": True,
            },
        )
        payload = self._checked_payload(response, action="authentication")
        token = payload.get("sessionToken")
        if not isinstance(token, str) or not token:
            raise YunoApiError("authentication failed: missing session token")
        return LoginResult(session_token=token)

    async def get_electricity_usage(self, auth: AuthConfig, *, session_token: str) -> UsageResult:
        """Fetch and parse hourly electricity usage."""
        headers = self._headers(auth, auth.usage_signature)
        headers["X-Http-sessionToken"] = session_token
        response = await self._session.get(
            f"{self._base_url}/api/bill/electricityUsage",
            headers=headers,
        )
        payload = self._checked_payload(response, action="usage fetch")
        return UsageResult(
            hourly=_parse_hourly_usage(payload.get("hourlyUsageDetails")),
            daily=_parse_daily_usage(payload.get("dailyUsageDetails")),
        )

    @staticmethod
    def _headers(auth: AuthConfig, signature: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Accept-Language": "en-IE,en;q=0.9",
            "Authorization": auth.basic_authorization,
            "Content-Type": "application/json",
            "User-Agent": "YunoEnergyHomeAssistant/0.1",
            "X-Http-originid": auth.origin_id,
            "X-Http-signature": signature,
        }

    @staticmethod
    def _checked_payload(response: ResponseProtocol, *, action: str) -> dict[str, Any]:
        payload = response.json()
        details = _api_error_details(payload)
        if response.status_code in {401, 403}:
            raise YunoApiError(
                f"{action} failed: authentication failed "
                f"(HTTP {response.status_code}{details})"
            )
        if response.status_code >= 400:
            raise YunoApiError(f"{action} failed: HTTP {response.status_code}{details}")
        if not isinstance(payload, dict):
            raise YunoApiError(f"{action} failed: response was not a JSON object")
        return payload


def _parse_hourly_usage(value: object) -> list[HourlyUsageDay]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise YunoApiError("usage fetch failed: hourlyUsageDetails was not a list")

    days: list[HourlyUsageDay] = []
    for item in value:
        if not isinstance(item, dict):
            raise YunoApiError("usage fetch failed: hourly usage item was not an object")
        usage_kwh = _float_list(item.get("hourlyUsageInKwh"), "hourlyUsageInKwh")
        usage_eur = _float_list(item.get("hourlyUsageInEuro"), "hourlyUsageInEuro")
        standing = _float_list(
            item.get("hourlyStandingChargeInEuro"),
            "hourlyStandingChargeInEuro",
        )
        if len(usage_kwh) != 24 or len(usage_eur) != 24 or len(standing) != 24:
            raise YunoApiError("usage fetch failed: hourly arrays must contain 24 values")
        days.append(
            HourlyUsageDay(
                date=_date_value(item.get("date"), "date"),
                usage_kwh=usage_kwh,
                usage_eur=usage_eur,
                standing_charge_eur=standing,
                highest_hourly_usage=_optional_str(item.get("highestHourlyUsage")),
                read_type=_optional_str(item.get("readType")),
            )
        )
    return days


def _api_error_details(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    parts: list[str] = []
    for key in ("title", "errorCode", "status"):
        value = payload.get(key)
        if isinstance(value, (str, int, float)):
            parts.append(f"{key}={value}")
    return f"; {', '.join(parts)}" if parts else ""


def _parse_daily_usage(value: object) -> list[DailyUsage]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise YunoApiError("usage fetch failed: dailyUsageDetails was not a list")

    days: list[DailyUsage] = []
    for item in value:
        if not isinstance(item, dict):
            raise YunoApiError("usage fetch failed: daily usage item was not an object")
        days.append(
            DailyUsage(
                date=_date_value(item.get("date"), "date"),
                usage_kwh=_float_value(item.get("dailyUsageInkWh"), "dailyUsageInkWh"),
                usage_eur=_float_value(item.get("dailyUsageInEuro"), "dailyUsageInEuro"),
                standing_charge_eur=_float_value(
                    item.get("dailyStandingChargeInEuro"),
                    "dailyStandingChargeInEuro",
                ),
                read_type=_optional_str(item.get("readType")),
            )
        )
    return days


def _float_list(value: object, field: str) -> list[float]:
    if not isinstance(value, list):
        raise YunoApiError(f"usage fetch failed: {field} was not a list")
    return [_float_value(item, field) for item in value]


def _float_value(value: object, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise YunoApiError(f"usage fetch failed: {field} was not numeric")
    return float(value)


def _date_value(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise YunoApiError(f"usage fetch failed: {field} was not a string")
    try:
        return date.fromisoformat(value)
    except ValueError as err:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            raise YunoApiError(f"usage fetch failed: {field} was not ISO formatted") from err


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
