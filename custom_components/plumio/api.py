"""HTTP + Server-Sent Events client for the Plumio integration API.

Deliberately free of Home Assistant imports so it can be tested (and reused) alone.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
from typing import Any

import aiohttp

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Synthetic event emitted by `PlumioClient.events` once the stream is established.
STREAM_OPEN = "_open"


class PlumioError(Exception):
    """Base error: the request did not succeed."""


class PlumioConnectionError(PlumioError):
    """The server could not be reached, or answered with a 5xx."""


class PlumioAuthError(PlumioError):
    """The link token is no longer valid (revoked, or its admin left the Nest)."""


class PlumioRequestError(PlumioError):
    """The server refused the request (4xx). `code` is stable and machine readable."""

    def __init__(self, status: int, code: str, detail: str, retry_after: float | None = None) -> None:
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail
        self.retry_after = retry_after


@dataclass(slots=True, frozen=True)
class SseEvent:
    """One event from the stream. `id` is what to send back as Last-Event-ID."""

    event: str
    data: dict[str, Any]
    id: str | None


class PlumioClient:
    """Thin client. One instance per config entry."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str | None = None) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._token = token

    # ---------- pairing (no token yet) ----------

    async def pair_start(self, instance_name: str | None) -> dict[str, Any]:
        return await self._request("POST", "/integrations/pair/start", json_body={"instanceName": instance_name}, auth=False)

    async def pair_poll(self, device_code: str) -> dict[str, Any]:
        return await self._request("POST", "/integrations/pair/poll", json_body={"deviceCode": device_code}, auth=False)

    # ---------- reads ----------

    async def snapshot(self) -> dict[str, Any]:
        return await self._request("GET", "/integration/v1/snapshot")

    async def trips(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return await self._request("GET", f"/integration/v1/members/{user_id}/trips", params={"limit": str(limit)})

    async def driving_summary(self, user_id: str, tz: str | None = None) -> dict[str, Any]:
        params = {"tz": tz} if tz else None
        return await self._request("GET", f"/integration/v1/members/{user_id}/driving/summary", params=params)

    async def day_timeline(self, user_id: str, start: str, end: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/integration/v1/members/{user_id}/day-timeline", params={"from": start, "to": end}
        )

    # ---------- actions ----------

    async def request_location(self, user_id: str | None = None) -> bool:
        """Ask for a fresh fix. Returns False when nothing could be sent to that member."""
        if user_id is None:
            await self._request("POST", "/integration/v1/refresh")
            return True
        result = await self._request("POST", f"/integration/v1/members/{user_id}/refresh")
        return bool(result and result.get("sent"))

    async def ring(self, user_id: str) -> None:
        await self._request("POST", f"/integration/v1/members/{user_id}/ring")

    async def stop_ring(self, user_id: str) -> None:
        await self._request("POST", f"/integration/v1/members/{user_id}/ring/stop")

    async def create_place(self, place: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/integration/v1/places", json_body=place)

    async def update_place(self, place_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/integration/v1/places/{place_id}", json_body=changes)

    async def delete_place(self, place_id: str) -> None:
        await self._request("DELETE", f"/integration/v1/places/{place_id}")

    # ---------- stream ----------

    async def events(self, last_event_id: str | None, read_timeout: float) -> AsyncIterator[SseEvent]:
        """Yield events until the connection drops. Heartbeats reset the read timeout."""
        headers = self._headers(auth=True)
        headers["Accept"] = "text/event-stream"
        headers["Cache-Control"] = "no-cache"
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=read_timeout)
        try:
            async with self._session.get(
                f"{self._base}/integration/v1/events/stream", headers=headers, timeout=timeout
            ) as resp:
                await self._raise_for_status(resp)
                # A quiet Nest can go minutes without an event: say "connected" now,
                # not when the first one happens to arrive.
                yield SseEvent(event=STREAM_OPEN, data={}, id=None)
                async for event in parse_sse(resp.content):
                    yield event
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PlumioConnectionError(str(err) or type(err).__name__) from err

    # ---------- plumbing ----------

    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        auth: bool = True,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                headers=self._headers(auth),
                json=json_body,
                params=params,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                await self._raise_for_status(resp)
                if resp.status == 204 or resp.content_length == 0:
                    return None
                text = await resp.text()
                return json.loads(text) if text else None
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PlumioConnectionError(str(err) or type(err).__name__) from err

    @staticmethod
    async def _raise_for_status(resp: aiohttp.ClientResponse) -> None:
        if resp.status < 400:
            return
        if resp.status == 401:
            raise PlumioAuthError("Link token rejected")
        if resp.status >= 500:
            raise PlumioConnectionError(f"Server error {resp.status}")
        code, detail = "error", ""
        try:
            body = json.loads(await resp.text())
            code = str(body.get("code") or code)
            detail = str(body.get("detail") or "")
        except (ValueError, AttributeError):
            pass
        retry_after: float | None = None
        if (raw := resp.headers.get("Retry-After")) is not None:
            try:
                retry_after = float(raw)
            except ValueError:
                retry_after = None
        raise PlumioRequestError(resp.status, code, detail, retry_after)


async def parse_sse(lines: AsyncIterator[bytes]) -> AsyncIterator[SseEvent]:
    """Parse a text/event-stream body. Comment-only blocks (heartbeats) yield nothing."""
    event: str | None = None
    event_id: str | None = None
    data: list[str] = []
    async for raw in lines:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            if data and event:
                try:
                    payload = json.loads("\n".join(data))
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    yield SseEvent(event=event, data=payload, id=event_id)
            event, event_id, data = None, None, []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
        elif field == "id":
            event_id = value
