"""Exercise Home Assistant's recorder validation, mocking only the database queue."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
from homeassistant.components.recorder import statistics as recorder

from custom_components.yuno_energy.statistics import async_import_hourly_statistics
from custom_components.yuno_energy.yuno_api.models import HourlyUsageDay


@pytest.mark.asyncio
async def test_sum_metadata_needs_no_recorder_backfill_or_deprecation() -> None:
    day = HourlyUsageDay(
        date=date(2026, 9, 1),
        usage_kwh=[1.0] * 24,
        usage_eur=[0.25] * 24,
        standing_charge_eur=[0.02] * 24,
        highest_hourly_usage="0",
        read_type="Actual",
    )
    submitted: list[dict[str, Any]] = []
    real_add = recorder.async_add_external_statistics

    def record_submission(hass: Any, metadata: Any, rows: Any) -> None:
        # Capture before HA can silently backfill missing metadata fields.
        submitted.append(deepcopy(metadata))
        real_add(hass, metadata, rows)

    queue = Mock()
    with (
        patch.object(recorder, "get_instance", return_value=queue),
        patch.object(recorder, "report_usage", create=True) as report,
        patch.object(recorder, "async_add_external_statistics", side_effect=record_submission),
    ):
        result = await async_import_hourly_statistics(
            object(),
            entry_id="recorder-test",
            hourly_days=[day],
            imported_energy_starts=set(),
            energy_last_sum=0.0,
            imported_cost_starts=set(),
            cost_last_sum=0.0,
        )
        report.assert_not_called()
        assert len(submitted) == queue.async_import_statistics.call_count == 2
        for metadata, call in zip(
            submitted, queue.async_import_statistics.call_args_list, strict=True
        ):
            assert metadata == call.args[0], "Recorder had to repair the submitted metadata"
            assert metadata["has_sum"] is True
            if "mean_type" in cast(Any, recorder).StatisticMetaData.__annotations__:
                assert metadata["mean_type"] == cast(Any, recorder).StatisticMeanType.NONE
                assert "has_mean" not in metadata
            else:
                assert metadata["has_mean"] is False
                assert "mean_type" not in metadata
            if "unit_class" in cast(Any, recorder).StatisticMetaData.__annotations__:
                expected_class = "energy" if metadata["unit_of_measurement"] == "kWh" else None
                assert metadata["unit_class"] == expected_class
            else:
                assert "unit_class" not in metadata
            assert len(call.args[1]) == 24

        assert submitted[0]["statistic_id"] == "yuno_energy:recorder_test_electricity_import"
        assert submitted[1]["statistic_id"] == "yuno_energy:recorder_test_electricity_import_cost"
        energy_starts, energy_sum, cost_starts, cost_sum = result
        assert len(energy_starts) == len(cost_starts) == 24
        assert energy_sum == 24.0
        assert cost_sum == 6.48
        repeated = await async_import_hourly_statistics(
            object(),
            entry_id="recorder-test",
            hourly_days=[day],
            imported_energy_starts=energy_starts,
            energy_last_sum=energy_sum,
            imported_cost_starts=cost_starts,
            cost_last_sum=cost_sum,
        )
        assert repeated == result
        assert queue.async_import_statistics.call_count == 2
