"""Test configuration for Yarbo integration.

pytest-homeassistant-custom-component loads the real HA at plugin startup,
so all HA modules resolve to the actual homeassistant package.

enable_custom_integrations: clears the HA loader deny-flag so that the
hass fixture can discover and load our integration from ./custom_components/.
"""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow hass fixture to load integrations from ./custom_components/."""
