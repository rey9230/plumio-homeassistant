"""Domain services: actions on members, place management and read-only queries."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .actions import run_action
from .const import ATTR_PLACE_ID, DOMAIN
from .coordinator import PlumioCoordinator

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_RADIUS = "radius"
ATTR_PLACE_TYPE = "place_type"
ATTR_LIMIT = "limit"
ATTR_DATE = "date"

# Lowercase here (Home Assistant translation keys); Plumio's API wants them uppercase.
PLACE_TYPES = ["home", "work", "school", "custom"]

MEMBER_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})
ENTRY_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})

CREATE_PLACE_SCHEMA = ENTRY_SCHEMA.extend(
    {
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1, max=60)),
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        vol.Required(ATTR_RADIUS): vol.All(vol.Coerce(float), vol.Range(min=1, max=50000)),
        vol.Optional(ATTR_PLACE_TYPE, default="custom"): vol.In(PLACE_TYPES),
    }
)
UPDATE_PLACE_SCHEMA = ENTRY_SCHEMA.extend(
    {
        vol.Required(ATTR_PLACE_ID): cv.string,
        vol.Optional(ATTR_NAME): vol.All(cv.string, vol.Length(min=1, max=60)),
        vol.Inclusive(ATTR_LATITUDE, "coords"): cv.latitude,
        vol.Inclusive(ATTR_LONGITUDE, "coords"): cv.longitude,
        vol.Optional(ATTR_RADIUS): vol.All(vol.Coerce(float), vol.Range(min=1, max=50000)),
        vol.Optional(ATTR_PLACE_TYPE): vol.In(PLACE_TYPES),
    }
)
DELETE_PLACE_SCHEMA = ENTRY_SCHEMA.extend({vol.Required(ATTR_PLACE_ID): cv.string})
TRIPS_SCHEMA = MEMBER_SCHEMA.extend({vol.Optional(ATTR_LIMIT, default=20): vol.All(int, vol.Range(min=1, max=200))})
TIMELINE_SCHEMA = MEMBER_SCHEMA.extend({vol.Optional(ATTR_DATE): cv.date})


def _loaded_coordinators(hass: HomeAssistant) -> list[PlumioCoordinator]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def _coordinator_for_entry(hass: HomeAssistant, call: ServiceCall) -> PlumioCoordinator:
    """The Nest a call is about. With a single linked Nest there is nothing to choose."""
    coordinators = _loaded_coordinators(hass)
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id is not None:
        for coordinator in coordinators:
            if coordinator.config_entry.entry_id == entry_id:
                return coordinator
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nest_not_found")
    if len(coordinators) == 1:
        return coordinators[0]
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nest_ambiguous")


def _member_for_device(hass: HomeAssistant, call: ServiceCall) -> tuple[PlumioCoordinator, str]:
    """Resolve a member device to (its Nest, the Plumio user id)."""
    device = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    if device is not None:
        for coordinator in _loaded_coordinators(hass):
            prefix = f"{coordinator.nest_id}_member_"
            for domain, ident in device.identifiers:
                if domain == DOMAIN and ident.startswith(prefix):
                    return coordinator, ident.removeprefix(prefix)
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="member_not_found")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register every Plumio service."""

    async def request_location(call: ServiceCall) -> None:
        coordinator, user_id = _member_for_device(hass, call)
        await run_action(coordinator.client.request_location(user_id))

    async def ring_phone(call: ServiceCall) -> None:
        coordinator, user_id = _member_for_device(hass, call)
        await run_action(coordinator.client.ring(user_id))

    async def stop_ring(call: ServiceCall) -> None:
        coordinator, user_id = _member_for_device(hass, call)
        await run_action(coordinator.client.stop_ring(user_id))

    async def create_place(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_for_entry(hass, call)
        place = await run_action(
            coordinator.client.create_place(
                {
                    "name": call.data[ATTR_NAME],
                    "lat": call.data[ATTR_LATITUDE],
                    "lng": call.data[ATTR_LONGITUDE],
                    "radiusMeters": call.data[ATTR_RADIUS],
                    "type": call.data[ATTR_PLACE_TYPE].upper(),
                }
            )
        )
        await coordinator.async_request_refresh()
        return {"place": place} if call.return_response else None

    async def update_place(call: ServiceCall) -> None:
        coordinator = _coordinator_for_entry(hass, call)
        changes: dict[str, Any] = {}
        for attr, field in (
            (ATTR_NAME, "name"),
            (ATTR_LATITUDE, "lat"),
            (ATTR_LONGITUDE, "lng"),
            (ATTR_RADIUS, "radiusMeters"),
            (ATTR_PLACE_TYPE, "type"),
        ):
            if attr in call.data:
                value = call.data[attr]
                changes[field] = value.upper() if attr == ATTR_PLACE_TYPE else value
        await run_action(coordinator.client.update_place(call.data[ATTR_PLACE_ID], changes))
        await coordinator.async_request_refresh()

    async def delete_place(call: ServiceCall) -> None:
        coordinator = _coordinator_for_entry(hass, call)
        await run_action(coordinator.client.delete_place(call.data[ATTR_PLACE_ID]))
        await coordinator.async_request_refresh()

    async def import_zones(call: ServiceCall) -> ServiceResponse:
        """Copy Home Assistant zones into the Nest as places, skipping names it already has."""
        coordinator = _coordinator_for_entry(hass, call)
        existing = {str(p.get("name", "")).casefold() for p in coordinator.data.places.values()}
        created: list[str] = []
        for state in hass.states.async_all("zone"):
            name = state.name
            lat, lng = state.attributes.get(ATTR_LATITUDE), state.attributes.get(ATTR_LONGITUDE)
            if lat is None or lng is None or name.casefold() in existing or state.attributes.get("passive"):
                continue
            await run_action(
                coordinator.client.create_place(
                    {
                        "name": name[:60],
                        "lat": lat,
                        "lng": lng,
                        "radiusMeters": float(state.attributes.get(ATTR_RADIUS) or 100),
                        "type": "HOME" if state.entity_id == "zone.home" else "CUSTOM",
                    }
                )
            )
            existing.add(name.casefold())
            created.append(name)
        if created:
            await coordinator.async_request_refresh()
        return {"created": created} if call.return_response else None

    async def get_trips(call: ServiceCall) -> ServiceResponse:
        coordinator, user_id = _member_for_device(hass, call)
        return {"trips": await run_action(coordinator.client.trips(user_id, call.data[ATTR_LIMIT]))}

    async def get_driving_summary(call: ServiceCall) -> ServiceResponse:
        coordinator, user_id = _member_for_device(hass, call)
        return await run_action(coordinator.client.driving_summary(user_id, hass.config.time_zone))

    async def get_day_timeline(call: ServiceCall) -> ServiceResponse:
        coordinator, user_id = _member_for_device(hass, call)
        day = call.data.get(ATTR_DATE) or dt_util.now().date()
        start = dt_util.as_utc(datetime.combine(day, datetime.min.time(), dt_util.get_default_time_zone()))
        end = start + timedelta(days=1)
        return await run_action(
            coordinator.client.day_timeline(
                user_id, start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")
            )
        )

    register = hass.services.async_register
    register(DOMAIN, "request_location", request_location, schema=MEMBER_SCHEMA)
    register(DOMAIN, "ring_phone", ring_phone, schema=MEMBER_SCHEMA)
    register(DOMAIN, "stop_ring", stop_ring, schema=MEMBER_SCHEMA)
    register(
        DOMAIN, "create_place", create_place, schema=CREATE_PLACE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    register(DOMAIN, "update_place", update_place, schema=UPDATE_PLACE_SCHEMA)
    register(DOMAIN, "delete_place", delete_place, schema=DELETE_PLACE_SCHEMA)
    register(
        DOMAIN, "import_zones", import_zones, schema=ENTRY_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    register(DOMAIN, "get_trips", get_trips, schema=TRIPS_SCHEMA, supports_response=SupportsResponse.ONLY)
    register(
        DOMAIN, "get_driving_summary", get_driving_summary, schema=MEMBER_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    register(
        DOMAIN, "get_day_timeline", get_day_timeline, schema=TIMELINE_SCHEMA, supports_response=SupportsResponse.ONLY
    )
