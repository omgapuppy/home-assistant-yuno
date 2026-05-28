from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.yuno_energy.statistics import (
    build_hourly_statistics,
    build_new_hourly_cost_statistics,
    build_new_hourly_statistics,
    cost_statistic_id_for_entry,
    statistic_id_for_entry,
)
from custom_components.yuno_energy.yuno_api.models import HourlyUsageDay


def test_builds_hourly_statistics_with_europe_dublin_wall_clock_hours() -> None:
    day = HourlyUsageDay(
        date=datetime(2026, 5, 26).date(),
        usage_kwh=[float(hour) for hour in range(24)],
        usage_eur=[float(hour) / 10 for hour in range(24)],
        standing_charge_eur=[0.02 for _ in range(24)],
        highest_hourly_usage="23",
        read_type="Actual",
    )

    rows = build_hourly_statistics([day])

    assert len(rows) == 24
    assert rows[0].start == datetime(2026, 5, 26, 0, 0, tzinfo=ZoneInfo("Europe/Dublin"))
    assert rows[23].start == datetime(2026, 5, 26, 23, 0, tzinfo=ZoneInfo("Europe/Dublin"))
    assert rows[0].sum == 0.0
    assert rows[23].sum == sum(float(hour) for hour in range(24))
    assert rows[23].state == 23.0


def test_statistic_id_is_stable_for_config_entry() -> None:
    assert (
        statistic_id_for_entry("abc123")
        == "custom_components:yuno_energy_abc123_electricity_import"
    )
    assert (
        cost_statistic_id_for_entry("abc123")
        == "custom_components:yuno_energy_abc123_electricity_import_cost"
    )


def test_builds_only_new_statistics_from_previous_cumulative_sum() -> None:
    day = HourlyUsageDay(
        date=datetime(2026, 5, 26).date(),
        usage_kwh=[1.0 for _ in range(24)],
        usage_eur=[0.1 for _ in range(24)],
        standing_charge_eur=[0.02 for _ in range(24)],
        highest_hourly_usage="0",
        read_type="Actual",
    )
    imported = {
        datetime(2026, 5, 26, hour, tzinfo=ZoneInfo("Europe/Dublin")).isoformat()
        for hour in range(23)
    }

    rows = build_new_hourly_statistics([day], imported_starts=imported, initial_sum=100.0)

    assert len(rows) == 1
    assert rows[0].start == datetime(2026, 5, 26, 23, tzinfo=ZoneInfo("Europe/Dublin"))
    assert rows[0].state == 1.0
    assert rows[0].sum == 101.0


def test_builds_hourly_cost_statistics_from_usage_and_standing_charge() -> None:
    day = HourlyUsageDay(
        date=datetime(2026, 5, 26).date(),
        usage_kwh=[1.0 for _ in range(24)],
        usage_eur=[0.25 for _ in range(24)],
        standing_charge_eur=[0.02 for _ in range(24)],
        highest_hourly_usage="0",
        read_type="Actual",
    )

    rows = build_new_hourly_cost_statistics([day], imported_starts=set(), initial_sum=10.0)

    assert len(rows) == 24
    assert rows[0].start == datetime(2026, 5, 26, 0, tzinfo=ZoneInfo("Europe/Dublin"))
    assert rows[0].state == 0.27
    assert rows[0].sum == 10.27
    assert rows[23].state == 0.27
    assert rows[23].sum == 16.48
