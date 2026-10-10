"""State for one linked Nest: a snapshot kept current by the event stream."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
import random
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import STREAM_OPEN, PlumioAuthError, PlumioClient, PlumioConnectionError, PlumioError, SseEvent
from .const import (
    ATTR_MEMBER_ID,
    ATTR_NEST_ID,
    CONF_NEST_ID,
    DOMAIN,
    EVENT_ARRIVAL,
    EVENT_DEPARTURE,
    EVENT_MEMBER,
    EVENT_MEMBER_BACK,
    EVENT_MEMBER_STALE,
    EVENT_PLUMIO,
    EVENT_RESYNC,
    EVENT_SOS,
    EVENT_SOS_RESOLVED,
    EVENT_TAG_SEEN,
    EVENT_TRIP_COMPLETED,
    POLL_INTERVAL_STREAM_DOWN,
    POLL_INTERVAL_STREAM_UP,
    STALE_AFTER,
    STREAM_BACKOFF_MAX,
    STREAM_BACKOFF_MIN,
    STREAM_READ_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

type PlumioConfigEntry = ConfigEntry[PlumioCoordinator]

# (event type, member id or None, payload)
EventListener = Callable[[str, str | None, dict[str, Any]], None]


@dataclass(slots=True)
class PlumioData:
    """Everything the entities read. Keys are Plumio ids."""

    nest: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, bool] = field(default_factory=dict)
    members: dict[str, dict[str, Any]] = field(default_factory=dict)
    places: dict[str, dict[str, Any]] = field(default_factory=dict)
    tags: dict[str, dict[str, Any]] = field(default_factory=dict)
    sos: dict[str, dict[str, Any]] = field(default_factory=dict)
    stale: set[str] = field(default_factory=set)
    last_trip: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def paused(self) -> bool:
        return bool(self.nest.get("paused"))

    def members_at(self, place_id: str) -> list[dict[str, Any]]:
        return [m for m in self.members.values() if m.get("placeId") == place_id]

    def members_home(self) -> list[dict[str, Any]]:
        home_ids = {pid for pid, p in self.places.items() if p.get("type") == "HOME" and not p.get("disabled")}
        return [m for m in self.members.values() if m.get("placeId") in home_ids]


def parse_ts(value: Any) -> datetime | None:
    """ISO-8601 from the API to an aware datetime (None when absent or malformed)."""
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


def snapshot_to_data(raw: dict[str, Any], previous: PlumioData | None, now: datetime) -> PlumioData:
    """Build the state from a full snapshot, carrying over what only events tell us."""
    members = {m["userId"]: dict(m) for m in raw.get("members", [])}
    stale: set[str] = set()
    for user_id, member in members.items():
        seen = parse_ts(member.get("locationUpdatedAt"))
        if member.get("sharing") and seen is not None and now - seen > STALE_AFTER:
            stale.add(user_id)
    last_trip = {k: v for k, v in (previous.last_trip if previous else {}).items() if k in members}
    return PlumioData(
        nest=dict(raw.get("nest", {})),
        capabilities=dict(raw.get("capabilities", {})),
        members=members,
        places={p["id"]: dict(p) for p in raw.get("places", [])},
        tags={t["id"]: dict(t) for t in raw.get("tags", [])},
        sos={s["id"]: dict(s) for s in raw.get("activeSos", [])},
        stale=stale,
        last_trip=last_trip,
    )


def apply_event(data: PlumioData, event: str, user_id: str | None, payload: dict[str, Any], ts: Any) -> bool:
    """Fold one stream event into the state. Returns False when a full resync is needed."""
    if event == EVENT_MEMBER:
        if user_id is None:
            return True
        current = data.members.get(user_id)
        if current is None:
            return False  # someone joined (or was un-excluded): only a snapshot knows the rest
        current.update(payload)
        if not payload.get("sharing", True) or payload.get("approximate"):
            current.update(placeId=None, placeName=None, placeSince=None)
        if payload.get("locationUpdatedAt"):
            data.stale.discard(user_id)
    elif event == EVENT_ARRIVAL and user_id in data.members:
        data.members[user_id].update(
            placeId=payload.get("placeId") or None, placeName=payload.get("placeName"), placeSince=ts
        )
    elif event == EVENT_DEPARTURE and user_id in data.members:
        member = data.members[user_id]
        left = payload.get("placeId") or None
        if left is None or member.get("placeId") == left:
            member.update(placeId=None, placeName=None, placeSince=None)
    elif event == EVENT_SOS:
        if sos_id := payload.get("sosId"):
            data.sos[sos_id] = {"id": sos_id, "userId": user_id, "createdAt": ts}
    elif event == EVENT_SOS_RESOLVED:
        data.sos.pop(payload.get("sosId", ""), None)
    elif event == EVENT_MEMBER_STALE and user_id:
        data.stale.add(user_id)
    elif event == EVENT_MEMBER_BACK and user_id:
        data.stale.discard(user_id)
    elif event == EVENT_TRIP_COMPLETED and user_id:
        data.last_trip[user_id] = dict(payload)
    elif event == EVENT_TAG_SEEN:
        tag = data.tags.get(payload.get("tagId", ""))
        if tag is None:
            return False
        tag.update({k: payload[k] for k in ("lat", "lng", "accuracy", "lastSeenAt", "batteryMv") if k in payload})
    return True


class PlumioCoordinator(DataUpdateCoordinator[PlumioData]):
    """Owns the snapshot poll and the long-lived event stream."""

    config_entry: PlumioConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PlumioConfigEntry, client: PlumioClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=POLL_INTERVAL_STREAM_DOWN,
            always_update=True,
        )
        self.client = client
        self.nest_id: str = entry.data[CONF_NEST_ID]
        # Registry id of the Nest's device; members, places and tags hang from it.
        self.nest_device_id: str | None = None
        self.stream_connected = False
        self._ever_connected = False
        self._last_event_id: str | None = None
        self._stream_task: asyncio.Task[None] | None = None
        self._event_listeners: list[EventListener] = []

    # ---------- snapshot ----------

    async def _async_update_data(self) -> PlumioData:
        try:
            raw = await self.client.snapshot()
        except PlumioAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PlumioError as err:
            raise UpdateFailed(str(err)) from err
        data = snapshot_to_data(raw, self.data, dt_util.utcnow())
        if data.capabilities.get("trips"):
            await self._load_last_trips(data)
        self._remove_gone_devices(data)
        return data

    async def _load_last_trips(self, data: PlumioData) -> None:
        """Last trip per member, once. After that `trip_completed` keeps it current."""
        for user_id in data.members:
            if user_id in data.last_trip:
                continue
            try:
                trips = await self.client.trips(user_id, limit=1)
            except PlumioError:
                continue
            data.last_trip[user_id] = trips[0] if trips else {}

    def _remove_gone_devices(self, data: PlumioData) -> None:
        """Members, places and tags that left the Nest take their devices with them."""
        prefix = f"{self.nest_id}_"
        keep = {self.nest_id}
        keep |= {f"{prefix}member_{i}" for i in data.members}
        keep |= {f"{prefix}place_{i}" for i in data.places}
        keep |= {f"{prefix}tag_{i}" for i in data.tags}
        # A paused Nest reports nobody; that is not the same as everybody leaving.
        if data.paused:
            return
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(registry, self.config_entry.entry_id):
            ours = {ident for domain, ident in device.identifiers if domain == DOMAIN}
            if ours and not ours & keep:
                registry.async_update_device(device.id, remove_config_entry_id=self.config_entry.entry_id)

    # ---------- stream ----------

    def start_stream(self) -> None:
        self._stream_task = self.config_entry.async_create_background_task(
            self.hass, self._stream_loop(), name=f"{DOMAIN} stream {self.nest_id}"
        )

    async def async_shutdown(self) -> None:
        if self._stream_task is not None:
            self._stream_task.cancel()
            self._stream_task = None
        await super().async_shutdown()

    async def _stream_loop(self) -> None:
        backoff = STREAM_BACKOFF_MIN
        while True:
            try:
                async for event in self.client.events(self._last_event_id, STREAM_READ_TIMEOUT):
                    if not self.stream_connected:
                        self._set_stream_connected(True)
                    backoff = STREAM_BACKOFF_MIN
                    if event.event != STREAM_OPEN:
                        await self._handle_stream_event(event)
                # The server closed the stream cleanly (link revoked, deploy…): reconnect.
            except PlumioAuthError:
                self._set_stream_connected(False)
                self.config_entry.async_start_reauth(self.hass)
                return
            except PlumioConnectionError as err:
                _LOGGER.debug("Plumio stream dropped: %s", err)
            except PlumioError as err:
                _LOGGER.warning("Plumio stream refused: %s", err)
            self._set_stream_connected(False)
            await asyncio.sleep(backoff + random.uniform(0, backoff / 2))
            backoff = min(backoff * 2, STREAM_BACKOFF_MAX)

    def _set_stream_connected(self, connected: bool) -> None:
        if self.stream_connected == connected:
            return
        self.stream_connected = connected
        self.update_interval = POLL_INTERVAL_STREAM_UP if connected else POLL_INTERVAL_STREAM_DOWN
        if connected:
            # With an event id, the server replays what we missed (or says `resync`).
            # Reconnecting without one — the Nest was quiet before the drop — there is
            # nothing to resume from, so one snapshot closes the gap. Not on the very
            # first connect: setup took a snapshot a moment ago.
            if self._ever_connected and self._last_event_id is None:
                self.hass.async_create_task(self.async_request_refresh())
            self._ever_connected = True
        self.async_update_listeners()

    async def _handle_stream_event(self, sse: SseEvent) -> None:
        if sse.id:
            self._last_event_id = sse.id
        if sse.event == EVENT_RESYNC or self.data is None:
            await self.async_request_refresh()
            return
        payload = sse.data.get("data") or {}
        if not isinstance(payload, dict):
            payload = {}
        user_id = sse.data.get("userId")
        if not apply_event(self.data, sse.event, user_id, payload, sse.data.get("ts")):
            await self.async_request_refresh()
        # Not async_set_updated_data: that would push the safety poll back on every event
        # and, in a busy Nest, it would never run.
        self.async_update_listeners()
        if sse.event != EVENT_MEMBER:
            self._announce(sse.event, user_id, payload)

    # ---------- events out ----------

    @callback
    def async_add_event_listener(self, listener: EventListener) -> CALLBACK_TYPE:
        self._event_listeners.append(listener)

        @callback
        def remove() -> None:
            self._event_listeners.remove(listener)

        return remove

    def _announce(self, event: str, user_id: str | None, payload: dict[str, Any]) -> None:
        for listener in list(self._event_listeners):
            listener(event, user_id, payload)
        member = self.data.members.get(user_id or "", {}) if self.data else {}
        self.hass.bus.async_fire(
            EVENT_PLUMIO,
            {
                "type": event,
                ATTR_NEST_ID: self.nest_id,
                ATTR_MEMBER_ID: user_id,
                "member_name": member.get("displayName"),
                **payload,
            },
        )
