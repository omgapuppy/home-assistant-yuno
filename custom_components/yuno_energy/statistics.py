"""Recorder statistics helpers for Yuno Energy hourly imports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from .const import DOMAIN
from .yuno_api.models import HourlyUsageDay

LOCAL_TZ = ZoneInfo("Europe/Dublin")
STATISTICS_SOURCE = DOMAIN
_INVALID_STATISTIC_OBJECT_ID = re.compile(r"[^a-z0-9_]+")


@dataclass(frozen=True)
class HourlyStatisticRow:
    """One hourly statistic row prepared for Home Assistant recorder import."""

    start: datetime
    state: float
    sum: float


def statistic_id_for_entry(entry_id: str) -> str:
    """Return the stable external statistic id for a config entry."""
    return f"{DOMAIN}:{_statistic_object_id(entry_id)}_electricity_import"


def cost_statistic_id_for_entry(entry_id: str) -> str:
    """Return the stable external cost statistic id for a config entry."""
    return f"{statistic_id_for_entry(entry_id)}_cost"


def _statistic_object_id(entry_id: str) -> str:
    object_id = _INVALID_STATISTIC_OBJECT_ID.sub("_", entry_id.lower()).strip("_")
    return object_id or "entry"


def build_hourly_statistics(days: list[HourlyUsageDay]) -> list[HourlyStatisticRow]:
    """Convert Yuno's 24 local wall-clock values per day into hourly statistics.

    Yuno returns exactly 24 values per date in observed captures. For DST transition
    dates this preserves the app's local wall-clock indexing rather than inventing or
    dropping an hour, because the private API does not expose UTC offsets per value.
    """
    return build_new_hourly_statistics(days, imported_starts=set(), initial_sum=0.0)


def build_new_hourly_statistics(
    days: list[HourlyUsageDay],
    *,
    imported_starts: set[str],
    initial_sum: float,
) -> list[HourlyStatisticRow]:
    """Build hourly statistics that have not already been imported."""
    rows: list[HourlyStatisticRow] = []
    cumulative = initial_sum
    for day in sorted(days, key=lambda item: item.date):
        if len(day.usage_kwh) != 24:
            continue
        for hour, usage in enumerate(day.usage_kwh):
            start = datetime(
                day.date.year,
                day.date.month,
                day.date.day,
                hour,
                tzinfo=LOCAL_TZ,
            )
            if start.isoformat() in imported_starts:
                continue
            cumulative += usage
            rows.append(
                HourlyStatisticRow(
                    start=start,
                    state=usage,
                    sum=cumulative,
                )
            )
    return rows


def build_new_hourly_cost_statistics(
    days: list[HourlyUsageDay],
    *,
    imported_starts: set[str],
    initial_sum: float,
) -> list[HourlyStatisticRow]:
    """Build hourly total-cost statistics that have not already been imported."""
    rows: list[HourlyStatisticRow] = []
    cumulative = initial_sum
    for day in sorted(days, key=lambda item: item.date):
        if len(day.usage_eur) != 24 or len(day.standing_charge_eur) != 24:
            continue
        for hour in range(24):
            usage_cost = day.usage_eur[hour]
            standing_charge = day.standing_charge_eur[hour]
            start = datetime(
                day.date.year,
                day.date.month,
                day.date.day,
                hour,
                tzinfo=LOCAL_TZ,
            )
            if start.isoformat() in imported_starts:
                continue
            cost = round(usage_cost + standing_charge, 6)
            cumulative = round(cumulative + cost, 6)
            rows.append(
                HourlyStatisticRow(
                    start=start,
                    state=cost,
                    sum=cumulative,
                )
            )
    return rows


async def async_import_hourly_statistics(
    hass: Any,
    *,
    entry_id: str,
    hourly_days: list[HourlyUsageDay],
    imported_energy_starts: set[str],
    energy_last_sum: float,
    imported_cost_starts: set[str],
    cost_last_sum: float,
) -> tuple[set[str], float, set[str], float]:
    """Import new hourly statistics into Home Assistant recorder.

    Home Assistant external statistics are keyed by statistic id and start time. This
    helper avoids re-importing identical timestamps during normal polling. If Yuno
    revises a past hour, a future version can compare stored values and call the
    recorder adjustment APIs; the current importer keeps the repeated poll idempotent.
    """
    energy_rows = build_new_hourly_statistics(
        hourly_days,
        imported_starts=imported_energy_starts,
        initial_sum=energy_last_sum,
    )
    cost_rows = build_new_hourly_cost_statistics(
        hourly_days,
        imported_starts=imported_cost_starts,
        initial_sum=cost_last_sum,
    )
    if not energy_rows and not cost_rows:
        return imported_energy_starts, energy_last_sum, imported_cost_starts, cost_last_sum

    from homeassistant.components.recorder import statistics as recorder_statistics  # noqa: PLC0415
    from homeassistant.const import UnitOfEnergy  # noqa: PLC0415

    recorder_stats = cast(Any, recorder_statistics)
    if energy_rows:
        metadata = recorder_stats.StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Yuno Energy electricity import",
            source=STATISTICS_SOURCE,
            statistic_id=statistic_id_for_entry(entry_id),
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )
        statistic_rows = [
            recorder_stats.StatisticData(start=row.start, state=row.state, sum=row.sum)
            for row in energy_rows
        ]
        recorder_stats.async_add_external_statistics(hass, metadata, statistic_rows)
        imported_energy_starts = imported_energy_starts | {
            row.start.isoformat() for row in energy_rows
        }
        energy_last_sum = energy_rows[-1].sum

    if cost_rows:
        metadata = recorder_stats.StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Yuno Energy electricity import cost",
            source=STATISTICS_SOURCE,
            statistic_id=cost_statistic_id_for_entry(entry_id),
            unit_of_measurement="EUR",
        )
        statistic_rows = [
            recorder_stats.StatisticData(start=row.start, state=row.state, sum=row.sum)
            for row in cost_rows
        ]
        recorder_stats.async_add_external_statistics(hass, metadata, statistic_rows)
        imported_cost_starts = imported_cost_starts | {row.start.isoformat() for row in cost_rows}
        cost_last_sum = cost_rows[-1].sum

    return imported_energy_starts, energy_last_sum, imported_cost_starts, cost_last_sum
