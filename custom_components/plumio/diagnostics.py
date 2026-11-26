"""Diagnostics, with everything that locates, names or identifies a person removed."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_LINK_ID, CONF_NEST_ID, CONF_TOKEN
from .coordinator import PlumioConfigEntry, PlumioData

TO_REDACT = {
    CONF_TOKEN,
    CONF_LINK_ID,
    CONF_NEST_ID,
    "linkId",
    "nestId",
    "userId",
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


def _aliases(entry: PlumioConfigEntry, data: PlumioData) -> dict[str, str]:
    """Every Plumio account id in the dump, to a placeholder.

    Members are keyed by user id, and `async_redact_data` only looks at key names, never
    at the keys themselves nor at list items: those ids have to be swapped before it runs.
    Each person keeps the same placeholder everywhere (member_1 in `members`, `stale`,
    `sos` and `last_trip`), so the dump still says who is who without saying who.
    """
    user_ids = [*data.members, *data.stale, *data.last_trip, *(s.get("userId") for s in data.sos.values())]
    aliases: dict[str, str] = {}
    for user_id in user_ids:
        if isinstance(user_id, str) and user_id and user_id not in aliases:
            aliases[user_id] = f"member_{len(aliases) + 1}"
    for key in (CONF_NEST_ID, CONF_LINK_ID):
        if value := entry.data.get(key):
            aliases[value] = REDACTED
    if nest_id := data.nest.get("id"):
        aliases[nest_id] = REDACTED
    return aliases


def _pseudonymize(value: Any, aliases: dict[str, str]) -> Any:
    """Swap every id in `aliases` wherever it appears: dict keys, values and list items."""
    if isinstance(value, dict):
        return {_pseudonymize(k, aliases): _pseudonymize(v, aliases) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_pseudonymize(v, aliases) for v in value]
    if isinstance(value, str):
        return aliases.get(value, value)
    return value


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PlumioConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    aliases = _aliases(entry, coordinator.data)
    data = _pseudonymize(asdict(coordinator.data), aliases)
    data["stale"] = sorted(data["stale"])
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": _pseudonymize(dict(entry.options), aliases),
        "stream_connected": coordinator.stream_connected,
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(data, TO_REDACT),
    }
