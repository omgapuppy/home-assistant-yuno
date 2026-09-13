from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientConnectionError

from custom_components.yuno_energy.yuno_api.auth import AuthConfig
from custom_components.yuno_energy.yuno_api.client import (
    AiohttpSessionAdapter,
    YunoApiClient,
    YunoConnectionError,
)


@pytest.mark.asyncio
async def test_adapter_preserves_signed_body_and_disables_redirects() -> None:
    session = MagicMock()
    response = MagicMock(status=200)
    response.json = AsyncMock(return_value={"sessionToken": "fixture-token"})
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    auth = AuthConfig.from_account_credentials("offline@example.invalid", "synthetic")
    await YunoApiClient(session=AiohttpSessionAdapter(session)).login(auth)
    kwargs = session.post.call_args.kwargs
    assert kwargs["data"] == auth.login_body.encode()  # type: ignore[union-attr]
    assert "json" not in kwargs
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"].total == 30


@pytest.mark.asyncio
async def test_adapter_converts_transport_errors_without_including_secrets() -> None:
    session = MagicMock()
    session.get.side_effect = ClientConnectionError("secret transport detail")
    with pytest.raises(YunoConnectionError) as err:
        await AiohttpSessionAdapter(session).get("https://example.invalid", headers={})
    assert "secret transport detail" not in str(err.value)
