"""Shared pytest fixtures for the whereiput.it Inventory integration tests.

Uses pytest-homeassistant-custom-component (PHACC) for the Home Assistant test
harness and aioresponses to mock the frozen api.whereiput.it endpoints.
"""

import pytest
from aioresponses import aioresponses

pytest_plugins = "pytest_homeassistant_custom_component"


# --- Test constants -------------------------------------------------------

BASE_URL = "https://api.whereiput.it"
TOKEN = "inv_testtoken1234567890"

SEARCH_URL = f"{BASE_URL}/api/v1/inventory/items/search"
AREAS_URL = f"{BASE_URL}/api/v1/inventory/me/areas"

# One row matching the VERIFIED server contract
# (ItemApiController.php:175-183): name, location:{name}, area:{name}, quantity.
mock_search_response = {
    "data": [
        {
            "name": "młotek",
            "location": {"name": "Szuflada"},
            "area": {"name": "Garaż"},
            "quantity": 2,
        }
    ],
    "meta": {"current_page": 1, "last_page": 1, "total": 1},
}

# me/areas contract (MeAreasController.php:42-62): {data:[{id,name,is_owner}]}.
mock_areas_response = {
    "data": [
        {"id": 7, "name": "Garaż", "is_owner": True},
        {"id": 9, "name": "Piwnica", "is_owner": False},
    ]
}


# --- Fixtures -------------------------------------------------------------

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in every test (PHACC)."""
    yield


@pytest.fixture
def mock_aiohttp():
    """aioresponses mock for stubbing the search + areas endpoints.

    Usage:
        def test_x(mock_aiohttp):
            mock_aiohttp.get(SEARCH_URL, payload=mock_search_response)
    """
    with aioresponses() as mocked:
        yield mocked
