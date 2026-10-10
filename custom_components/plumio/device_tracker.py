"""Device trackers: one per member, one per tag."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HOME_FROM_PLACES,
    CONF_MAX_GPS_ACCURACY,
    DEFAULT_HOME_FROM_PLACES,
    DEFAULT_MAX_GPS_ACCURACY,
    PLACE_TYPE_HOME,
)
from .coordinator import PlumioConfigEntry, PlumioCoordinator
from .entity import MemberEntity, TagEntity, async_add_as_they_appear


async def async_setup_entry(
    hass: HomeAssistant, entry: PlumioConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_as_they_appear(
        coordinator,
        async_add_entities,
        members=lambda user_id: [MemberTracker(coordinator, user_id)],
        tags=lambda tag_id: [TagTracker(coordinator, tag_id)],
    )


class MemberTracker(MemberEntity, TrackerEntity):
    """Where a person is.

    Privacy comes first: someone who paused sharing has no coordinates here (the state
    goes unknown, never "the last place we saw them"), and someone sharing only an
    approximate area shows its centre with the area's radius as accuracy.
    """

    _attr_name = None
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: PlumioCoordinator, user_id: str) -> None:
        super().__init__(coordinator, user_id, "location")
        self._fix: tuple[float, float, int] | None = None
        self._accept_fix()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._accept_fix()
        super()._handle_coordinator_update()

    def _accept_fix(self) -> None:
        """Keep the last good fix when a new one is too imprecise to be worth showing."""
        member = self.member
        lat, lng = member.get("lat"), member.get("lng")
        if not member.get("sharing") or lat is None or lng is None:
            self._fix = None
            return
        accuracy = int(member.get("accuracy") or 0)
        limit = self.coordinator.config_entry.options.get(CONF_MAX_GPS_ACCURACY, DEFAULT_MAX_GPS_ACCURACY)
        if not member.get("approximate") and limit and accuracy > limit and self._fix is not None:
            return
        self._fix = (lat, lng, accuracy)

    @property
    def latitude(self) -> float | None:
        return self._fix[0] if self._fix else None

    @property
    def longitude(self) -> float | None:
        return self._fix[1] if self._fix else None

    @property
    def location_accuracy(self) -> int:
        return self._fix[2] if self._fix else 0

    @property
    def battery_level(self) -> int | None:
        return self.member.get("batteryLevel")

    @property
    def location_name(self) -> str | None:
        """A Plumio place of type Home counts as home, with no zone to configure."""
        if not self.coordinator.config_entry.options.get(CONF_HOME_FROM_PLACES, DEFAULT_HOME_FROM_PLACES):
            return None
        place = self.coordinator.data.places.get(self.member.get("placeId") or "")
        if place and place.get("type") == PLACE_TYPE_HOME and self._fix is not None:
            return STATE_HOME
        return None

    @property
    def entity_picture(self) -> str | None:
        return self.member.get("avatarUrl") or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        member = self.member
        return {
            "place": member.get("placeName"),
            "at_place_since": member.get("placeSince"),
            "speed": member.get("speed"),
            "heading": member.get("heading"),
            "activity": member.get("userActivity"),
            "driving": member.get("inTrip"),
            "sharing": member.get("sharing"),
            "approximate": member.get("approximate"),
            "last_seen": member.get("lastSeenAt"),
            "location_updated": member.get("locationUpdatedAt"),
        }


class TagTracker(TagEntity, TrackerEntity):
    """Where a tag was last heard. It is the position of the phone that heard it."""

    _attr_name = None
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: PlumioCoordinator, tag_id: str) -> None:
        super().__init__(coordinator, tag_id, "tag_location")

    @property
    def latitude(self) -> float | None:
        return self.tag.get("lat")

    @property
    def longitude(self) -> float | None:
        return self.tag.get("lng")

    @property
    def location_accuracy(self) -> int:
        return int(self.tag.get("accuracy") or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"last_seen": self.tag.get("lastSeenAt"), "icon_key": self.tag.get("icon")}
