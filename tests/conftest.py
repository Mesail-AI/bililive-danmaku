"""Shared fixtures for the unit test tree.

Fixtures here are used by more than one subdirectory (base / upstream /
gateway); subdirectory-only fixtures live in that subdirectory's conftest.
"""

import struct
from collections.abc import AsyncIterator, Callable
from typing import Any

import aiohttp
import msgspec
import pytest
from aiohttp import web

from bililive_danmaku.base.config import AppConfig, RoomConfig
from bililive_danmaku.upstream.proto import (
    HEADER_LEN,
    OP_AUTH_REPLY,
    OP_HEARTBEAT,
    OP_SEND_MSG_REPLY,
    pack,
)

DM_PAYLOAD: dict[str, Any] = {
    "cmd": "LIVE_OPEN_PLATFORM_DM",
    "uname": "stub-user",
    "msg": "hello from stub",
    "msg_id": "stub-dm-1",
    "room_id": 23058938,
}

# hold 模式下允许的客户端心跳间隔上限（秒）：超时未收到心跳即断开，
# 模拟平台对缺失心跳的处置。
HEARTBEAT_GRACE: float = 1.5


@pytest.fixture
def make_app_config() -> Callable[..., AppConfig]:
    """Return a factory building a valid ``AppConfig`` with test defaults.

    Keyword overrides are applied on top of the defaults, so a test only
    spells out what it actually varies.
    """

    def factory(**overrides: Any) -> AppConfig:
        values: dict[str, Any] = {
            "server_tokens": ["unit-token"],
            "rooms": [RoomConfig(room_id=23058938, id_code="unit-id-code")],
            "upstream_app_id": "123456",
            "upstream_key": "unit-key",
            "upstream_secret": "unit-secret",
        }
        values.update(overrides)

        return AppConfig(**values)

    return factory


class UpstreamStub:
    """Local stub of the bilibili open platform.

    The HTTP surface answers ``/v2/app/start`` with a valid envelope whose
    ``wss_link`` points back at the stub's own ``/ws``; the fake long
    connection answers the auth frame and pushes one DM event. In default
    mode the socket then drops mid-stream; in ``hold`` mode it stays open
    and enforces client ws heartbeats, disconnecting when none arrive
    within :data:`HEARTBEAT_GRACE`. Every auth body received is recorded.
    """

    def __init__(self, runner: web.AppRunner, port: int, holder: dict[str, Any]) -> None:

        self._runner = runner
        self._holder = holder
        self.port = port
        self.auth_bodies: list[bytes] = []

    @property
    def api_url(self) -> str:

        return f"http://127.0.0.1:{self.port}"

    @property
    def dm_payload(self) -> dict[str, Any]:

        return DM_PAYLOAD

    @property
    def hold(self) -> bool:
        """Whether the fake long connection stays open and enforces heartbeats."""

        return bool(self._holder.get("hold", False))

    @hold.setter
    def hold(self, value: bool) -> None:

        self._holder["hold"] = value

    @property
    def ws_heartbeat_count(self) -> int:
        """How many client ws-heartbeat frames the stub has received."""

        return int(self._holder.get("ws_heartbeats", 0))

    async def stop(self) -> None:

        await self._runner.cleanup()


@pytest.fixture
async def upstream_stub() -> AsyncIterator[UpstreamStub]:

    auth_bodies: list[bytes] = []
    holder: dict[str, Any] = {"hold": False, "ws_heartbeats": 0}

    async def start_app(request: web.Request) -> web.Response:

        auth_bodies.append(await request.read())

        return web.json_response(
            {
                "code": 0,
                "message": "0",
                "request_id": "stub",
                "data": {
                    "game_info": {"game_id": "stub-game"},
                    "websocket_info": {
                        "wss_link": [f"ws://127.0.0.1:{holder['port']}/ws"],
                        "auth_body": '{"stub": true}',
                    },
                },
            }
        )

    async def heartbeat_app(request: web.Request) -> web.Response:

        return web.json_response({"code": 0, "message": "0"})

    async def end_app(request: web.Request) -> web.Response:

        return web.json_response({"code": 0, "message": "0"})

    async def fake_ws(request: web.Request) -> web.WebSocketResponse:

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        msg = await ws.receive()
        assert msg.type == aiohttp.WSMsgType.BINARY
        auth_bodies.append(msg.data)

        await ws.send_bytes(pack(op=OP_AUTH_REPLY, body=b'{"code": 0}'))
        await ws.send_bytes(
            pack(op=OP_SEND_MSG_REPLY, body=msgspec.json.encode(DM_PAYLOAD))
        )

        if not holder["hold"]:
            await ws.close()

            return ws

        # hold 模式：保持连接并强制要求客户端 ws 心跳，超时未收到即断开
        # （模拟平台对缺失心跳的处置）。
        while True:
            try:
                frame = await ws.receive(timeout=HEARTBEAT_GRACE)
            except TimeoutError:
                break

            if frame.type != aiohttp.WSMsgType.BINARY:
                continue

            *_, op, _ = struct.unpack(">IHHII", frame.data[:HEADER_LEN])

            if op == OP_HEARTBEAT:
                holder["ws_heartbeats"] += 1

        await ws.close()

        return ws

    app = web.Application()
    app.router.add_post("/v2/app/start", start_app)
    app.router.add_post("/v2/app/heartbeat", heartbeat_app)
    app.router.add_post("/v2/app/end", end_app)
    app.router.add_get("/ws", fake_ws)

    runner = web.AppRunner(app)

    try:
        await runner.setup()

        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        holder["port"] = int(runner.addresses[0][1])
        stub = UpstreamStub(runner, holder["port"], holder)
        stub.auth_bodies = auth_bodies

        yield stub

    finally:
        await runner.cleanup()
