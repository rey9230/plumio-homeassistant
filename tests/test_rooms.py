"""Room of each tag: found through Bermuda (or a chosen sensor), shown, and told to Plumio."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, call

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.plumio.api import PlumioConnectionError
from custom_components.plumio.const import CONF_BERMUDA_AUTO_ADD, CONF_ROOM_SOURCES
from custom_components.plumio.rooms import ibeacon_id

from .conftest import snapshot

BEACON = "a923b4a3931044499732a63c687d4576_1_7"
KEYS = {"id": "t-keys", "name": "Llaves", "icon": "keys", "lat": 27.9, "lng": -82.4, "hardwareId": "1-7"}


async def _flush(hass: HomeAssistant) -> None:
    for _ in range(3):
        await asyncio.sleep(0.02)
        await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _flush(hass)


def _bermuda_area(hass: HomeAssistant, state: str) -> str:
    """What Bermuda creates for a beacon it tracks: an Area sensor whose unique id is the beacon."""
    entity = er.async_get(hass).async_get_or_create("sensor", "bermuda", BEACON, suggested_object_id="keys_area")
    hass.states.async_set(entity.entity_id, state)
    return entity.entity_id


@pytest.fixture
def client_with_keys(client: AsyncMock) -> AsyncMock:
    client.snapshot.return_value = snapshot(tags=[KEYS])
    client.set_tag_room = AsyncMock()
    return client


def test_ibeacon_id_is_what_bermuda_calls_the_beacon() -> None:
    assert ibeacon_id("1-7") == BEACON
    assert ibeacon_id("02-0010") == "a923b4a3931044499732a63c687d4576_2_10"
    assert ibeacon_id(None) is None
    assert ibeacon_id("abc") is None
    assert ibeacon_id("1-") is None


async def test_room_follows_bermuda_and_plumio_hears_it(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    area = _bermuda_area(hass, "Cocina")
    await _setup(hass, entry)

    room = hass.states.get("sensor.llaves_room")
    assert room.state == "Cocina"
    assert room.attributes["source"] == area
    client_with_keys.set_tag_room.assert_awaited_once_with("t-keys", "Cocina")

    hass.states.async_set(area, "Sala")
    await _flush(hass)
    assert hass.states.get("sensor.llaves_room").state == "Sala"

    # Out of range of every proxy: no room, and Plumio is told so.
    hass.states.async_set(area, "unknown")
    await _flush(hass)
    assert hass.states.get("sensor.llaves_room").state == "unknown"
    assert client_with_keys.set_tag_room.await_args_list == [
        call("t-keys", "Cocina"),
        call("t-keys", "Sala"),
        call("t-keys", None),
    ]


async def test_room_is_said_again_so_plumio_does_not_forget_it(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    _bermuda_area(hass, "Cocina")
    await _setup(hass, entry)
    assert client_with_keys.set_tag_room.await_count == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))
    await _flush(hass)
    assert client_with_keys.set_tag_room.await_count == 2


async def test_a_failed_report_is_retried_on_the_next_change(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    client_with_keys.set_tag_room.side_effect = [PlumioConnectionError("down"), None]
    area = _bermuda_area(hass, "Cocina")
    await _setup(hass, entry)

    hass.states.async_set(area, "Cocina", {"changed": True})  # same room: nothing new to say…
    await _flush(hass)
    assert client_with_keys.set_tag_room.await_count == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))  # …until the reconfirmation
    await _flush(hass)
    assert client_with_keys.set_tag_room.await_count == 2


async def test_bermuda_appears_after_the_tag(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    await _setup(hass, entry)
    assert hass.states.get("sensor.llaves_room").state == "unknown"

    # Bermuda heard the beacon for the first time; the next poll finds its sensor.
    _bermuda_area(hass, "Garaje")
    await entry.runtime_data.async_refresh()
    await _flush(hass)
    assert hass.states.get("sensor.llaves_room").state == "Garaje"


async def test_tags_are_added_to_bermuda_once(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    bermuda = MockConfigEntry(domain="bermuda", options={"configured_devices": ["AA:BB:CC:DD:EE:FF"]})
    bermuda.add_to_hass(hass)
    await _setup(hass, entry)
    assert bermuda.options["configured_devices"] == ["AA:BB:CC:DD:EE:FF", BEACON.upper()]

    await entry.runtime_data.async_refresh()
    await _flush(hass)
    assert bermuda.options["configured_devices"] == ["AA:BB:CC:DD:EE:FF", BEACON.upper()]


async def test_adding_to_bermuda_can_be_switched_off(
    hass: HomeAssistant, client_with_keys: AsyncMock, entry: MockConfigEntry
) -> None:
    bermuda = MockConfigEntry(domain="bermuda", options={"configured_devices": []})
    bermuda.add_to_hass(hass)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_BERMUDA_AUTO_ADD: False})
    await _setup(hass, entry)
    assert bermuda.options["configured_devices"] == []


async def test_a_chosen_sensor_wins_over_bermuda(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    _bermuda_area(hass, "Cocina")
    hass.states.async_set("sensor.espresense_keys", "Despacho")
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ROOM_SOURCES: {"t-keys": "sensor.espresense_keys"}})
    await _setup(hass, entry)

    assert hass.states.get("sensor.llaves_room").state == "Despacho"
    client_with_keys.set_tag_room.assert_awaited_once_with("t-keys", "Despacho")


async def test_without_a_local_sensor_it_shows_what_plumio_knows(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    client_with_keys.snapshot.return_value = snapshot(tags=[KEYS | {"room": "Sala"}])
    await _setup(hass, entry)
    assert hass.states.get("sensor.llaves_room").state == "Sala"
    # Nothing local to report: Plumio is not told back what it said.
    client_with_keys.set_tag_room.assert_not_awaited()


async def test_options_let_you_pick_a_room_sensor_per_tag(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_keys: AsyncMock
) -> None:
    await _setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"home_from_places": True, "max_gps_accuracy": 200, "bermuda_auto_add": False}
    )
    assert result["step_id"] == "rooms"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"Llaves": "sensor.room_keys"})
    assert entry.options[CONF_ROOM_SOURCES] == {"t-keys": "sensor.room_keys"}
    assert entry.options[CONF_BERMUDA_AUTO_ADD] is False
