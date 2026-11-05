"""Fixtures for the gateway-layer tests.

Gateway fixtures provide ready-made configs only: the async context
manager must be entered inside each test, because pytest-asyncio
finalizes async fixtures in a different task than their setup — which
trips anyio's cancel-scope ownership check on context-manager exit.
"""

import socket
from collections.abc import AsyncIterator, Callable

import aiohttp
import pytest

from bililive_danmaku.base.config import AppConfig
from tests.conftest import UpstreamStub


@pytest.fixture
def make_free_port() -> Callable[[], int]:
    """Return a factory handing out locally bindable ports.

    Each port is bound then released, so it is guaranteed to have no
    listener in this test run — never hardcode a port number instead.
    """

    def factory() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    return factory


@pytest.fixture
def gateway_config(
    upstream_stub: UpstreamStub,
    make_free_port: Callable[[], int],
    make_app_config: Callable[..., AppConfig],
) -> AppConfig:

    return make_app_config(
        upstream_host=upstream_stub.api_url,
        server_port=make_free_port(),
    )


@pytest.fixture
def gateway_config_without_upstream(
    make_free_port: Callable[[], int],
    make_app_config: Callable[..., AppConfig],
) -> AppConfig:

    # 上游指向一个刚验证过无人监听的端口：连接必然立刻被拒绝。
    dead_port = make_free_port()

    return make_app_config(
        upstream_host=f"http://127.0.0.1:{dead_port}",
        server_port=make_free_port(),
    )


@pytest.fixture
async def http_client() -> AsyncIterator[aiohttp.ClientSession]:

    async with aiohttp.ClientSession() as session:
        yield session
