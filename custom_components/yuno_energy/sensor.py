"""Sensors for the Yuno Energy integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YunoEnergyCoordinator


def _daily_value(data: dict[str, Any], attr: str) -> float | None:
    latest = data.get("latest_daily")
    if latest is None:
        return None
    value = getattr(latest, attr)
    return float(value) if isinstance(value, (int, float)) else None


def _freshness_lag(data: dict[str, Any]) -> int | None:
    latest = data.get("latest_hourly")
    if latest is None:
        return None
    today = datetime.now().astimezone().date()
    latest_date: date = latest.date
    return (today - latest_date).days


@dataclass(frozen=True)
class SensorDescription:
    """Description for a Yuno sensor."""

    key: str
    name: str
    value_fn: Callable[[dict[str, Any]], Any]
    native_unit_of_measurement: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


SENSORS = [
    SensorDescription(
        key="latest_usage_date",
        name="Latest usage date",
        value_fn=lambda data: data["latest_hourly"].date if data.get("latest_hourly") else None,
    ),
    SensorDescription(
        key="latest_read_type",
        name="Latest read type",
        value_fn=lambda data: (
            data["latest_hourly"].read_type if data.get("latest_hourly") else None
        ),
    ),
    SensorDescription(
        key="yesterday_kwh",
        name="Yesterday usage",
        value_fn=lambda data: _daily_value(data, "usage_kwh"),
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDescription(
        key="yesterday_usage_cost_eur",
        name="Yesterday usage cost",
        value_fn=lambda data: _daily_value(data, "usage_eur"),
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDescription(
        key="yesterday_standing_charge_eur",
        name="Yesterday standing charge",
        value_fn=lambda data: _daily_value(data, "standing_charge_eur"),
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDescription(
        key="days_returned",
        name="Days returned",
        value_fn=lambda data: data.get("days_returned"),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key="data_freshness_lag",
        name="Data freshness lag",
        value_fn=_freshness_lag,
        native_unit_of_measurement="d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yuno Energy sensors."""
    coordinator: YunoEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        YunoEnergySensor(coordinator, entry.entry_id, description) for description in SENSORS
    )


class YunoEnergySensor(CoordinatorEntity[YunoEnergyCoordinator], SensorEntity):
    """A Yuno Energy sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YunoEnergyCoordinator,
        entry_id: str,
        description: SensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_translation_key = description.key
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class

    @property
    def native_value(self) -> Any:
        """Return sensor state."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
