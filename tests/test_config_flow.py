from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yuno_energy.config_data import account_data_from_input
from custom_components.yuno_energy.const import DOMAIN
from custom_components.yuno_energy.yuno_api.client import UsageResult, YunoAuthenticationError

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations", "mock_yuno_http_session"),
]
API = "custom_components.yuno_energy.config_flow.YunoApiClient.get_authenticated_usage"
SETUP = "custom_components.yuno_energy.async_setup_entry"
INPUT = {"email": "offline@example.invalid", "password": "synthetic", "scan_interval_minutes": 360}


async def start_account_flow(hass: HomeAssistant) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["account", "manual"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "account"}
    )
    assert result["type"] == FlowResultType.FORM
    return dict(result)


async def test_account_flow_stores_token_but_no_plaintext_password(hass: HomeAssistant) -> None:
    result = await start_account_flow(hass)
    with (
        patch(API, return_value=(UsageResult([], []), "fresh-token")) as api,
        patch(SETUP, return_value=True),
    ):
        result = dict(await hass.config_entries.flow.async_configure(result["flow_id"], INPUT))
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["session_token"] == "fresh-token"
    assert result["data"]["auth_mode"] == "account"
    assert "password" not in result["data"]
    assert "synthetic" not in repr(result["data"])
    api.assert_awaited_once()
    assert api.call_args.kwargs == {"session_token": "", "allow_login": True}


async def test_rejected_credentials_redisplay_form_without_password_default(
    hass: HomeAssistant,
) -> None:
    result = await start_account_flow(hass)
    with patch(API, side_effect=YunoAuthenticationError("authentication failed: HTTP 400")) as api:
        result = dict(await hass.config_entries.flow.async_configure(result["flow_id"], INPUT))
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert "synthetic" not in repr(result)
    api.assert_awaited_once()


async def test_reauth_does_not_retry_saved_credentials_on_open(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data={**account_data_from_input(INPUT), "session_token": "expired"}
    )
    entry.add_to_hass(hass)
    with patch(API) as api:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=dict(entry.data),
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    api.assert_not_awaited()
    with (
        patch(API, return_value=(UsageResult([], []), "replacement")),
        patch.object(
            hass.config_entries,
            "async_reload",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["session_token"] == "replacement"
    assert "password" not in entry.data


async def test_reconfigure_manual_entry_to_account_preserves_entry_and_options(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            "basic_authorization": "Basic fixture",
            "usage_signature": "usage-signature",
            "session_token": "old",
        },
        options={"scan_interval_minutes": 90},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "account"}
    )
    with (
        patch(API, return_value=(UsageResult([], []), "replacement")),
        patch.object(
            hass.config_entries,
            "async_reload",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data["auth_mode"] == "account"
    assert entry.data["session_token"] == "replacement"
    assert entry.options["scan_interval_minutes"] == 90


async def test_manual_session_mode_still_works(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with (
        patch(API, return_value=(UsageResult([], []), "existing-token")) as api,
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "basic_authorization": "Basic fixture",
                "usage_signature": "signature",
                "session_token": "existing-token",
                "origin_id": "64",
                "scan_interval_minutes": 360,
            },
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert api.call_args.kwargs == {"session_token": "existing-token", "allow_login": False}
