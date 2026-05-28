"""Config-flow error mapping helpers."""

from __future__ import annotations

import re

from .yuno_api.client import YunoApiError

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b("
    r"authorization|basic_authorization|x-http-sessiontoken|sessiontoken|"
    r"session_token|password|email|token"
    r")\b\s*[:=]\s*[^,\n;]+"
)
_BASIC_VALUE = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=._:-]+")


def error_key_from_exception(err: Exception) -> str:
    """Map internal exceptions to Home Assistant config-flow error keys."""
    if isinstance(err, YunoApiError):
        message = str(err)
        if "response" in message or "payload" in message or "usage fetch failed" in message:
            return "bad_response"
        if "authentication failed" in message:
            return "invalid_auth"
        return "bad_response"
    if isinstance(err, (TimeoutError, OSError)):
        return "cannot_connect"
    return "unknown"


def diagnostic_message_from_exception(err: Exception) -> str:
    """Return a sanitized validation diagnostic suitable for UI/logging."""
    if isinstance(err, YunoApiError):
        message = str(err) or err.__class__.__name__
    elif isinstance(err, TimeoutError):
        message = "request timed out"
    elif isinstance(err, OSError):
        message = str(err) or err.__class__.__name__
        if err.errno is not None:
            message = f"{message} (errno {err.errno})"
    else:
        message = err.__class__.__name__
    return _redact_sensitive_fragments(message)


def _redact_sensitive_fragments(message: str) -> str:
    """Redact secret-looking fragments from exception text."""
    message = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=<redacted>",
        message,
    )
    return _BASIC_VALUE.sub("Basic <redacted>", message)
