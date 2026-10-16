"""Diagnostics, with everything that locates or names a person removed."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import PlumioConfigEntry

TO_REDACT = {
    CONF_TOKEN,
    "lat",
    "lng",
    "displayName",
    "avatarUrl",
    "name",
    "placeName",
    "note",
    "originName",
    "destName",
    # A trip's route. The state no longer keeps them, but redact them anyway in case
    # they ever come back through a payload.
    "previewPolyline",
    "boundingBox",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PlumioConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = asdict(coordinator.data)
    data["stale"] = sorted(data["stale"])
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "stream_connected": coordinator.stream_connected,
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(data, TO_REDACT),
    }
