"""End-to-end check through a running Home Assistant.

Drives a freshly started Home Assistant over its own HTTP API exactly as a person would
through the UI — onboarding, "Add integration", the link step — and plays the Plumio
admin's part against the backend. Then watches Home Assistant's states react.

    python scripts/e2e_home_assistant.py http://127.0.0.1:8129 http://127.0.0.1:8089 http://host.docker.internal:8089

The third argument is the backend's address as seen FROM Home Assistant.
"""

from __future__ import annotations

import asyncio
import secrets
import sys

import aiohttp

STEP = 0


def check(condition: bool, what: str, detail: object = "") -> None:
    global STEP
    if not condition:
        print(f"  FAIL  {what}  {detail}")
        raise SystemExit(1)
    STEP += 1
    print(f"  [{STEP:02d}] ok  {what}")


async def wait_until(probe, what: str, timeout: float = 30.0):
    """Poll `probe` until it returns something truthy."""
    deadline = asyncio.get_running_loop().time() + timeout
    last = None
    while asyncio.get_running_loop().time() < deadline:
        last = await probe()
        if last:
            check(True, what)
            return last
        await asyncio.sleep(0.5)
    check(False, what, f"(timed out after {timeout:.0f}s, last={last!r})")


async def main(ha: str, backend: str, backend_from_ha: str) -> None:
    async with aiohttp.ClientSession() as s:

        async def api(method: str, url: str, token: str | None = None, **kw):
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with s.request(method, url, headers=headers, **kw) as r:
                text = await r.text()
                if r.status >= 400:
                    raise SystemExit(f"  FAIL  {method} {url} -> {r.status}: {text[:400]}")
                return (await r.json(content_type=None)) if text else None

        # ---- Home Assistant: onboarding, as on first boot ----
        client_id = f"{ha}/"
        created = await api(
            "POST",
            f"{ha}/api/onboarding/users",
            json={
                "client_id": client_id,
                "name": "E2E",
                "username": "e2e",
                "password": secrets.token_urlsafe(18),  # throwaway instance, never reused
                "language": "es",
            },
        )
        tokens = await api(
            "POST",
            f"{ha}/auth/token",
            data={"grant_type": "authorization_code", "code": created["auth_code"], "client_id": client_id},
        )
        hass = tokens["access_token"]
        check(bool(hass), "Home Assistant is onboarded")

        # ---- Plumio: a family ----
        admin = (await api("POST", f"{backend}/auth/start", json={"displayName": "Reniel"}))["accessToken"]
        me = await api("GET", f"{backend}/users/me", admin)
        nest_id = (await api("POST", f"{backend}/nests", admin, json={"name": "Casa"}))["id"]
        await api(
            "POST",
            f"{backend}/nests/{nest_id}/places",
            admin,
            json={"name": "Casa", "type": "HOME", "lat": 27.95, "lng": -82.45, "radiusMeters": 200.0},
        )

        # ---- "Add integration → Plumio", with the Advanced section pointing at this backend ----
        flow = await api(
            "POST",
            f"{ha}/api/config/config_entries/flow",
            hass,
            json={"handler": "plumio"},
        )
        check(flow["type"] == "form" and flow["step_id"] == "user", "the flow opens (integration loaded by Home Assistant)")
        flow = await api(
            "POST", f"{ha}/api/config/config_entries/flow/{flow['flow_id']}", hass, json={"advanced": {"api_url": backend_from_ha}}
        )
        check(flow.get("step_id") == "link", "Home Assistant reached the backend and shows the link step", flow)
        code = flow["description_placeholders"]["code"]
        qr = [f for f in flow["data_schema"] if f["name"] == "qr"][0]["selector"]["qr_code"]["data"]
        check(len(code) == 9 and qr.endswith(code.replace("-", "")), "a code and a QR of the same link are on screen")

        # Submitting before approval keeps the code and says so.
        flow = await api("POST", f"{ha}/api/config/config_entries/flow/{flow['flow_id']}", hass, json={})
        check(flow.get("errors") == {"base": "not_approved_yet"}, "submitting too early says: not approved yet")

        # ---- the admin approves in "the app" ----
        await api("POST", f"{backend}/integrations/pair/{code}/approve", admin, json={"nestId": nest_id})
        flow = await api("POST", f"{ha}/api/config/config_entries/flow/{flow['flow_id']}", hass, json={})
        check(flow["type"] == "create_entry" and flow["title"] == "Casa", "after approval the entry is created, named after the Nest")

        async def state(entity_id: str):
            async with s.get(f"{ha}/api/states/{entity_id}", headers={"Authorization": f"Bearer {hass}"}) as r:
                return (await r.json()) if r.status == 200 else None

        # ---- entities exist ----
        tracker = await wait_until(lambda: state("device_tracker.reniel"), "device_tracker.reniel exists")
        check(tracker["state"] in ("unknown", "not_home"), "no location reported yet: not home, or unknown", tracker["state"])
        await wait_until(lambda: state("sensor.casa_members_home"), "the Nest's sensors exist")
        await wait_until(lambda: state("binary_sensor.casa_occupied"), "the place's sensors exist")

        async def live():
            st = await state("binary_sensor.casa_live_connection")
            return st if st and st["state"] == "on" else None

        await wait_until(live, "the live connection (SSE) is up", 30)

        # ---- a phone reports: Home Assistant reacts over the stream ----
        await api(
            "POST",
            f"{backend}/locations",
            admin,
            json={"lat": 27.95, "lng": -82.45, "accuracy": 9.0, "batteryLevel": 64, "charging": True},
        )

        async def located():
            st = await state("device_tracker.reniel")
            return st if st and st["attributes"].get("latitude") == 27.95 else None

        tracker = await wait_until(located, "the tracker shows the reported fix within seconds", 15)
        check(tracker["attributes"]["gps_accuracy"] == 9, "...with its accuracy")

        async def battery():
            st = await state("sensor.reniel_battery")
            return st if st and st["state"] == "64" else None

        await wait_until(battery, "the battery sensor follows", 10)

        # Arrival needs the server's 60 s dwell; a second fix after it confirms the stay.
        print("        (waiting out the server's 60 s dwell before an arrival counts)")
        await asyncio.sleep(63)
        await api("POST", f"{backend}/locations", admin, json={"lat": 27.95, "lng": -82.45, "accuracy": 9.0, "batteryLevel": 63})

        async def home():
            st = await state("device_tracker.reniel")
            return st if st and st["state"] == "home" else None

        await wait_until(home, "arriving at the Home place turns the tracker to `home`", 25)
        anyone = await state("binary_sensor.casa_anyone_home")
        check(anyone["state"] == "on", "`anyone home` is on")
        events = await state("event.reniel_events")
        check(events["attributes"].get("event_type") == "arrival", "the member's event entity fired `arrival`", events["attributes"])

        # ---- pausing sharing: no location at all ----
        await api("PATCH", f"{backend}/nests/{nest_id}/membership/privacy", admin, json={"shareLocation": False})
        await asyncio.sleep(1.2)
        await api("POST", f"{backend}/presence/heartbeat", admin, json={"batteryLevel": 63, "charging": False})

        async def hidden():
            st = await state("device_tracker.reniel")
            return st if st and "latitude" not in st["attributes"] else None

        # The safety poll (60 s when needed) covers it if no event carries the change.
        tracker = await wait_until(hidden, "pausing removes the location from Home Assistant", 80)
        check(tracker["state"] == "unknown", "...and the tracker is `unknown`, not the last place seen", tracker["state"])

        # ---- a free Nest: actions are unavailable, and say why ----
        ring = await state("button.reniel_ring_phone")
        check(ring["state"] == "unavailable", "on a free Nest the ring button is unavailable")

        # ---- revoking from the app ----
        link_id = (await api("GET", f"{backend}/nests/{nest_id}/integrations", admin))[0]["id"]
        await api("DELETE", f"{backend}/integrations/{link_id}", admin)

        async def reauth():
            # Flows in progress are only listed over the websocket API.
            async with s.ws_connect(f"{ha}/api/websocket") as ws:
                await ws.receive_json()
                await ws.send_json({"type": "auth", "access_token": hass})
                await ws.receive_json()
                await ws.send_json({"id": 1, "type": "config_entries/flow/progress"})
                flows = (await ws.receive_json()).get("result") or []
            return [f for f in flows if f["handler"] == "plumio" and f["context"].get("source") == "reauth"]

        await wait_until(reauth, "revoking in the app makes Home Assistant ask to link again", 150)

    print(f"\nAll {STEP} checks passed: Home Assistant {ha} <-> Plumio {backend}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3].rstrip("/")))
