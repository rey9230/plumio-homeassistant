"""Event entities: what happens to a member, and to the Nest's tags."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import EVENT_TAG_SEEN, MEMBER_EVENT_TYPES
from .coordinator import PlumioConfigEntry, PlumioCoordinator
from .entity import MemberEntity, NestEntity, async_add_as_they_appear


async def async_setup_entry(
    hass: HomeAssistant, entry: PlumioConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([NestEvents(coordinator)])
    async_add_as_they_appear(
        coordinator,
        async_add_entities,
        members=lambda user_id: [MemberEvents(coordinator, user_id)],
    )


class MemberEvents(MemberEntity, EventEntity):
    """Arrivals, departures, SOS, low battery… for one person."""

    _attr_event_types = MEMBER_EVENT_TYPES

    def __init__(self, coordinator: PlumioCoordinator, user_id: str) -> None:
        super().__init__(coordinator, user_id, "activity_events")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_event_listener(self._on_event))

    @callback
    def _on_event(self, event: str, user_id: str | None, payload: dict[str, Any]) -> None:
        if user_id != self.user_id or event not in MEMBER_EVENT_TYPES:
            return
        self._trigger_event(event, _attributes(payload))
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """State only changes on events, not on every location update."""


class NestEvents(NestEntity, EventEntity):
    """Events that belong to no member in particular."""

    _attr_event_types = [EVENT_TAG_SEEN]

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "nest_events")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_event_listener(self._on_event))

    @callback
    def _on_event(self, event: str, user_id: str | None, payload: dict[str, Any]) -> None:
        if event != EVENT_TAG_SEEN:
            return
        self._trigger_event(event, _attributes(payload))
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """State only changes on events."""


def _attributes(payload: dict[str, Any]) -> dict[str, Any]:
    """Server camelCase to the snake_case automations expect."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in key)
        out[snake] = value
    return out
