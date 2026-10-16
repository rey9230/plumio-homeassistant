"""The blueprints, imported into a real Home Assistant and driven by Plumio events."""

from __future__ import annotations

import asyncio
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.components.automation.config import async_validate_config_item
from homeassistant.components.blueprint import models
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, yaml as yaml_util

from .conftest import CAMILA, RENIEL, FakeStream, member, snapshot

BLUEPRINTS = Path(__file__).parent.parent / "blueprints" / "automation" / "plumio"
ALL = sorted(p.name for p in BLUEPRINTS.glob("*.yaml"))


def _load(name: str) -> models.Blueprint:
    return models.Blueprint(
        yaml_util.load_yaml_dict(BLUEPRINTS / name), expected_domain="automation", schema=BLUEPRINT_SCHEMA
    )


def test_there_are_blueprints() -> None:
    assert len(ALL) >= 10


@pytest.mark.parametrize("name", ALL)
async def test_blueprint_is_valid_with_only_the_required_inputs(hass: HomeAssistant, name: str) -> None:
    """What a user gets after filling in only the mandatory fields must be a valid automation."""
    bp = _load(name)
    assert bp.metadata["source_url"].endswith(f"/blueprints/automation/plumio/{name}")
    required = {
        key: _sample(spec) for key, spec in bp.inputs.items() if not (isinstance(spec, dict) and "default" in spec)
    }
    inputs = models.BlueprintInputs(bp, {"use_blueprint": {"path": f"plumio/{name}", "input": required}})
    inputs.validate()
    config = inputs.async_substitute()
    config["id"] = name
    assert await async_validate_config_item(hass, name, config) is not None


def _sample(spec: dict[str, Any]) -> Any:
    selector = spec["selector"]
    if "entity" in selector:
        domain = (selector["entity"].get("filter") or [{}])[0].get("domain", "sensor")
        domain = domain[0] if isinstance(domain, list) else domain
        entity = f"{domain}.sample"
        return [entity] if selector["entity"].get("multiple") else entity
    if "action" in selector:
        return []
    if "text" in selector:
        return "notify.family"
    raise AssertionError(f"No sample value for {spec}")


# ---------- behaviour ----------


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, tmp_path: Path, automations: list[dict]
) -> list[ServiceCall]:
    hass.config.config_dir = str(tmp_path)
    shutil.copytree(BLUEPRINTS, tmp_path / "blueprints" / "automation" / "plumio")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _flush(hass)
    calls = async_mock_service(hass, "notify", "family")
    assert await async_setup_component(hass, "automation", {"automation": automations})
    await _flush(hass)
    return calls


async def _flush(hass: HomeAssistant) -> None:
    """The stream is read by a background task: give it and the automations a few turns."""
    for _ in range(3):
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()


def _use(name: str, **inputs: Any) -> dict[str, Any]:
    return {"use_blueprint": {"path": f"plumio/{name}", "input": {"notify_service": "notify.family", **inputs}}}


