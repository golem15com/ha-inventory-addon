# GREEN in Plan 03
"""Setup-entry skeleton tests.

Asserts async_setup_entry stores a per-entry InventoryClient under
hass.data[DOMAIN][entry.entry_id] and async_unload_entry pops it again.
"""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.whereiput_inventory.api import InventoryClient
from custom_components.whereiput_inventory.const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    DOMAIN,
)


async def test_setup_entry_stores_client_then_unload_pops(hass: HomeAssistant) -> None:
    """Setup stores a client per entry_id; unload removes it."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # The manifest declares dependencies: ["conversation"]; set it up (and its
    # own homeassistant dep) before the entry so HA can resolve the dep tree.
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BASE_URL: "https://api.whereiput.it",
            CONF_TOKEN: "inv_valid",
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    stored = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(stored["client"], InventoryClient)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data.get(DOMAIN, {})
