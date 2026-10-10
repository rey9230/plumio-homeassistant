"""End-to-end check of the integration's client against a real Plumio backend.

Uses the very same `api.py` Home Assistant runs (loaded on its own, so this needs no
Home Assistant install), and plays the admin's part — the approval the Plumio app does —
over plain HTTP.

    python scripts/e2e_against_backend.py http://127.0.0.1:8089

Exits non-zero on the first thing that does not match.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys

import aiohttp

API_PY = Path(__file__).resolve().parent.parent / "custom_components" / "plumio" / "api.py"
spec = importlib.util.spec_from_file_location("plumio_api_client", API_PY)
api = importlib.util.module_from_spec(spec)
sys.modules["plumio_api_client"] = api
spec.loader.exec_module(api)

STEP = 0


def ok(what: str) -> None:
    global STEP
    STEP += 1
    print(f"  [{STEP:02d}] ok  {what}")


def check(condition: bool, what: str) -> None:
    if not condition:
        print(f"  FAIL  {what}")
        raise SystemExit(1)
    ok(what)


class Admin:
    """What the Plumio app does, over HTTP, with a person's session."""

    def __init__(self, session: aiohttp.ClientSession, base: str) -> None:
        self.session, self.base, self.jwt = session, base, ""

    async def call(self, method: str, path: str, body: dict | None = None, expect: int | None = None):
        headers = {"Authorization": f"Bearer {self.jwt}"} if self.jwt else {}
        async with self.session.request(method, self.base + path, json=body, headers=headers) as resp:
            text = await resp.text()
            if expect is not None and resp.status != expect:
                raise SystemExit(f"  FAIL  {method} {path} -> {resp.status} (wanted {expect}): {text[:300]}")
            if expect is None and resp.status >= 400:
                raise SystemExit(f"  FAIL  {method} {path} -> {resp.status}: {text[:300]}")
            return (await resp.json(content_type=None)) if text else None


async def next_event(stream, wanted: str, timeout: float):
    """Read the stream until an event of type `wanted` shows up."""

    async def read():
        async for event in stream:
            if event.event == wanted:
                return event
        return None

    return await asyncio.wait_for(read(), timeout)


