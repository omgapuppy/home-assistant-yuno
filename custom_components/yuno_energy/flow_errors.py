"""Config-flow error mapping helpers."""

from __future__ import annotations

from .yuno_api.client import YunoApiError


def error_key_from_exception(err: Exception) -> str:
    """Map internal exceptions to Home Assistant config-flow error keys."""
    if isinstance(err, YunoApiError):
        message = str(err)
        if "response" in message or "payload" in message:
            return "bad_response"
        if "authentication failed" in message:
            return "invalid_auth"
    return "cannot_connect"
