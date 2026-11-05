"""Gateway subscription tests: auth, room lookup, streaming and lifecycle.

The gateway runs against the local open-platform stub (see the tree-root
conftest), so every code path here is exercised on localhost without
network access. The async context manager is entered inside each test —
see the gateway conftest note on pytest-asyncio task ownership.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator

import aiohttp
import pytest

from bililive_danmaku.base.config import AppConfig
from bililive_danmaku.gateway import Gateway
from bililive_danmaku.upstream import client as upstream_client
from tests.conftest import UpstreamStub


def ws_url(gateway: Gateway, room_id: int | str, token: str = "unit-token") -> str:
    host, port = gateway.addresses[0]
    query = f"room_id={room_id}&token={token}" if token else f"room_id={room_id}"

    return f"http://{host}:{port}/ws?{query}"


@contextlib.asynccontextmanager
async def streaming_ws(
    gateway: Gateway,
    http_client: aiohttp.ClientSession,
    room_id: int = 23058938,
    token: str = "unit-token",
) -> AsyncGenerator[aiohttp.ClientWebSocketResponse, None]:

    ws = await http_client.ws_connect(ws_url(gateway, room_id=room_id, token=token))

    try:
        yield ws
    finally:
        await ws.close()


class TestGatewayAuth:
    """Rejected handshakes close with the documented codes."""

    async def test_missing_token_is_rejected_with_4401(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        async with Gateway(gateway_config) as gateway:
            ws = await http_client.ws_connect(ws_url(gateway, room_id=23058938, token=""))

            msg = await ws.receive(timeout=5)

        assert msg.type == aiohttp.WSMsgType.CLOSE
        assert msg.data == 4401

    async def test_wrong_token_is_rejected_with_4401(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        async with Gateway(gateway_config) as gateway:
            ws = await http_client.ws_connect(
                ws_url(gateway, room_id=23058938, token="nope")
            )

            msg = await ws.receive(timeout=5)

        assert msg.type == aiohttp.WSMsgType.CLOSE
        assert msg.data == 4401

    async def test_unknown_room_is_rejected_with_4404(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        async with Gateway(gateway_config) as gateway:
            ws = await http_client.ws_connect(ws_url(gateway, room_id=999))

            msg = await ws.receive(timeout=5)

        assert msg.type == aiohttp.WSMsgType.CLOSE
        assert msg.data == 4404

    async def test_non_integer_room_is_rejected_with_4404(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        async with Gateway(gateway_config) as gateway:
            ws = await http_client.ws_connect(ws_url(gateway, room_id="abc"))

            msg = await ws.receive(timeout=5)

        assert msg.type == aiohttp.WSMsgType.CLOSE
        assert msg.data == 4404


class TestGatewayStreaming:
    """A subscriber rides the full pipeline: stub event in, frames out."""

    async def test_subscriber_receives_event_then_1011_on_upstream_drop(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        async with Gateway(gateway_config) as gateway:
            async with streaming_ws(gateway, http_client) as ws:
                first = await ws.receive(timeout=10)
                assert first.type == aiohttp.WSMsgType.TEXT
                payload = json.loads(first.data)
                assert payload["cmd"] == "LIVE_OPEN_PLATFORM_DM"
                assert payload["msg"] == "hello from stub"

                second = await ws.receive(timeout=10)
                assert second.type == aiohttp.WSMsgType.CLOSE
                assert second.data == 1011

    async def test_reconnect_loop_serves_a_following_subscriber(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        async with Gateway(gateway_config) as gateway:
            async with streaming_ws(gateway, http_client) as first_ws:
                await first_ws.receive(timeout=10)
                await first_ws.receive(timeout=10)

            async with streaming_ws(gateway, http_client) as second_ws:
                first = await second_ws.receive(timeout=10)
                second = await second_ws.receive(timeout=10)

        assert first.type == aiohttp.WSMsgType.TEXT
        assert json.loads(first.data)["cmd"] == "LIVE_OPEN_PLATFORM_DM"
        assert second.type == aiohttp.WSMsgType.CLOSE
        assert second.data == 1011

    async def test_waiting_session_keeps_ws_alive_while_upstream_fails(
        self,
        gateway_config_without_upstream: AppConfig,
        http_client: aiohttp.ClientSession,
    ) -> None:
        """上游持续失败时，挂起会话的连接必须保持可响应。

        服务端心跳 pong 由处理协程的收包循环驱动——这是对"处理协程停在
        就绪等待上、连接被心跳判死（1006 裸断）"缺陷的回归测试。
        """
        async with Gateway(gateway_config_without_upstream) as gateway:
            async with streaming_ws(gateway, http_client) as ws:
                await asyncio.wait_for(ws.ping(b"probe"), timeout=3)

                # 依旧挂起：没有事件、也没有 1011/1006
                with pytest.raises(TimeoutError):
                    await ws.receive(timeout=1.5)


class TestUpstreamHeartbeat:
    """网关托管的客户端必须持续发送上游 ws 心跳。

    心跳循环只在客户端的异步上下文管理器内启动——曾因网关监督循环不经
    上下文托管客户端（直接 ``client.start()``）而从未发出，真实环境连接
    被平台周期性断开、全房间分钟级闪断。桩在 hold 模式下强制要求心跳，
    超时未收到即断开：修复前本测试必红。
    """

    async def test_gateway_client_sends_ws_heartbeat(
        self,
        gateway_config: AppConfig,
        http_client: aiohttp.ClientSession,
        upstream_stub: UpstreamStub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 把 30s 的心跳周期压到 0.4s，让桩能在秒级窗口内观察到多个周期。
        monkeypatch.setattr(upstream_client, "WS_HEARTBEAT_INTERVAL", 0.4)
        upstream_stub.hold = True

        async with Gateway(gateway_config) as gateway:
            async with streaming_ws(gateway, http_client) as ws:
                first = await ws.receive(timeout=5)
                assert first.type == aiohttp.WSMsgType.TEXT
                assert json.loads(first.data)["cmd"] == "LIVE_OPEN_PLATFORM_DM"

                # 连接须跨多个心跳周期保持存活：若心跳缺失，桩会在 1.5s
                # 后断开，这里收到的是 CLOSE(1011) 而非超时。
                with pytest.raises(TimeoutError):
                    await ws.receive(timeout=3)

        assert upstream_stub.ws_heartbeat_count >= 3
