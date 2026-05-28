from __future__ import annotations

from custom_components.yuno_energy.flow_errors import (
    diagnostic_message_from_exception,
    error_key_from_exception,
)
from custom_components.yuno_energy.yuno_api.client import YunoApiError


def test_maps_authentication_failure_to_invalid_auth() -> None:
    assert (
        error_key_from_exception(YunoApiError("authentication failed: HTTP 401"))
        == "invalid_auth"
    )


def test_maps_response_shape_failure_to_bad_response() -> None:
    assert (
        error_key_from_exception(YunoApiError("authentication failed: response was not JSON"))
        == "bad_response"
    )


def test_maps_yuno_usage_parse_failure_to_bad_response() -> None:
    assert (
        error_key_from_exception(
            YunoApiError("usage fetch failed: hourlyUsageDetails was not a list")
        )
        == "bad_response"
    )


def test_maps_transport_failure_to_cannot_connect() -> None:
    assert error_key_from_exception(OSError("connection refused")) == "cannot_connect"


def test_diagnostic_message_redacts_secret_fragments() -> None:
    diagnostic = diagnostic_message_from_exception(
        OSError(
            "failed with Authorization=Basic abc123, "
            "X-Http-sessionToken=secret-token, email=person@example.test"
        )
    )

    assert "abc123" not in diagnostic
    assert "secret-token" not in diagnostic
    assert "person@example.test" not in diagnostic
    assert "Authorization=<redacted>" in diagnostic
    assert "X-Http-sessionToken=<redacted>" in diagnostic
    assert "email=<redacted>" in diagnostic