async def test_place_alert_names_who_and_where(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    calls = await _setup(
        hass, entry, tmp_path, [_use("place_alert.yaml", members=["event.camila_events"], place="escuela")]
    )

    stream.push("arrival", CAMILA, {"placeId": "p-school", "placeName": "Escuela"}, event_id="2-0")
    await _flush(hass)
    stream.push("arrival", CAMILA, {"placeId": "p-gym", "placeName": "Gym"}, event_id="3-0")
    await _flush(hass)

    assert [c.data["message"] for c in calls] == ["Camila arrived at Escuela"]


async def test_sos_turns_lights_red_and_sends_a_critical_notification(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    lights = async_mock_service(hass, "light", "turn_on")
    calls = await _setup(
        hass,
        entry,
        tmp_path,
        [_use("sos_alarm.yaml", members=["binary_sensor.camila_sos"], lights=["light.sala"])],
    )

    stream.push("sos", CAMILA, {"sosId": "s1"}, event_id="2-0")
    await _flush(hass)

    assert calls[0].data["title"] == "SOS · Camila"
    assert calls[0].data["data"]["push"]["sound"]["critical"] == 1
    assert "maps.google.com/?q=27.95,-82.45" in calls[0].data["message"]
    assert lights[0].data["rgb_color"] == [255, 0, 0]

    stream.push("sos_resolved", None, {"sosId": "s1"}, event_id="3-0")
    await _flush(hass)
    assert calls[-1].data["message"] == "Camila's SOS was resolved."


async def test_crash_and_driving_summary(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    calls = await _setup(
        hass,
        entry,
        tmp_path,
        [
            _use("crash_alert.yaml", members=["event.camila_events"]),
            _use("driving_report.yaml", members=["event.camila_events"], only_with_incidents=True),
        ],
    )

    stream.push("crash", CAMILA, {}, event_id="2-0")
    await _flush(hass)
    assert calls[0].data["title"] == "Possible crash · Camila"

    clean = {"distanceMeters": 12000, "maxSpeed": 20.0, "hardBrakingCount": 0, "rapidAccelCount": 0, "speedingCount": 0}
    stream.push("trip_completed", CAMILA, clean, event_id="3-0")
    await _flush(hass)
    assert len(calls) == 1

    stream.push("trip_completed", CAMILA, clean | {"hardBrakingCount": 2, "destName": "Escuela"}, event_id="4-0")
    await _flush(hass)
    message = " ".join(calls[1].data["message"].split())
    assert message == "Camila finished a trip to Escuela: 12.0 km, top speed 72 km/h, 2 incident(s)."

    stream.push("speed_alert", CAMILA, {"kmh": 131.4}, event_id="5-0")
    await _flush(hass)
    assert calls[2].data["message"].strip() == "Camila is going over the speed limit (131 km/h)."


async def test_low_battery_for_phones_and_tags(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    calls = await _setup(
        hass,
        entry,
        tmp_path,
        [_use("low_battery.yaml", members=["event.camila_events"], tags=["sensor.llaves_battery_voltage"])],
    )

    stream.push("low_battery", CAMILA, {"batteryLevel": 9, "threshold": 15}, event_id="2-0")
    await _flush(hass)
    assert calls[0].data["message"].strip() == "Camila's phone is at 9%."

    stream.push("tag_seen", None, {"tagId": "t-keys", "name": "Llaves", "lat": 27.9, "lng": -82.4, "batteryMv": 2400})
    await _flush(hass)
    assert "Llaves" in calls[1].data["message"]


async def test_last_one_out(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    lights_off = async_mock_service(hass, "light", "turn_off")
    await _setup(
        hass,
        entry,
        tmp_path,
        [
            {
                "use_blueprint": {
                    "path": "plumio/house_empty.yaml",
                    "input": {
                        "anyone_home": "binary_sensor.casa_anyone_home",
                        "empty_for": 5,
                        "empty_actions": [{"action": "light.turn_off", "target": {"entity_id": "all"}}],
                    },
                }
            }
        ],
    )

    stream.push("departure", RENIEL, {"placeId": "p-home", "placeName": "Casa"}, event_id="2-0")
    await _flush(hass)
    assert hass.states.get("binary_sensor.casa_anyone_home").state == "off"
    assert not lights_off

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await _flush(hass)
    assert len(lights_off) == 1


async def test_forgot_the_keys(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    # Home is where the keys were last heard.
    await hass.config.async_update(latitude=27.9, longitude=-82.4, radius=100)
    calls = await _setup(
        hass,
        entry,
        tmp_path,
        [_use("forgot_tag.yaml", member="device_tracker.reniel", tags=["device_tracker.llaves"], wait=5)],
    )
    assert hass.states.get("device_tracker.llaves").state == "home"

    stream.push("departure", RENIEL, {"placeId": "p-home", "placeName": "Casa"}, event_id="2-0")
    stream.push("member", RENIEL, {"lat": 28.5, "lng": -81.3, "sharing": True}, event_id="3-0")
    # Not _flush: the automation is now inside its delay, and waiting for it would wait it out.
    await asyncio.sleep(0.2)
    assert hass.states.get("device_tracker.reniel").state != "home"
    # What the server says from now on, for the poll that runs while we wait.
    away = member(RENIEL, "Reniel", lat=28.5, lng=-81.3)
    client.snapshot.return_value = snapshot(members=[away, member(CAMILA, "Camila")])

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await _flush(hass)
    assert calls[0].data["message"] == "Did you forget something? Llaves stayed at home."


async def test_reminder_only_on_the_chosen_days(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, tmp_path: Path
) -> None:
    await hass.config.async_update(latitude=27.9, longitude=-82.4, radius=100)
    now = dt_util.now()
    at = (now + timedelta(minutes=1)).strftime("%H:%M:00")
    today = now.strftime("%a").lower()[:3]
    calls = await _setup(
        hass,
        entry,
        tmp_path,
        [_use("tag_reminder.yaml", tag="device_tracker.llaves", at=at, weekdays=[today])],
    )

    async_fire_time_changed(hass, now + timedelta(minutes=1, seconds=1))
    await _flush(hass)
    assert calls[0].data["message"] == "Don't forget Llaves."


@pytest.fixture
def client_with_owner_home(client: AsyncMock) -> AsyncMock:
    client.snapshot.return_value = snapshot(members=[member(RENIEL, "Reniel", lat=27.9, lng=-82.4)])
    return client


async def test_tag_left_home_without_its_owner(
    hass: HomeAssistant, entry: MockConfigEntry, client_with_owner_home: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    await hass.config.async_update(latitude=27.9, longitude=-82.4, radius=100)
    calls = await _setup(
        hass,
        entry,
        tmp_path,
        [_use("tag_left_home.yaml", tag="device_tracker.llaves", owner="device_tracker.reniel")],
    )
    assert hass.states.get("device_tracker.reniel").state == "home"

    stream.push("tag_seen", None, {"tagId": "t-keys", "name": "Llaves", "lat": 28.5, "lng": -81.3, "accuracy": 10.0})
    await _flush(hass)
    assert calls[0].data["message"] == "Llaves just left home, and you are still there."


async def test_arrival_waits_for_the_door_and_only_for_the_first_one(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream, tmp_path: Path
) -> None:
    hass.states.async_set("binary_sensor.front_door", "off")
    lights = async_mock_service(hass, "light", "turn_on")
    await _setup(
        hass,
        entry,
        tmp_path,
        [
            {
                "use_blueprint": {
                    "path": "plumio/arrival_home.yaml",
                    "input": {
                        "members": ["device_tracker.camila", "device_tracker.reniel"],
                        "only_first": True,
                        "door_sensor": "binary_sensor.front_door",
                        "arrival_actions": [{"action": "light.turn_on", "target": {"entity_id": "light.entrance"}}],
                    },
                }
            }
        ],
    )

    # Reniel is already home, so Camila is not the first one: nothing happens.
    stream.push("arrival", CAMILA, {"placeId": "p-home", "placeName": "Casa"}, event_id="2-0")
    await _flush(hass)
    hass.states.async_set("binary_sensor.front_door", "on")
    await _flush(hass)
    assert not lights

    # Everyone leaves; Reniel comes back first, and the light waits for the door.
    hass.states.async_set("binary_sensor.front_door", "off")
    stream.push("departure", CAMILA, {"placeId": "p-home"}, event_id="3-0")
    stream.push("member", CAMILA, {"lat": 28.5, "lng": -81.3, "sharing": True}, event_id="4-0")
    stream.push("departure", RENIEL, {"placeId": "p-home"}, event_id="5-0")
    stream.push("member", RENIEL, {"lat": 28.5, "lng": -81.3, "sharing": True}, event_id="6-0")
    await _flush(hass)
    stream.push("arrival", RENIEL, {"placeId": "p-home", "placeName": "Casa"}, event_id="7-0")
    await asyncio.sleep(0.2)
    assert not lights
    hass.states.async_set("binary_sensor.front_door", "on")
    await _flush(hass)
    assert lights[0].data["entity_id"] == ["light.entrance"]
