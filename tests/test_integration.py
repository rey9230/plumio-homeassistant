"""The integration loaded in a real Home Assistant core, against a fake Plumio."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from custom_components.plumio.api import PlumioAuthError, PlumioRequestError
from custom_components.plumio.const import CONF_NEST_ID, CONF_TOKEN, DOMAIN, EVENT_PLUMIO

from .conftest import CAMILA, HOME, NEST_ID, RENIEL, FakeStream, member, snapshot


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# ---------- config flow ----------


async def test_link_flow_waits_for_approval_then_creates_entry(hass: HomeAssistant) -> None:
    pairing = {
        "deviceCode": "dc",
        "userCode": "ABCD-EFGH",
        "verificationUri": "https://www.useplumio.com/link",
        "verificationUriComplete": "https://www.useplumio.com/link/ABCDEFGH",
        "expiresIn": 600,
        "interval": 5,
    }
    approved = {"status": "APPROVED", "token": "plm_ha_x", "linkId": "link1", "nestId": NEST_ID, "nestName": "Casa"}
    with (
        patch("custom_components.plumio.config_flow.PlumioClient", autospec=True) as cls,
        patch("custom_components.plumio.async_setup_entry", return_value=True),
    ):
        api = cls.return_value
        api.pair_start = AsyncMock(return_value=pairing)
        api.pair_poll = AsyncMock(side_effect=[{"status": "PENDING"}, approved])

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"advanced": {}})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "link"
        assert result["description_placeholders"]["code"] == "ABCD-EFGH"

        # Submitting before the admin approved keeps the same code on screen.
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "not_approved_yet"}
        assert api.pair_start.await_count == 1

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Casa"
        assert result["data"][CONF_TOKEN] == "plm_ha_x"
        assert result["data"][CONF_NEST_ID] == NEST_ID


async def test_denied_code_is_replaced_by_a_fresh_one(hass: HomeAssistant) -> None:
    with patch("custom_components.plumio.config_flow.PlumioClient", autospec=True) as cls:
        api = cls.return_value
        api.pair_start = AsyncMock(
            return_value={"deviceCode": "dc", "userCode": "AAAA-BBBB", "verificationUri": "u", "verificationUriComplete": "u/1"}
        )
        api.pair_poll = AsyncMock(return_value={"status": "DENIED"})
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"advanced": {}})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["errors"] == {"base": "denied"}
        assert api.pair_start.await_count == 2


# ---------- entities ----------


async def test_entities_reflect_the_snapshot(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> None:
    await _setup(hass, entry)

    # A Plumio place of type Home is home, with no zone configured.
    assert hass.states.get("device_tracker.reniel").state == "home"
    camila = hass.states.get("device_tracker.camila")
    assert camila.attributes["latitude"] == 27.95
    assert camila.attributes["gps_accuracy"] == 12
    assert hass.states.get("sensor.camila_battery").state == "80"
    assert hass.states.get("sensor.reniel_place").state == "Casa"
    assert hass.states.get("sensor.casa_members_home").state == "1"
    assert hass.states.get("binary_sensor.casa_anyone_home").state == "on"
    assert hass.states.get("binary_sensor.casa_everyone_home").state == "off"
    assert hass.states.get("device_tracker.llaves").attributes["latitude"] == 27.9


async def test_live_connection_is_on_before_any_event(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock
) -> None:
    """A quiet Nest sends nothing for minutes; the connection is still up."""
    await _setup(hass, entry)
    assert hass.states.get("binary_sensor.casa_live_connection").state == "on"


async def test_paused_member_has_no_location_at_all(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> None:
    paused = member(CAMILA, "Camila", sharing=False, lat=None, lng=None, accuracy=None)
    client.snapshot.return_value = snapshot(members=[member(RENIEL, "Reniel"), paused])
    await _setup(hass, entry)

    state = hass.states.get("device_tracker.camila")
    assert state.state == "unknown"
    assert "latitude" not in state.attributes
    assert hass.states.get("binary_sensor.camila_sharing_location").state == "off"
    assert hass.states.get("sensor.camila_distance_from_home").state == "unknown"


async def test_approximate_area_shows_radius_as_accuracy(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> None:
    bubble = member(CAMILA, "Camila", approximate=True, accuracy=1000.0)
    client.snapshot.return_value = snapshot(members=[bubble])
    await _setup(hass, entry)

    # Wider than the "ignore imprecise fixes" limit on purpose: it is an area, not a bad fix.
    assert hass.states.get("device_tracker.camila").attributes["gps_accuracy"] == 1000
    assert hass.states.get("binary_sensor.camila_approximate_area_only").state == "on"


async def test_stream_events_update_state_and_fire_on_the_bus(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    await _setup(hass, entry)
    fired = async_capture_events(hass, EVENT_PLUMIO)

    stream.push("arrival", CAMILA, {"placeId": HOME, "placeName": "Casa", "eventId": "e1"}, event_id="5-0")
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.camila").state == "home"
    assert hass.states.get("binary_sensor.casa_everyone_home").state == "on"
    assert hass.states.get("binary_sensor.casa_live_connection").state == "on"
    assert hass.states.get("event.camila_events").attributes["event_type"] == "arrival"
    assert fired[0].data["type"] == "arrival"
    assert fired[0].data["member_name"] == "Camila"

    stream.push("member", CAMILA, {"lat": 30.0, "lng": -80.0, "sharing": True, "batteryLevel": 9}, event_id="6-0")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.camila_battery").state == "9"
    # Location updates are state, not events: nothing new on the bus.
    assert len(fired) == 1


async def test_heartbeat_without_location_keeps_the_last_fix(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    """Seen against production: a heartbeat arrives with every location field null."""
    await _setup(hass, entry)
    heartbeat = {
        "lat": None, "lng": None, "accuracy": None, "speed": None, "heading": None,
        "locationUpdatedAt": None, "userActivity": None,
        "sharing": True, "approximate": False, "batteryLevel": 41, "online": True,
    }  # fmt: skip
    stream.push("member", CAMILA, heartbeat)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.camila")
    assert state.attributes["latitude"] == 27.95
    assert state.attributes["gps_accuracy"] == 12
    assert hass.states.get("sensor.camila_battery").state == "41"

    # Pausing is not a heartbeat: that one does take the location away.
    stream.push("member", CAMILA, {**heartbeat, "sharing": False})
    await hass.async_block_till_done()
    assert "latitude" not in hass.states.get("device_tracker.camila").attributes


async def test_resync_event_fetches_a_new_snapshot(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    await _setup(hass, entry)
    before = client.snapshot.await_count
    stream.push("resync")
    await hass.async_block_till_done()
    assert client.snapshot.await_count > before


async def test_new_member_appears_without_reload(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    await _setup(hass, entry)
    assert hass.states.get("device_tracker.abuela") is None

    client.snapshot.return_value = snapshot(
        members=[member(RENIEL, "Reniel"), member(CAMILA, "Camila"), member("u-abuela", "Abuela")]
    )
    stream.push("member", "u-abuela", {"lat": 1.0, "lng": 1.0, "sharing": True})
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.abuela") is not None


async def test_member_hidden_then_shown_again_comes_back(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    """The admin hides someone in the app and later shows them again: no reload needed."""
    await _setup(hass, entry)
    assert hass.states.get("device_tracker.camila") is not None

    client.snapshot.return_value = snapshot(members=[member(RENIEL, "Reniel")])
    stream.push("resync")
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.camila") is None

    client.snapshot.return_value = snapshot(members=[member(RENIEL, "Reniel"), member(CAMILA, "Camila")])
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.camila") is not None


# ---------- actions ----------


async def test_buttons_call_plumio_and_explain_refusals(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock
) -> None:
    await _setup(hass, entry)

    await hass.services.async_call("button", "press", {"entity_id": "button.camila_ring_phone"}, blocking=True)
    client.ring.assert_awaited_once_with(CAMILA)

    client.ring.side_effect = PlumioRequestError(429, "rate_limited", "wait")
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call("button", "press", {"entity_id": "button.camila_ring_phone"}, blocking=True)
    assert raised.value.translation_key == "rate_limited"

    # Nothing was sent (paused, or no phone): say so instead of pretending.
    client.request_location.return_value = False
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.camila_request_location"}, blocking=True
        )
    assert raised.value.translation_key == "location_not_requested"


async def test_action_buttons_unavailable_without_the_capability(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock
) -> None:
    free = snapshot()
    free["capabilities"] = dict.fromkeys(free["capabilities"], False)
    client.snapshot.return_value = free
    await _setup(hass, entry)

    assert hass.states.get("button.camila_ring_phone").state == "unavailable"
    assert hass.states.get("sensor.camila_last_trip_distance").state == "unavailable"
    # The basics stay: location is free.
    assert hass.states.get("device_tracker.camila").state != "unavailable"


# ---------- free plan ----------

# What the server sends about a member of a Nest without Premium: no map.
NO_MAP = {
    "lat": None, "lng": None, "accuracy": None, "speed": None, "heading": None,
    "locationUpdatedAt": None, "inTrip": False, "userActivity": None,
}  # fmt: skip


def _free_snapshot() -> dict:
    free = snapshot(
        members=[
            member(RENIEL, "Reniel", placeId=HOME, placeName="Casa", placeSince="2026-10-10T08:00:00Z", **NO_MAP),
            member(CAMILA, "Camila", **NO_MAP),
        ]
    )
    free["capabilities"] = dict.fromkeys(free["capabilities"], False)
    return free


async def test_free_nest_says_who_is_home_but_not_where(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    client.snapshot.return_value = _free_snapshot()
    await _setup(hass, entry)

    # Presence, with no coordinates behind it.
    reniel = hass.states.get("device_tracker.reniel")
    assert reniel.state == "home"
    assert "latitude" not in reniel.attributes
    assert hass.states.get("device_tracker.camila").state == "not_home"
    assert hass.states.get("binary_sensor.casa_anyone_home").state == "on"
    assert hass.states.get("sensor.casa_members_home").state == "1"

    # Places and battery are part of the free plan.
    assert hass.states.get("sensor.reniel_place").state == "Casa"
    assert hass.states.get("sensor.camila_battery").state == "80"

    # What Premium adds is there to be seen, locked.
    for locked in (
        "sensor.camila_speed",
        "sensor.camila_activity",
        "sensor.camila_distance_from_home",
        "binary_sensor.camila_driving",
        "button.camila_ring_phone",
    ):
        assert hass.states.get(locked).state == "unavailable", locked

    # Arrivals still arrive, and move the tracker, live.
    stream.push("arrival", CAMILA, {"placeId": HOME, "placeName": "Casa", "eventId": "e1"})
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.camila").state == "home"
    assert hass.states.get("event.camila_events").attributes["event_type"] == "arrival"

    stream.push("departure", CAMILA, {"placeId": HOME, "placeName": "Casa", "eventId": "e2"})
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.camila").state == "not_home"


async def test_paused_member_of_a_free_nest_is_unknown_not_away(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock
) -> None:
    free = _free_snapshot()
    free["members"][1]["sharing"] = False
    client.snapshot.return_value = free
    await _setup(hass, entry)
    assert hass.states.get("device_tracker.camila").state == "unknown"


async def test_free_nest_is_told_what_premium_unlocks_until_it_upgrades(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock
) -> None:
    client.snapshot.return_value = _free_snapshot()
    await _setup(hass, entry)
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(DOMAIN, f"premium_locked_{NEST_ID}")
    assert issue is not None
    assert issue.translation_placeholders == {"nest": "Casa"}

    client.snapshot.return_value = snapshot()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, f"premium_locked_{NEST_ID}") is None
    assert hass.states.get("sensor.camila_speed").state != "unavailable"


# ---------- lifecycle ----------


async def test_revoked_link_starts_reauth(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> None:
    client.snapshot.side_effect = PlumioAuthError("revoked")
    entry.add_to_hass(hass)
    with patch("custom_components.plumio.config_flow.PlumioClient", autospec=True) as cls:
        cls.return_value.pair_start = AsyncMock(
            return_value={"deviceCode": "dc", "userCode": "AAAA-BBBB", "verificationUri": "u", "verificationUriComplete": "u/1"}
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    # The person is shown a fresh code to approve, not an error to decipher.
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]
    assert flows[0]["step_id"] == "link"


async def test_unload(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> None:
    await _setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
