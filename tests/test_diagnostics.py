"""Diagnostics: nothing in the dump locates, names or identifies anyone."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.plumio.diagnostics import async_get_config_entry_diagnostics

from .conftest import CAMILA, NEST_ID, RENIEL, FakeStream, snapshot


async def test_diagnostics_hide_every_account_id(
    hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock, stream: FakeStream
) -> None:
    client.snapshot.return_value = snapshot(
        activeSos=[{"id": "sos1", "userId": CAMILA, "createdAt": "2026-10-10T12:10:00Z"}]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    data = entry.runtime_data.data
    data.stale.clear()  # the fixture's fixes are old: start from a known set
    data.stale.add(CAMILA)
    data.last_trip[RENIEL] = {"distanceMeters": 1200.0}

    diag = await async_get_config_entry_diagnostics(hass, entry)
    dump = json.dumps(diag)

    for secret in (RENIEL, CAMILA, NEST_ID, "link1", "plm_ha_test", "Reniel", "Camila", "27.95"):
        assert secret not in dump, secret

    # Still readable: the same person keeps the same placeholder everywhere.
    members = diag["data"]["members"]
    assert sorted(members) == ["member_1", "member_2"]
    camila = next(k for k, v in members.items() if v["batteryLevel"] == 80 and v["placeId"] is None)
    reniel = next(k for k in members if k != camila)
    assert diag["data"]["stale"] == [camila]
    assert set(diag["data"]["last_trip"]) <= {"member_1", "member_2"}
    assert diag["data"]["last_trip"][reniel] == {"distanceMeters": 1200.0}
    assert diag["data"]["sos"]["sos1"]["userId"] == "**REDACTED**"
    assert members[camila]["userId"] == "**REDACTED**"
    assert diag["entry"]["nest_id"] == "**REDACTED**"
    assert diag["entry"]["link_id"] == "**REDACTED**"
    assert diag["data"]["nest"]["id"] == "**REDACTED**"
