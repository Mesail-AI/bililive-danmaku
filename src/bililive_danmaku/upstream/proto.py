"""哔哩哔哩长连接线路协议编解码。

帧由固定 16 字节大端包头加包体组成：

==============  ====
包总长          u32
包头长          u16
协议版本        u16
操作码          u32
序号            u32
==============  ====

开放平台上协议版本恒为 :data:`VER_JSON`，包体是 UTF-8 JSON 文本。
一条 WebSocket 消息可能背靠背携带多个帧；:func:`parse` 负责拆分。
"""

import struct
from typing import Final

import msgspec

from bililive_danmaku.upstream.exceptions import ProtocolError

__all__ = (
    "OP_AUTH",
    "OP_AUTH_REPLY",
    "OP_HEARTBEAT",
    "OP_HEARTBEAT_REPLY",
    "OP_SEND_MSG_REPLY",
    "VER_JSON",
    "Packet",
    "pack",
    "parse",
)

HEADER_LEN: Final[int] = 16

VER_JSON: Final[int] = 0

OP_HEARTBEAT: Final[int] = 2
OP_HEARTBEAT_REPLY: Final[int] = 3
OP_SEND_MSG_REPLY: Final[int] = 5
OP_AUTH: Final[int] = 7
OP_AUTH_REPLY: Final[int] = 8

_HEADER: Final[struct.Struct] = struct.Struct(">IHHII")


class Packet(msgspec.Struct, frozen=True, kw_only=True):
    """单个线路帧：包头字段加原始包体字节。

    用普通 ``msgspec.Struct`` 而非 ``BaseStruct`` ：帧不跨 JSON 边界——它
    的编解码是二进制的（:func:`pack`/:func:`parse`）， ``BaseStruct`` 的
    序列化契约在这里没有用武之地。
    """

    ver: int
    op: int
    seq: int
    body: bytes = b""


def pack(*, op: int, ver: int = VER_JSON, seq: int = 1, body: bytes = b"") -> bytes:

    header = _HEADER.pack(HEADER_LEN + len(body), HEADER_LEN, ver, op, seq)

    return header + body


def parse(data: bytes) -> list[Packet]:

    packets: list[Packet] = []
    offset = 0

    while offset < len(data):
        if len(data) - offset < HEADER_LEN:
            raise ProtocolError("Truncated frame header.")

        packet_len, header_len, ver, op, seq = _HEADER.unpack_from(data, offset)

        if header_len != HEADER_LEN:
            raise ProtocolError(
                f"Unexpected frame header length. header_len={header_len}"
            )

        if packet_len < header_len or offset + packet_len > len(data):
            raise ProtocolError(f"Truncated frame body. packet_len={packet_len}")

        body = data[offset + header_len : offset + packet_len]
        packets.append(Packet(ver=ver, op=op, seq=seq, body=body))
        offset += packet_len

    return packets
