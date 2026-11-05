"""Unit tests for bililive_danmaku.upstream.client."""

import hashlib

import pytest

from bililive_danmaku.upstream.client import BililiveClient
from tests.conftest import UpstreamStub


def make_client(**overrides: str) -> BililiveClient:
    """Return a client with default unit credentials, overridden as needed."""

    values: dict[str, str] = {"id_code": "c", "app_id": "1", "key": "k", "secret": "s"}
    values.update(overrides)

    return BililiveClient(**values)


class TestSign:
    """``_sign`` assembles the open-platform signature header set."""

    def test_headers_carry_the_required_fields(self) -> None:
        headers = make_client()._sign('{"x": 1}')

        assert headers["x-bili-accesskeyid"] == "k"
        assert headers["x-bili-signature-method"] == "HMAC-SHA256"
        assert headers["x-bili-signature-version"] == "1.0"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert "x-bili-timestamp" in headers
        assert "x-bili-signature-nonce" in headers
        assert headers["Authorization"]

    def test_content_md5_digests_the_exact_body(self) -> None:
        headers = make_client()._sign('{"x": 1}')

        assert headers["x-bili-content-md5"] == hashlib.md5(b'{"x": 1}').hexdigest()


class TestClientLifecycle:
    """Lifecycle guards fire before any network is touched."""

    async def test_events_before_start_raises_runtime_error(self) -> None:
        client = make_client()
        generator = client.events()

        with pytest.raises(RuntimeError, match="start"):
            await generator.__anext__()

        await generator.aclose()

    async def test_shutdown_is_safe_when_never_started(self) -> None:
        client = make_client()

        assert client.running is False
        await client.shutdown()
        assert client.running is False


class TestClientAgainstStub:
    """The full appStart + OP_AUTH handshake against the local stub."""

    async def test_auth_handshake_and_event_stream(
        self, upstream_stub: UpstreamStub
    ) -> None:
        client = make_client(host=upstream_stub.api_url)
        events = []

        async with client:
            # 逐个 append（推导式在生成器中途抛错时会丢弃已产出的元素），
            # 因此不接受 PERF401 的 extend 写法。
            with pytest.raises(ConnectionError):
                async for event in client.events():
                    events.append(event)  # noqa: PERF401

        assert events == [upstream_stub.dm_payload]
        assert client.running is False
        assert upstream_stub.auth_bodies
