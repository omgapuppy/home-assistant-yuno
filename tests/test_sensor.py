from __future__ import annotations

from custom_components.yuno_energy.const import DOMAIN
from custom_components.yuno_energy.device import device_info_for_entry


def test_device_info_groups_entities_under_config_entry_device() -> None:
    device_info = device_info_for_entry("entry-123")

    assert device_info["identifiers"] == {(DOMAIN, "entry-123")}
    assert device_info["name"] == "Yuno Energy"
    assert device_info["manufacturer"] == "Yuno Energy Ireland"
