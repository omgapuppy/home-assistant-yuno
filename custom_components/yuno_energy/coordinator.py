"""Data update coordinator for Yuno Energy."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_data import auth_config_from_data, has_login_credentials, session_token_from_data
from .const import CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL, DOMAIN
from .statistics import async_import_hourly_statistics
from .yuno_api.client import AiohttpSessionAdapter, YunoApiClient, YunoApiError
from .yuno_api.models import DailyUsage


class YunoEnergyCoordinator(DataUpdateCoordinator[Any]):
    """Coordinator that polls Yuno usage and imports recorder statistics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval_minutes = int(
            entry.options.get(
                CONF_SCAN_INTERVAL_MINUTES,
                entry.data.get(
                    CONF_SCAN_INTERVAL_MINUTES,
                    DEFAULT_SCAN_INTERVAL.total_seconds() / 60,
                ),
            )
        )
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
        )
        self.entry = entry
        self.api = YunoApiClient(
            session=AiohttpSessionAdapter(async_get_clientsession(hass)),
        )
        self._store: Store[dict[str, Any]] = Store(
            hass,
            1,
            f"{DOMAIN}_{entry.entry_id}_statistics",
        )
        self.imported_energy_starts: set[str] = set()
        self.energy_last_sum = 0.0
        self.imported_cost_starts: set[str] = set()
        self.cost_last_sum = 0.0
        self.last_update: datetime | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            stored = await self._store.async_load() or {}
            self.imported_energy_starts = set(
                cast(
                    list[str],
                    stored.get("imported_energy_starts", stored.get("imported_starts", [])),
                )
            )
            self.energy_last_sum = float(stored.get("energy_last_sum", stored.get("last_sum", 0.0)))
            self.imported_cost_starts = set(
                cast(list[str], stored.get("imported_cost_starts", []))
            )
            self.cost_last_sum = float(stored.get("cost_last_sum", 0.0))
            entry_data = dict(self.entry.data)
            auth = auth_config_from_data(entry_data)
            try:
                if configured_session_token := session_token_from_data(entry_data):
                    usage = await self.api.get_electricity_usage(
                        auth,
                        session_token=configured_session_token,
                    )
                else:
                    login = await self.api.login(auth)
                    usage = await self.api.get_electricity_usage(
                        auth,
                        session_token=login.session_token,
                    )
            except YunoApiError as err:
                if (
                    configured_session_token
                    and "authentication failed" in str(err)
                    and has_login_credentials(entry_data)
                ):
                    login = await self.api.login(auth)
                    usage = await self.api.get_electricity_usage(
                        auth,
                        session_token=login.session_token,
                    )
                else:
                    raise
            (
                self.imported_energy_starts,
                self.energy_last_sum,
                self.imported_cost_starts,
                self.cost_last_sum,
            ) = await async_import_hourly_statistics(
                self.hass,
                entry_id=self.entry.entry_id,
                hourly_days=usage.hourly,
                imported_energy_starts=self.imported_energy_starts,
                energy_last_sum=self.energy_last_sum,
                imported_cost_starts=self.imported_cost_starts,
                cost_last_sum=self.cost_last_sum,
            )
            await self._store.async_save(
                {
                    "imported_energy_starts": sorted(self.imported_energy_starts),
                    "energy_last_sum": self.energy_last_sum,
                    "imported_cost_starts": sorted(self.imported_cost_starts),
                    "cost_last_sum": self.cost_last_sum,
                }
            )
        except YunoApiError as err:
            if "authentication failed" in str(err):
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(str(err)) from err
        except (TimeoutError, OSError) as err:
            raise UpdateFailed("Yuno API request failed") from err
        self.last_update = datetime.now().astimezone()
        return {
            "hourly": usage.hourly,
            "daily": usage.daily,
            "latest_hourly": max(usage.hourly, key=lambda item: item.date, default=None),
            "latest_daily": _latest_daily(usage.daily),
            "days_returned": len(usage.hourly),
            "last_update": self.last_update,
        }


def _latest_daily(days: list[DailyUsage]) -> DailyUsage | None:
    return max(days, key=lambda item: item.date, default=None)
