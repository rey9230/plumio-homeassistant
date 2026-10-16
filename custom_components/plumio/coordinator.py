"""State for one linked Nest: a snapshot kept current by the event stream."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import random
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, issue_registry as ir
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
    PREMIUM_URL,
    POLL_INTERVAL_STREAM_UP,
    STALE_AFTER,
    STREAM_BACKOFF_MAX,
    STREAM_BACKOFF_MIN,
    STREAM_READ_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

type PlumioConfigEntry = ConfigEntry[PlumioCoordinator]

# What a location fix carries and a heartbeat does not.
_LOCATION_KEYS = frozenset({"lat", "lng", "accuracy", "speed", "heading", "locationUpdatedAt", "userActivity"})

# A 401 without the server's "token is dead" code is not proof the link is gone (an
# infrastructure hiccup can surface as one): only this many in a row ask for a new link.
AUTH_STRIKES_BEFORE_REAUTH = 3

# A member whose last trip could not be read is not asked again on every poll.
TRIP_RETRY_AFTER = timedelta(minutes=30)

# What the trip sensors read. Nothing else of a trip is kept: a trip from the API also
# carries its route (polyline, bounding box), and that has no business in the state or
# in diagnostics.
_TRIP_KEYS = (
    "startedAt",
    "endedAt",
    "distanceMeters",
    "maxSpeed",
    "hardBrakingCount",
    "rapidAccelCount",
    "speedingCount",
    "originName",
    "destName",
)


def trip_summary(trip: dict[str, Any] | None) -> dict[str, Any]:
    """Only the fields the trip sensors use."""
    if not trip:
        return {}
    return {k: trip[k] for k in _TRIP_KEYS if k in trip}


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

    @property
    def has_location(self) -> bool:
        """Coordinates, speed and activity: what Premium adds on top of presence.

        Without it the Nest still says who is home, in which place, and their battery.
        """
        return bool(self.capabilities.get("location", True))

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
        if payload.get("sharing", True) and payload.get("lat") is None:
            # A heartbeat: the phone says it is alive (battery, online) and nothing about
            # where it is. Its empty location must not erase the one we have. Pausing is
            # different — `sharing` is false there — and does erase it.
            payload = {k: v for k, v in payload.items() if k not in _LOCATION_KEYS}
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
        data.last_trip[user_id] = trip_summary(payload)
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
        self._auth_strikes = 0
        self._trip_retry_at: dict[str, datetime] = {}

    # ---------- snapshot ----------

    async def _async_update_data(self) -> PlumioData:
        try:
            raw = await self.client.snapshot()
        except PlumioAuthError as err:
            if self._auth_rejected(err):
                raise ConfigEntryAuthFailed(str(err)) from err
            raise UpdateFailed(str(err)) from err
        except PlumioError as err:
            raise UpdateFailed(str(err)) from err
        self._auth_strikes = 0
        data = snapshot_to_data(raw, self.data, dt_util.utcnow())
        if data.capabilities.get("trips"):
            await self._load_last_trips(data)
        self._remove_gone_devices(data)
        self._say_what_premium_unlocks(data)
        return data

    def _say_what_premium_unlocks(self, data: PlumioData) -> None:
        """One notice per free Nest, in Repairs; gone the moment its owner upgrades."""
        issue_id = f"premium_locked_{self.nest_id}"
        if data.capabilities.get("premium") or data.paused:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="premium_locked",
            translation_placeholders={"nest": data.nest.get("name") or self.config_entry.title},
            learn_more_url=PREMIUM_URL,
        )

    def _auth_rejected(self, err: PlumioAuthError) -> bool:
        """True when a 401 means the link is really gone and a new one is needed."""
        if err.definitive:
            return True
        self._auth_strikes += 1
        return self._auth_strikes >= AUTH_STRIKES_BEFORE_REAUTH

    async def _load_last_trips(self, data: PlumioData) -> None:
        """Last trip per member, once. After that `trip_completed` keeps it current.

        All members at once, and one that failed waits a while before being asked again.
        """
        now = dt_util.utcnow()
        todo = [
            user_id
            for user_id in data.members
            if user_id not in data.last_trip and self._trip_retry_at.get(user_id, now) <= now
        ]
        if not todo:
            return
        results = await asyncio.gather(
            *(self.client.trips(user_id, limit=1) for user_id in todo), return_exceptions=True
        )
        for user_id, result in zip(todo, results, strict=True):
            if isinstance(result, PlumioError):
                self._trip_retry_at[user_id] = now + TRIP_RETRY_AFTER
                continue
            if isinstance(result, BaseException):
                raise result
            self._trip_retry_at.pop(user_id, None)
            data.last_trip[user_id] = trip_summary(result[0]) if result else {}

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
                registry.async_remove_device(device.id)

    # ---------- stream ----------

    def start_stream(self) -> None:
        self._stream_task = self.config_entry.async_create_background_task(
            self.hass, self._stream_loop(), name=f"{DOMAIN} stream {self.nest_id}"
        )

    async def async_shutdown(self) -> None:
        ir.async_delete_issue(self.hass, DOMAIN, f"premium_locked_{self.nest_id}")
        if self._stream_task is not None:
            self._stream_task.cancel()
            self._stream_task = None
        await super().async_shutdown()

    async def _stream_loop(self) -> None:
        backoff = STREAM_BACKOFF_MIN
        while True:
            try:
                async for event in self.client.events(self._last_event_id, STREAM_READ_TIMEOUT):
                    self._auth_strikes = 0
                    if not self.stream_connected:
                        self._set_stream_connected(True)
                    backoff = STREAM_BACKOFF_MIN
                    if event.event != STREAM_OPEN:
                        await self._handle_stream_event(event)
                # The server closed the stream cleanly (link revoked, deploy…): reconnect.
            except PlumioAuthError as err:
                if self._auth_rejected(err):
                    self._set_stream_connected(False)
                    self.config_entry.async_start_reauth(self.hass)
                    return
                # Not proof the link is gone: keep trying, with the usual backoff.
                _LOGGER.debug("Plumio stream got a 401 without a reason; retrying")
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
