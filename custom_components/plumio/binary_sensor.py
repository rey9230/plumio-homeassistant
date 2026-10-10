"""Binary sensors for members, places and the Nest."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PlumioConfigEntry, PlumioCoordinator, PlumioData
from .entity import MemberEntity, NestEntity, PlaceEntity, async_add_as_they_appear


@dataclass(frozen=True, kw_only=True)
class MemberBinaryDescription(BinarySensorEntityDescription):
    """`is_on` gets the whole state and the member id: some answers live outside the member."""

    is_on: Callable[[PlumioData, str], bool | None]


def _member(data: PlumioData, user_id: str) -> dict[str, Any]:
    return data.members.get(user_id, {})


MEMBER_BINARY_SENSORS: tuple[MemberBinaryDescription, ...] = (
    MemberBinaryDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on=lambda d, u: _member(d, u).get("charging"),
    ),
    MemberBinaryDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d, u: _member(d, u).get("online"),
    ),
    MemberBinaryDescription(
        key="driving",
        device_class=BinarySensorDeviceClass.MOVING,
        is_on=lambda d, u: bool(_member(d, u).get("inTrip")),
    ),
    MemberBinaryDescription(
        key="sharing",
        is_on=lambda d, u: bool(_member(d, u).get("sharing")),
    ),
    MemberBinaryDescription(
        key="approximate",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d, u: bool(_member(d, u).get("approximate")),
    ),
    MemberBinaryDescription(
        key="sos",
        device_class=BinarySensorDeviceClass.SAFETY,
        is_on=lambda d, u: any(s.get("userId") == u for s in d.sos.values()),
    ),
    MemberBinaryDescription(
        key="security_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d, u: bool(_member(d, u).get("securityFlag")),
    ),
    MemberBinaryDescription(
        key="not_reporting",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d, u: u in d.stale,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PlumioConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [StreamConnectedSensor(coordinator), AnyoneHomeSensor(coordinator), EveryoneHomeSensor(coordinator)]
    )
    async_add_as_they_appear(
        coordinator,
        async_add_entities,
        members=lambda user_id: [MemberBinarySensor(coordinator, user_id, d) for d in MEMBER_BINARY_SENSORS],
        places=lambda place_id: [PlaceOccupiedSensor(coordinator, place_id)],
    )


class MemberBinarySensor(MemberEntity, BinarySensorEntity):
    entity_description: MemberBinaryDescription

    def __init__(self, coordinator: PlumioCoordinator, user_id: str, description: MemberBinaryDescription) -> None:
        super().__init__(coordinator, user_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on(self.coordinator.data, self.user_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "security_alert":
            return {"kind": self.member.get("securityFlag")}
        return None


class StreamConnectedSensor(NestEntity, BinarySensorEntity):
    """Is the live connection up? When it is not, data still arrives, a minute late."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "live_connection")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.stream_connected


class AnyoneHomeSensor(NestEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "anyone_home")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.members_home())


class EveryoneHomeSensor(NestEntity, BinarySensorEntity):
    """Everyone who is sharing is home. Someone who paused cannot hold this off forever."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: PlumioCoordinator) -> None:
        super().__init__(coordinator, "everyone_home")

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        sharing = [m for m in data.members.values() if m.get("sharing")]
        home = {m["userId"] for m in data.members_home()}
        return bool(sharing) and all(m["userId"] in home for m in sharing)


class PlaceOccupiedSensor(PlaceEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: PlumioCoordinator, place_id: str) -> None:
        super().__init__(coordinator, place_id, "occupied")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.members_at(self.place_id))
