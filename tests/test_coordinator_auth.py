from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from test_account_auth import QueueSession

from custom_components.yuno_energy.config_data import account_data_from_input
from custom_components.yuno_energy.const import DOMAIN
from custom_components.yuno_energy.coordinator import YunoEnergyCoordinator
from custom_components.yuno_energy.yuno_api.client import YunoApiClient

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("mock_yuno_http_session")]


async def test_refresh_persists_token_and_restart_reuses_it(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **account_data_from_input(
                {"email": "offline@example.invalid", "password": "synthetic"}
            ),
            "session_token": "expired",
        },
    )
    entry.add_to_hass(hass)
    session = QueueSession([401, 200, 200])
    coordinator = YunoEnergyCoordinator(hass, entry)
    coordinator.api = YunoApiClient(session=session)
    with (
        patch("custom_components.yuno_energy.coordinator.Store.async_load", return_value=None),
        patch(
            "custom_components.yuno_energy.coordinator.Store.async_save",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.yuno_energy.coordinator.async_import_hourly_statistics",
            return_value=(set(), 0.0, set(), 0.0),
        ),
    ):
        await coordinator._async_update_data()
        assert entry.data["session_token"] == "fixture-session-token"
        restarted = YunoEnergyCoordinator(hass, entry)
        restarted.api = YunoApiClient(session=session)
        await restarted._async_update_data()
    assert [request[0] for request in session.requests] == ["GET", "POST", "GET", "GET"]


@pytest.mark.parametrize("status,error", [(401, ConfigEntryAuthFailed), (500, UpdateFailed)])
async def test_manual_auth_failure_and_server_failure_are_distinct(
    hass: HomeAssistant,
    status: int,
    error: type[Exception],
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "basic_authorization": "Basic fixture",
            "usage_signature": "signature",
            "session_token": "token",
        },
    )
    entry.add_to_hass(hass)
    coordinator = YunoEnergyCoordinator(hass, entry)
    coordinator.api = YunoApiClient(session=QueueSession([status]))
    with patch.object(coordinator._store, "async_load", return_value=None), pytest.raises(error):
        await coordinator._async_update_data()
