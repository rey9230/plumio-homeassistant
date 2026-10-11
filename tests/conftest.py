"""Shared fixtures: a fake Plumio server behind the client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.plumio.api import STREAM_OPEN, SseEvent
from custom_components.plumio.const import (
    CONF_API_URL,
    CONF_LINK_ID,
    CONF_NEST_ID,
    CONF_TOKEN,
    DEFAULT_API_URL,
    DOMAIN,
)

NEST_ID = "nest1"
CAMILA = "u-camila"
RENIEL = "u-reniel"
HOME = "p-home"


def member(user_id: str, name: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "userId": user_id,
        "displayName": name,
        "avatarUrl": None,
        "role": "MEMBER",
        "lat": 27.95,
        "lng": -82.45,
        "accuracy": 12.0,
        "speed": 0.0,
        "heading": None,
        "batteryLevel": 80,
        "charging": False,
        "online": True,
        "lastSeenAt": "2026-10-10T12:00:00Z",
        "sharing": True,
        "approximate": False,
        "locationUpdatedAt": "2026-10-10T12:00:00Z",
        "inTrip": False,
        "userActivity": "STILL",
        "securityFlag": None,
        "placeId": None,
        "placeName": None,
        "placeSince": None,
    }
    return base | overrides


def snapshot(**overrides: Any) -> dict[str, Any]:
    base = {
        "linkId": "link1",
        "nest": {"id": NEST_ID, "name": "Casa", "emoji": None, "paused": False},
        "capabilities": {
            "premium": True,
            "location": True,
            "history": True,
            "trips": True,
            "tags": True,
            "actions": True,
            "managePlaces": True,
        },
        "members": [
            member(RENIEL, "Reniel", role="ADMIN", placeId=HOME, placeName="Casa", placeSince="2026-10-10T08:00:00Z"),
            member(CAMILA, "Camila"),
        ],
        "places": [
            {"id": HOME, "name": "Casa", "type": "HOME", "lat": 27.95, "lng": -82.45, "radiusMeters": 150.0, "disabled": False}
        ],
        "tags": [
            {"id": "t-keys", "name": "Llaves", "icon": "keys", "lat": 27.9, "lng": -82.4, "accuracy": 20.0, "lastSeenAt": "2026-10-10T11:00:00Z", "batteryMv": 3010}
        ],
        "activeSos": [],
    }
    return base | overrides


class FakeStream:
    """Stands in for the SSE connection: tests push events, the coordinator reads them."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[SseEvent] = asyncio.Queue()
        self.last_event_ids: list[str | None] = []

    async def events(self, last_event_id: str | None, read_timeout: float) -> AsyncIterator[SseEvent]:
        self.last_event_ids.append(last_event_id)
        yield SseEvent(event=STREAM_OPEN, data={}, id=None)
        while True:
            yield await self.queue.get()

    def push(self, event: str, user_id: str | None = None, data: dict[str, Any] | None = None, event_id: str = "1-0") -> None:
        body = {"type": event, "userId": user_id, "data": data or {}, "ts": "2026-10-10T12:30:00Z"}
        self.queue.put_nowait(SseEvent(event=event, data=body, id=event_id))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components/plumio."""


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Casa",
        unique_id=NEST_ID,
        data={CONF_API_URL: DEFAULT_API_URL, CONF_TOKEN: "plm_ha_test", CONF_LINK_ID: "link1", CONF_NEST_ID: NEST_ID},
    )


@pytest.fixture
def stream() -> FakeStream:
    return FakeStream()


@pytest.fixture
def client(stream: FakeStream) -> Generator[AsyncMock]:
    """Patch the client the integration builds; reads return a premium two-member Nest."""
    with patch("custom_components.plumio.PlumioClient", autospec=True) as cls:
        instance = cls.return_value
        instance.snapshot = AsyncMock(return_value=snapshot())
        instance.trips = AsyncMock(return_value=[])
        instance.events = stream.events
        instance.request_location = AsyncMock(return_value=True)
        instance.ring = AsyncMock()
        yield instance
