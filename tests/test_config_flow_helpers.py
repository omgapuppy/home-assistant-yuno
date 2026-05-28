from __future__ import annotations

from custom_components.yuno_energy.flow_errors import error_key_from_exception
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


def test_maps_transport_failure_to_cannot_connect() -> None:
    assert error_key_from_exception(OSError("connection refused")) == "cannot_connect"
