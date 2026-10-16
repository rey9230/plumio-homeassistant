"""Which room of the house each tag is in, from this Home Assistant's own Bluetooth.

Plumio only knows where a phone was when it heard a tag: GPS, good enough for "at
home", useless for "in the kitchen". Home Assistant can do better: with a Bluetooth
proxy (an ESP32 running ESPHome) in each room and Bermuda working out which one hears
a beacon best, every Plumio tag gets an area.

This module finds, for each tag, the sensor that holds its room (Bermuda's Area
sensor for that iBeacon, or any sensor the user picks in the options), keeps the
tag's Room sensor in step with it, and tells Plumio so the app can show it too.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .api import PlumioError
from .const import (
    BERMUDA_CONFIGURED_DEVICES,
    BERMUDA_DOMAIN,
    CONF_BERMUDA_AUTO_ADD,
    CONF_ROOM_SOURCES,
    DEFAULT_BERMUDA_AUTO_ADD,
    PLUMIO_IBEACON_UUID,
    ROOM_REFRESH_INTERVAL,
)

if TYPE_CHECKING:
    from .coordinator import PlumioCoordinator

_LOGGER = logging.getLogger(__name__)

# States that say "it is not in any room I know of".
_NO_ROOM = {STATE_UNKNOWN, STATE_UNAVAILABLE, "", "none", "not_home", "away"}


def ibeacon_id(hardware_id: str | None) -> str | None:
    """`<model>-<number>` to the iBeacon a Plumio tag sends: UUID_major_minor, as Bermuda names it."""
    if not hardware_id:
        return None
    model, sep, number = hardware_id.partition("-")
    if not sep or not model.isdigit() or not number.isdigit():
        return None
    return f"{PLUMIO_IBEACON_UUID}_{int(model)}_{int(number)}"


def room_from_state(state: State | None) -> str | None:
    """A room name, or None when the sensor does not place it anywhere."""
    if state is None or state.state.strip().lower() in _NO_ROOM:
        return None
    return state.state.strip()


class TagRooms:
    """Room of every tag of one Nest: where it comes from, what it is, and telling Plumio."""

    def __init__(self, hass: HomeAssistant, coordinator: PlumioCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._sources: dict[str, str] = {}
        # What Plumio was last told per tag. Missing = never told since start.
        self._reported: dict[str, str | None] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_states: CALLBACK_TYPE | None = None
        self._offered_to_bermuda: set[str] = set()

    # ---------- reading ----------

    def source(self, tag_id: str) -> str | None:
        """The entity whose state is this tag's room, if there is one."""
        return self._sources.get(tag_id)

    def room(self, tag_id: str) -> str | None:
        """Where the tag is now. From the local sensor when there is one, else what Plumio last heard."""
        if (source := self._sources.get(tag_id)) is not None:
            return room_from_state(self.hass.states.get(source))
        return self.coordinator.data.tags.get(tag_id, {}).get("room")

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    # ---------- lifecycle ----------

    @callback
    def async_start(self) -> None:
        entry = self.coordinator.config_entry
        entry.async_on_unload(self.coordinator.async_add_listener(self._resolve))
        entry.async_on_unload(async_track_time_interval(self.hass, self._reconfirm, ROOM_REFRESH_INTERVAL))
        entry.async_on_unload(self._stop_tracking)
        self._resolve()

    @callback
    def _stop_tracking(self) -> None:
        if self._unsub_states is not None:
            self._unsub_states()
            self._unsub_states = None

    # ---------- finding the sources ----------

    @callback
    def _resolve(self) -> None:
        """Work out each tag's room sensor again: tags come and go, Bermuda finds beacons late."""
        options = self.coordinator.config_entry.options
        chosen: dict[str, str] = dict(options.get(CONF_ROOM_SOURCES) or {})
        registry = er.async_get(self.hass)
        sources: dict[str, str] = {}
        beacons: list[str] = []
        for tag_id, tag in self.coordinator.data.tags.items():
            if entity_id := chosen.get(tag_id):
                sources[tag_id] = entity_id
                continue
            beacon = ibeacon_id(tag.get("hardwareId"))
            if beacon is None:
                continue
            beacons.append(beacon)
            if entity_id := _bermuda_area_sensor(registry, beacon):
                sources[tag_id] = entity_id

        if options.get(CONF_BERMUDA_AUTO_ADD, DEFAULT_BERMUDA_AUTO_ADD):
            self._add_to_bermuda(beacons)

        if sources == self._sources:
            return
        self._sources = sources
        self._stop_tracking()
        if sources:
            self._unsub_states = async_track_state_change_event(
                self.hass, sorted(set(sources.values())), self._on_source_changed
            )
        self._notify()
        for tag_id in sources:
            self._schedule_report(tag_id)

    @callback
    def _add_to_bermuda(self, beacons: list[str]) -> None:
        """Ask Bermuda to track the Nest's tags, so their rooms appear with nothing to set up.

        Only ever adds, and each beacon once per start: if someone takes a tag out of
        Bermuda's list on purpose, it stays out until the next restart, and the option
        switches this off for good.
        """
        new = [b.upper() for b in beacons if b.upper() not in self._offered_to_bermuda]
        if not new:
            return
        self._offered_to_bermuda.update(new)
        for entry in self.hass.config_entries.async_entries(BERMUDA_DOMAIN):
            current = list(entry.options.get(BERMUDA_CONFIGURED_DEVICES) or [])
            missing = [b for b in new if b not in current]
            if missing:
                _LOGGER.info("Adding %d Plumio tag(s) to Bermuda", len(missing))
                self.hass.config_entries.async_update_entry(
                    entry, options={**entry.options, BERMUDA_CONFIGURED_DEVICES: current + missing}
                )

    # ---------- following them ----------

    @callback
    def _on_source_changed(self, event: Event[EventStateChangedData]) -> None:
        old = room_from_state(event.data["old_state"])
        new = room_from_state(event.data["new_state"])
        if old == new:
            return
        self._notify()
        for tag_id, source in self._sources.items():
            if source == event.data["entity_id"]:
                self._schedule_report(tag_id)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ---------- telling Plumio ----------

    @callback
    def _reconfirm(self, _now: Any) -> None:
        """Plumio forgets a room after a while unless it hears it again: say it again."""
        for tag_id in self._sources:
            if self.room(tag_id) is not None:
                self._schedule_report(tag_id, force=True)

    @callback
    def _schedule_report(self, tag_id: str, force: bool = False) -> None:
        self.coordinator.config_entry.async_create_task(
            self.hass, self._report(tag_id, force), f"plumio report room {tag_id}"
        )

    async def _report(self, tag_id: str, force: bool) -> None:
        if not self.coordinator.data.capabilities.get("tags"):
            return
        if tag_id not in self._sources or tag_id not in self.coordinator.data.tags:
            return
        room = self.room(tag_id)
        if not force and tag_id in self._reported and self._reported[tag_id] == room:
            return
        try:
            await self.coordinator.client.set_tag_room(tag_id, room)
        except PlumioError as err:
            # Next change or the next reconfirmation tries again.
            _LOGGER.debug("Could not tell Plumio the room of tag %s: %s", tag_id, err)
            self._reported.pop(tag_id, None)
            return
        self._reported[tag_id] = room


def _bermuda_area_sensor(registry: er.EntityRegistry, beacon: str) -> str | None:
    """Bermuda's Area sensor for an iBeacon has the beacon's id as its unique id."""
    for unique_id in (beacon, beacon.upper()):
        if entity_id := registry.async_get_entity_id("sensor", BERMUDA_DOMAIN, unique_id):
            return entity_id
    return None
