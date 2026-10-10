"""Plumio: family location for Home Assistant, pushed live from your Nest."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import PlumioClient
from .const import CONF_API_URL, CONF_TOKEN, DEFAULT_API_URL, DOMAIN, PLATFORMS
from .coordinator import PlumioConfigEntry, PlumioCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the domain services once, whatever the number of linked Nests."""
    async_setup_services(hass)
    return True


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.start_stream()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlumioConfigEntry) -> bool:
    """Unload a linked Nest. The stream task dies with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: PlumioConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
