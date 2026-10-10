"""Base entities and the helper that adds entities as members, places and tags appear."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlumioCoordinator

MANUFACTURER = "Plumio"


def nest_device_id(nest_id: str) -> str:
    return nest_id


def member_device_id(nest_id: str, user_id: str) -> str:
    return f"{nest_id}_member_{user_id}"


def place_device_id(nest_id: str, place_id: str) -> str:
    return f"{nest_id}_place_{place_id}"


def tag_device_id(nest_id: str, tag_id: str) -> str:
    return f"{nest_id}_tag_{tag_id}"


def via_nest(coordinator: PlumioCoordinator) -> dict[str, Any]:
    """Hang a device under its Nest.

    Home Assistant 2026.8 replaced `via_device` (an identifier) with `via_device_id`
    (the registry id). The Nest's device is created at setup, so its id is known here.
    """
    if "via_device_id" in DeviceInfo.__annotations__ and coordinator.nest_device_id:
        return {"via_device_id": coordinator.nest_device_id}
    return {"via_device": (DOMAIN, nest_device_id(coordinator.nest_id))}


class PlumioEntity(CoordinatorEntity[PlumioCoordinator]):
    """Common ground: has_entity_name and one unique id scheme."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PlumioCoordinator, device_ident: str, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_ident}_{key}"
        self._attr_translation_key = key


class NestEntity(PlumioEntity):
    """Something about the Nest as a whole."""

    def __init__(self, coordinator: PlumioCoordinator, key: str) -> None:
        super().__init__(coordinator, nest_device_id(coordinator.nest_id), key)
        nest = coordinator.data.nest
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, nest_device_id(coordinator.nest_id))},
            name=nest.get("name") or "Plumio",
            manufacturer=MANUFACTURER,
            model="Nest",
            entry_type=DeviceEntryType.SERVICE,
        )


class MemberEntity(PlumioEntity):
    """Something about one person. Unavailable once they leave or get excluded."""

    def __init__(self, coordinator: PlumioCoordinator, user_id: str, key: str) -> None:
        super().__init__(coordinator, member_device_id(coordinator.nest_id, user_id), key)
        self.user_id = user_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, member_device_id(coordinator.nest_id, user_id))},
            name=self.member.get("displayName") or "Plumio member",
            manufacturer=MANUFACTURER,
            model="Member",
            **via_nest(coordinator),
        )

    @property
    def member(self) -> dict[str, Any]:
        return self.coordinator.data.members.get(self.user_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.user_id in self.coordinator.data.members


class PlaceEntity(PlumioEntity):
    """Something about one place of the Nest."""

    def __init__(self, coordinator: PlumioCoordinator, place_id: str, key: str) -> None:
        super().__init__(coordinator, place_device_id(coordinator.nest_id, place_id), key)
        self.place_id = place_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, place_device_id(coordinator.nest_id, place_id))},
            name=self.place.get("name") or "Place",
            manufacturer=MANUFACTURER,
            model="Place",
            entry_type=DeviceEntryType.SERVICE,
            **via_nest(coordinator),
        )

    @property
    def place(self) -> dict[str, Any]:
        return self.coordinator.data.places.get(self.place_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.place_id in self.coordinator.data.places


class TagEntity(PlumioEntity):
    """Something about one Bluetooth tag."""

    def __init__(self, coordinator: PlumioCoordinator, tag_id: str, key: str) -> None:
        super().__init__(coordinator, tag_device_id(coordinator.nest_id, tag_id), key)
        self.tag_id = tag_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tag_device_id(coordinator.nest_id, tag_id))},
            name=self.tag.get("name") or "Tag",
            manufacturer=MANUFACTURER,
            model="Plumio Tag",
            **via_nest(coordinator),
        )

    @property
    def tag(self) -> dict[str, Any]:
        return self.coordinator.data.tags.get(self.tag_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.tag_id in self.coordinator.data.tags


@callback
def async_add_as_they_appear(
    coordinator: PlumioCoordinator,
    async_add_entities: Callable[[Iterable[Entity]], None],
    *,
    members: Callable[[str], Iterable[Entity]] | None = None,
    places: Callable[[str], Iterable[Entity]] | None = None,
    tags: Callable[[str], Iterable[Entity]] | None = None,
) -> None:
    """Create entities for every id present now, and for new ids on every update.

    A family changes: someone joins, a place is added, a tag is claimed. None of that
    should need a reload.
    """
    seen: dict[str, set[str]] = {"members": set(), "places": set(), "tags": set()}

    @callback
    def _sync() -> None:
        data = coordinator.data
        new: list[Entity] = []
        for kind, current, factory in (
            ("members", data.members, members),
            ("places", data.places, places),
            ("tags", data.tags, tags),
        ):
            if factory is None:
                continue
            # Forget who left: their device is removed, and if they come back (the admin
            # hides someone and shows them again) they need entities again. A paused Nest
            # reports nobody without anybody leaving, and keeps its devices.
            if not data.paused:
                seen[kind] &= current.keys()
            for ident in current.keys() - seen[kind]:
                seen[kind].add(ident)
                new.extend(factory(ident))
        if new:
            async_add_entities(new)

    _sync()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_sync))
