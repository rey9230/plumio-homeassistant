"""How events fold into the state. Pure functions: no Home Assistant needed to reason about them."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.plumio.coordinator import apply_event, snapshot_to_data

from .conftest import CAMILA, HOME, RENIEL, member, snapshot

NOW = datetime(2026, 10, 10, 12, 5, tzinfo=UTC)


def _data(**overrides):
    return snapshot_to_data(snapshot(**overrides), None, NOW)


def test_snapshot_indexes_by_id() -> None:
    data = _data()
    assert set(data.members) == {RENIEL, CAMILA}
    assert [m["userId"] for m in data.members_home()] == [RENIEL]
    assert data.members_at(HOME)[0]["displayName"] == "Reniel"


def test_snapshot_marks_long_silent_members_as_stale() -> None:
    quiet = member(CAMILA, "Camila", locationUpdatedAt="2026-10-10T10:00:00Z")
    paused = member(RENIEL, "Reniel", sharing=False, locationUpdatedAt=None)
    data = _data(members=[quiet, paused])
    # Paused is a choice, not a problem: only a sharing member can be "not reporting".
    assert data.stale == {CAMILA}


def test_member_event_merges_and_keeps_place() -> None:
    data = _data()
    assert apply_event(data, "member", RENIEL, {"lat": 28.0, "lng": -82.5, "sharing": True, "batteryLevel": 55}, None)
    assert data.members[RENIEL]["lat"] == 28.0
    assert data.members[RENIEL]["batteryLevel"] == 55
    assert data.members[RENIEL]["placeId"] == HOME


def test_pausing_drops_the_place_too() -> None:
    data = _data()
    apply_event(data, "member", RENIEL, {"lat": None, "lng": None, "sharing": False}, None)
    assert data.members[RENIEL]["lat"] is None
    assert data.members[RENIEL]["placeId"] is None


def test_unknown_member_asks_for_resync() -> None:
    data = _data()
    assert apply_event(data, "member", "u-new", {"lat": 1.0}, None) is False


def test_arrival_and_departure() -> None:
    data = _data()
    apply_event(data, "arrival", CAMILA, {"placeId": HOME, "placeName": "Casa"}, "2026-10-10T12:30:00Z")
    assert data.members[CAMILA]["placeId"] == HOME
    assert data.members[CAMILA]["placeSince"] == "2026-10-10T12:30:00Z"
    assert len(data.members_home()) == 2

    # Leaving some other place does not take her out of this one.
    apply_event(data, "departure", CAMILA, {"placeId": "p-other"}, None)
    assert data.members[CAMILA]["placeId"] == HOME
    apply_event(data, "departure", CAMILA, {"placeId": HOME}, None)
    assert data.members[CAMILA]["placeId"] is None


def test_sos_lifecycle() -> None:
    data = _data()
    apply_event(data, "sos", CAMILA, {"sosId": "s1"}, "2026-10-10T12:30:00Z")
    assert data.sos["s1"]["userId"] == CAMILA
    apply_event(data, "sos_resolved", None, {"sosId": "s1"}, None)
    assert data.sos == {}


def test_stale_and_back() -> None:
    data = _data()
    apply_event(data, "member_stale", CAMILA, {}, None)
    assert CAMILA in data.stale
    apply_event(data, "member_back", CAMILA, {}, None)
    assert CAMILA not in data.stale


def test_tag_seen_updates_known_tag_and_resyncs_for_unknown() -> None:
    data = _data()
    assert apply_event(data, "tag_seen", None, {"tagId": "t-keys", "lat": 30.0, "lng": -80.0, "batteryMv": 2900}, None)
    assert data.tags["t-keys"]["lat"] == 30.0
    assert data.tags["t-keys"]["batteryMv"] == 2900
    assert apply_event(data, "tag_seen", None, {"tagId": "t-new"}, None) is False


def test_trip_completed_becomes_last_trip() -> None:
    data = _data()
    apply_event(data, "trip_completed", CAMILA, {"distanceMeters": 5200.0, "maxSpeed": 22.0}, None)
    assert data.last_trip[CAMILA]["distanceMeters"] == 5200.0