async def main(base: str) -> None:
    async with aiohttp.ClientSession() as session:
        admin = Admin(session, base)
        admin.jwt = (await admin.call("POST", "/auth/start", {"displayName": "Reniel"}))["accessToken"]
        me = await admin.call("GET", "/users/me")
        nest = await admin.call("POST", "/nests", {"name": "Casa"})
        nest_id = nest["id"]
        place = await admin.call(
            "POST",
            f"/nests/{nest_id}/places",
            {"name": "Casa", "type": "HOME", "lat": 27.95, "lng": -82.45, "radiusMeters": 200.0},
        )
        ok("admin, nest and a Home place exist")

        # ---- pairing: Home Assistant's side with the real client ----
        anon = api.PlumioClient(session, base)
        pairing = await anon.pair_start("Casa HA")
        check(len(pairing["userCode"]) == 9 and "/link/" in pairing["verificationUriComplete"], "pair_start gives a code and a link")
        check((await anon.pair_poll(pairing["deviceCode"]))["status"] == "PENDING", "poll is PENDING before approval")

        code = pairing["userCode"]
        described = await admin.call("GET", f"/integrations/pair/{code}")
        check(described["instanceName"] == "Casa HA", "the app can see what is asking for access")
        await admin.call("POST", f"/integrations/pair/{code}/approve", {"nestId": nest_id}, expect=204)

        approved = await anon.pair_poll(pairing["deviceCode"])
        check(approved["status"] == "APPROVED" and approved["token"].startswith("plm_ha_"), "poll is APPROVED with a link token")
        check(approved["nestId"] == nest_id and approved["nestName"] == "Casa", "the token is for the approved Nest")
        check((await anon.pair_poll(pairing["deviceCode"]))["status"] == "EXPIRED", "the token is handed out only once")

        client = api.PlumioClient(session, base, approved["token"])

        # ---- snapshot: the keys the coordinator reads ----
        snap = await client.snapshot()
        check(snap["nest"]["id"] == nest_id and snap["nest"]["paused"] is False, "snapshot.nest")
        member = snap["members"][0]
        needed = {"userId", "displayName", "role", "lat", "lng", "accuracy", "batteryLevel", "sharing", "approximate",
                  "online", "inTrip", "placeId", "placeName", "placeSince", "locationUpdatedAt"}
        check(needed <= member.keys(), "snapshot.members has every field the entities read")
        check(member["userId"] == me["id"] and member["role"] == "ADMIN", "the admin is a member, flat (no nested state)")
        check(snap["places"][0]["id"] == place["id"] and snap["places"][0]["type"] == "HOME", "snapshot.places")
        check(set(snap["capabilities"]) >= {"premium", "trips", "tags", "actions"}, "snapshot.capabilities")
        check(snap["capabilities"]["premium"] is False, "a new Nest is on the free plan")

        # ---- the token only opens its own world ----
        try:
            await client._request("GET", "/nests")
            check(False, "a link token must not open the app's API")
        except api.PlumioRequestError as err:
            check(err.status == 403, "a link token is refused (403) on the app's API")

        # ---- paywall, with the server's stable error code ----
        try:
            await client.ring(me["id"])
            check(False, "ring must need Premium")
        except api.PlumioRequestError as err:
            check(err.code == "premium_required", "actions on a free Nest answer premium_required")

        # ---- live events over the real SSE stream ----
        stream = client.events(None, read_timeout=90).__aiter__()
        first = asyncio.create_task(next_event(stream, "member", 30))
        await asyncio.sleep(1.0)  # let the subscription settle
        await admin.call("POST", "/locations", {"lat": 27.95, "lng": -82.45, "accuracy": 8.0, "batteryLevel": 15})
        event = await first
        check(event is not None and event.data["userId"] == me["id"], "a location report arrives as a `member` event")
        check(event.data["data"]["lat"] == 27.95 and event.id is not None, "the event carries the fix and a resumable id")
        last_id = event.id

        low = await next_event(stream, "low_battery", 20)
        check(low.data["data"]["threshold"] == 20, "low battery arrives as its own event")
        last_id = low.id or last_id
        await stream.aclose()

        # ---- something happens while disconnected; resume picks it up ----
        await asyncio.sleep(1.2)  # the server fans out at most once per second per member
        await admin.call("POST", "/locations", {"lat": 27.9501, "lng": -82.4501, "accuracy": 8.0, "batteryLevel": 15})
        await asyncio.sleep(1.5)
        resumed = client.events(last_id, read_timeout=90).__aiter__()
        event = await next_event(resumed, "member", 20)
        check(event.data["data"]["lat"] == 27.9501, "reconnecting with Last-Event-ID replays what was missed")
        await resumed.aclose()

        stale = client.events("1-1", read_timeout=90).__aiter__()
        event = await next_event(stale, "resync", 20)
        check(event is not None, "an id the server no longer has yields `resync`")
        await stale.aclose()

        # ---- the admin's controls take effect at once ----
        link_id = (await admin.call("GET", f"/nests/{nest_id}/integrations"))[0]["id"]
        await admin.call("PATCH", f"/integrations/{link_id}", {"excludedUserIds": [me["id"]]})
        check((await client.snapshot())["members"] == [], "an excluded member disappears from the snapshot")
        await admin.call("PATCH", f"/integrations/{link_id}", {"excludedUserIds": []})

        await admin.call("DELETE", f"/integrations/{link_id}", expect=204)
        try:
            await client.snapshot()
            check(False, "a revoked link must stop working")
        except api.PlumioAuthError:
            ok("revoking from the app kills the token immediately (PlumioAuthError -> reauth)")

    print(f"\nAll {STEP} checks passed against {base}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8089"))
