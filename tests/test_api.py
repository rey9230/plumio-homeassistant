"""The SSE parser, and how HTTP errors are classified."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from custom_components.plumio.api import PlumioAuthError, PlumioClient, PlumioConnectionError, parse_sse


async def _lines(text: str) -> AsyncIterator[bytes]:
    for line in text.splitlines(keepends=True):
        yield line.encode()


async def _parse(text: str) -> list:
    return [event async for event in parse_sse(_lines(text))]


async def test_event_with_id_and_data() -> None:
    events = await _parse('id:17-0\nevent:arrival\ndata:{"type":"arrival","userId":"u1"}\n\n')
    assert len(events) == 1
    assert events[0].event == "arrival"
    assert events[0].id == "17-0"
    assert events[0].data["userId"] == "u1"


async def test_heartbeats_are_not_events() -> None:
    events = await _parse(':hb\n\n:hb\n\nevent:resync\ndata:{}\n\n')
    assert [e.event for e in events] == ["resync"]


async def test_garbage_data_is_skipped_not_fatal() -> None:
    events = await _parse('event:member\ndata:not json\n\nevent:member\ndata:{"userId":"u2"}\n\n')
    assert len(events) == 1
    assert events[0].data["userId"] == "u2"


async def test_crlf_and_space_after_colon() -> None:
    events = await _parse('id: 3-1\r\nevent: sos\r\ndata: {"a": 1}\r\n\r\n')
    assert events[0].id == "3-1"
    assert events[0].data == {"a": 1}


class _Resp:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body
        self.headers: dict[str, str] = {}

    async def text(self) -> str:
        return self._body


async def test_401_with_the_token_code_is_definitive() -> None:
    with pytest.raises(PlumioAuthError) as err:
        await PlumioClient._raise_for_status(_Resp(401, '{"code": "integration_token_invalid"}'))  # type: ignore[arg-type]
    assert err.value.definitive

    with pytest.raises(PlumioAuthError) as err:
        await PlumioClient._raise_for_status(_Resp(401, ""))  # type: ignore[arg-type]
    assert not err.value.definitive


async def test_503_is_a_connection_error_not_an_auth_one() -> None:
    with pytest.raises(PlumioConnectionError):
        await PlumioClient._raise_for_status(_Resp(503, '{"code": "unavailable"}'))  # type: ignore[arg-type]
