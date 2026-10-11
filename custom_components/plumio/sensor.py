"""Sensors for members, places, tags and the Nest."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.location import distance

from .coordinator import PlumioConfigEntry, PlumioCoordinator, parse_ts
from .entity import MemberEntity, NestEntity, PlaceEntity, TagEntity, async_add_as_they_appear

ACTIVITIES = ["still", "walking", "running", "on_bicycle", "in_vehicle", "unknown"]


@dataclass(frozen=True, kw_only=True)
class MemberSensorDescription(SensorEntityDescription):
    """`value` reads from the member dict; `premium` ones need the Nest to have Premium.

    They are still created on a free Nest, unavailable: seeing what is there to unlock
    is the point.
    """

    value: Callable[[dict[str, Any]], Any]
    premium: bool = False


def _activity(member: dict[str, Any]) -> str | None:
    raw = member.get("userActivity")
    if not raw:
        return None
    value = str(raw).lower()
    return value if value in ACTIVITIES else "unknown"


MEMBER_SENSORS: tuple[MemberSensorDescription, ...] = (
    MemberSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda m: m.get("batteryLevel"),
    ),
    MemberSensorDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        premium=True,
        value=lambda m: m.get("speed"),
    ),
    MemberSensorDescription(
        key="activity",
        device_class=SensorDeviceClass.ENUM,
        options=ACTIVITIES,
        premium=True,
        value=_activity,
    ),
    MemberSensorDescription(key="place", value=lambda m: m.get("placeName")),
    MemberSensorDescription(
        key="place_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda m: parse_ts(m.get("placeSince")),
    ),
    MemberSensorDescription(
        key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda m: parse_ts(m.get("lastSeenAt")),
    ),
    MemberSensorDescription(
        key="location_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        premium=True,
        value=lambda m: parse_ts(m.get("locationUpdatedAt")),
    ),
    MemberSensorDescription(
        key="heading",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        premium=True,
        value=lambda m: m.get("heading"),
    ),
    MemberSensorDescription(
        key="gps_accuracy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        premium=True,
        value=lambda m: m.get("accuracy"),
    ),
)


@dataclass(frozen=True, kw_only=True)
class TripSensorDescription(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]


TRIP_SENSORS: tuple[TripSensorDescription, ...] = (
    TripSensorDescription(
        key="last_trip_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value=lambda t: t.get("distanceMeters"),
    ),
    TripSensorDescription(
        key="last_trip_max_speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=0,
        value=lambda t: t.get("maxSpeed"),
    ),
    TripSensorDescription(
        key="last_trip_ended",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda t: parse_ts(t.get("endedAt")),
    ),
    TripSensorDescription(
        key="last_trip_events",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda t: (
            None
            if not t
            else int(t.get("hardBrakingCount") or 0) + int(t.get("rapidAccelCount") or 0) + int(t.get("speedingCount") or 0)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PlumioConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data

    def member_sensors(user_id: str) -> list[SensorEntity]:
        sensors: list[SensorEntity] = [MemberSensor(coordinator, user_id, d) for d in MEMBER_SENSORS]
        sensors.append(DistanceFromHomeSensor(coordinator, user_id))
        sensors.extend(TripSensor(coordinator, user_id, d) for d in TRIP_SENSORS)
        return sensors

    async_add_entities([MembersHomeSensor(coordinator), PlanSensor(coordinator)])
    async_add_as_they_appear(
        coordinator,
        async_add_entities,
        members=member_sensors,
        places=lambda place_id: [PlaceOccupancySensor(coordinator, place_id)],
        tags=lambda tag_id: [TagBatterySensor(coordinator, tag_id), TagLastSeenSensor(coordinator, tag_id)],
    )


class MemberSensor(MemberEntity, SensorEntity):
    entity_description: MemberSensorDescription

    def __init__(self, coordinator: PlumioCoordinator, user_id: str, description: MemberSensorDescription) -> None:
        super().__init__(coordinator, user_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.premium and not self.coordinator.data.has_location:
            return False
        return super().available

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.member)


class DistanceFromHomeSensor(MemberEntity, SensorEntity):
    """Straight-line distance to where Home Assistant lives. Unknown while paused."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_suggested_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_suggested_display_precision = 1
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PlumioCoordinator, user_id: str) -> None:
        super().__init__(coordinator, user_id, "distance_from_home")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.has_location

    @property
    def native_value(self) -> float | None:
        lat, lng = self.member.get("lat"), self.member.get("lng")
        if lat is None or lng is None or self.member.get("approximate"):
            return None
        return distance(self.hass.config.latitude, self.hass.config.longitude, lat, lng)


class TripSensor(MemberEntity, SensorEntity):
    """About the member's last trip. Premium: unavailable on a free Nest."""

    entity_description: TripSensorDescription

    def __init__(self, coordinator: PlumioCoordinator, user_id: str, description: TripSensorDescription) -> None:
        super().__init__(coordinator, user_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data.capabilities.get("trips"))

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data.last_trip.get(self.user_id) or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        trip = self.coordinator.data.last_trip.get(self.user_id) or {}
        if self.entity_description.key != "last_trip_ended" or not trip:
            return None
        return {
            "started": trip.get("startedAt"),
            "origin": trip.get("originName"),
            "destination": trip.get("destName"),
            "hard_braking": trip.get("hardBrakingCount"),
            "rapid_acceleration": trip.get("rapidAccelCount"),
            "speeding": trip.get("speedingCount"),
        }


class MembersHomeSensor(NestEntity, SensorEntity):
    """How many members are at a place of type Home."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "members_home")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.members_home())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"members": sorted(m.get("displayName", "") for m in self.coordinator.data.members_home())}


class PlanSensor(NestEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["free", "premium", "paused"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "plan")

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        if data.paused:
            return "paused"
        return "premium" if data.capabilities.get("premium") else "free"


class PlaceOccupancySensor(PlaceEntity, SensorEntity):
    """How many members are at this place right now, and who."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PlumioCoordinator, place_id: str) -> None:
        super().__init__(coordinator, place_id, "occupancy")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.members_at(self.place_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        place = self.place
        return {
            "members": sorted(m.get("displayName", "") for m in self.coordinator.data.members_at(self.place_id)),
            "latitude": place.get("lat"),
            "longitude": place.get("lng"),
            "radius": place.get("radiusMeters"),
            "place_type": place.get("type"),
        }


class TagBatterySensor(TagEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_suggested_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PlumioCoordinator, tag_id: str) -> None:
        super().__init__(coordinator, tag_id, "tag_battery")

    @property
    def native_value(self) -> int | None:
        return self.tag.get("batteryMv")


class TagLastSeenSensor(TagEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: PlumioCoordinator, tag_id: str) -> None:
        super().__init__(coordinator, tag_id, "tag_last_seen")

    @property
    def native_value(self) -> datetime | None:
        return parse_ts(self.tag.get("lastSeenAt"))
