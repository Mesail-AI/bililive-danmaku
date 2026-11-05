"""Integration: gateway against the real bilibili open platform.

Requires a real ``config.yaml`` (credentials, rooms and tokens) at the
repo root; skips when the real environment is not configured or the
platform is unreachable.
"""

import socket

import aiohttp
import msgspec
import pytest

from bililive_danmaku.base.config import AppConfig
from bililive_danmaku.gateway import Gateway

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def test_real_gateway_accepts_subscription_and_reaches_upstream() -> None:
    """The gateway authenticates, reaches the real upstream and stays up.

    Pass criteria, in order of preference: a real event arrives, or the
    connection simply stays open (upstream connected, room quiet). A 1011
    close means the platform was unreachable here — that skips. A 4401 or
    4404 close is a configuration bug, not a skip: the config exists but
    the gateway rejected it.
    """

    try:
        config = AppConfig.load_file()
    except (FileNotFoundError, ValueError, msgspec.ValidationError) as err:
        pytest.skip(f"real environment not configured: {err}")

    config.server_port = _free_port()

    async with Gateway(config) as gateway:
        host, port = gateway.addresses[0]
        url = (
            f"http://{host}:{port}/ws"
            f"?room_id={config.rooms[0].room_id}&token={config.server_tokens[0]}"
        )

        async with aiohttp.ClientSession() as http:
            ws = await http.ws_connect(url)

            try:
                msg = await ws.receive(timeout=15)
            except TimeoutError:
                return

            if msg.type == aiohttp.WSMsgType.CLOSE and msg.data == 1011:
                pytest.skip("bilibili upstream unreachable from this environment")

            assert msg.type == aiohttp.WSMsgType.TEXT, msg
