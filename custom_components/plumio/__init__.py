"""Plumio: family location for Home Assistant, pushed live from your Nest."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import PlumioClient
from .const import CONF_API_URL, CONF_TOKEN, DEFAULT_API_URL, DOMAIN, PLATFORMS
from .coordinator import PlumioConfigEntry, PlumioCoordinator
from .rooms import TagRooms
from .services import async_setup_services

# Where the dashboard card is served from.
CARD_URL = "/plumio_static/plumio-route-card.js"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the domain services once, whatever the number of linked Nests."""
    async_setup_services(hass)
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the day-route card and load it in every dashboard, with nothing to install.

    The version in the address makes browsers fetch the new file after an update
    instead of keeping the old one for a day.
    """
    if hass.http is None:
        return
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / "plumio-route-card.js"), False)]
    )
    # No dashboards to load it into (a Home Assistant running without its frontend).
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")


async def async_setup_entry(hass: HomeAssistant, entry: PlumioConfigEntry) -> bool:
    """Set up one linked Nest."""
    client = PlumioClient(
        async_get_clientsession(hass),
        entry.data.get(CONF_API_URL, DEFAULT_API_URL),
        entry.data[CONF_TOKEN],
    )
    coordinator = PlumioCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The Nest's device first: everything else is registered "via" it.
    nest_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.nest_id)},
        name=coordinator.data.nest.get("name") or entry.title,
        manufacturer="Plumio",
        configuration_url="https://www.useplumio.com/home-assistant",
        model="Nest",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    coordinator.nest_device_id = nest_device.id
    coordinator.rooms = TagRooms(hass, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.rooms.async_start()
    coordinator.start_stream()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlumioConfigEntry) -> bool:
    """Unload a linked Nest. The stream task dies with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: PlumioConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
