"""Unit tests for bililive_danmaku.upstream.proto."""

import struct

import pytest

from bililive_danmaku.upstream.exceptions import ProtocolError
from bililive_danmaku.upstream.proto import (
    HEADER_LEN,
    OP_AUTH,
    OP_AUTH_REPLY,
    OP_HEARTBEAT,
    VER_JSON,
    Packet,
    pack,
    parse,
)


class TestPack:
    """``pack`` builds the 16-byte big-endian framed wire form."""

    def test_pack_uses_protocol_defaults(self) -> None:
        data = pack(op=OP_HEARTBEAT)

        packet_len, header_len, ver, op, seq = struct.unpack(">IHHII", data)
        assert packet_len == HEADER_LEN
        assert header_len == HEADER_LEN
        assert ver == VER_JSON
        assert op == OP_HEARTBEAT
        assert seq == 1
        assert len(data) == HEADER_LEN

    def test_pack_appends_body_after_header(self) -> None:
        data = pack(op=OP_AUTH, body=b'{"uid": 1}')

        assert data[:HEADER_LEN] == struct.pack(
            ">IHHII", HEADER_LEN + 10, HEADER_LEN, 0, OP_AUTH, 1
        )
        assert data[HEADER_LEN:] == b'{"uid": 1}'


class TestParse:
    """``parse`` splits one or more concatenated frames."""

    def test_round_trips_a_single_frame(self) -> None:
        packets = parse(pack(op=OP_AUTH, body=b'{"uid": 1}'))

        assert packets == [Packet(ver=0, op=OP_AUTH, seq=1, body=b'{"uid": 1}')]

    def test_splits_back_to_back_frames(self) -> None:
        batch = pack(op=OP_AUTH, body=b'{"a": 1}') + pack(
            op=OP_AUTH_REPLY, body=b'{"code": 0}'
        )

        packets = parse(batch)

        assert [p.op for p in packets] == [OP_AUTH, OP_AUTH_REPLY]
        assert packets[1].body == b'{"code": 0}'

    def test_accepts_empty_body_frame(self) -> None:
        packets = parse(pack(op=OP_HEARTBEAT))

        assert packets == [Packet(ver=0, op=OP_HEARTBEAT, seq=1, body=b"")]

    def test_truncated_header_raises_protocol_error(self) -> None:
        with pytest.raises(ProtocolError, match="header"):
            parse(pack(op=OP_HEARTBEAT)[:10])

    def test_truncated_body_raises_protocol_error(self) -> None:
        data = pack(op=OP_AUTH, body=b'{"a": 1}')

        with pytest.raises(ProtocolError, match="body"):
            parse(data[:-4])

    def test_unexpected_header_length_raises_protocol_error(self) -> None:
        data = bytearray(pack(op=OP_HEARTBEAT))
        struct.pack_into(">H", data, 4, 32)

        with pytest.raises(ProtocolError, match="header_len"):
            parse(bytes(data))
