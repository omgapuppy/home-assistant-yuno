"""Typed models for Yuno API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HourlyUsageDay:
    """One Yuno hourly electricity usage day."""

    date: date
    usage_kwh: list[float]
    usage_eur: list[float]
    standing_charge_eur: list[float]
    highest_hourly_usage: str | None
    read_type: str | None


@dataclass(frozen=True)
class DailyUsage:
    """One Yuno daily electricity usage summary."""

    date: date
    usage_kwh: float
    usage_eur: float
    standing_charge_eur: float
    read_type: str | None
