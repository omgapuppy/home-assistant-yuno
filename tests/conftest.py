from collections.abc import Iterator
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_yuno_http_session() -> Iterator[None]:
    """Flow/coordinator tests use fake API responses, without opening HTTP sessions."""
    with (
        patch("custom_components.yuno_energy.config_flow.async_get_clientsession"),
        patch("custom_components.yuno_energy.coordinator.async_get_clientsession"),
    ):
        yield
