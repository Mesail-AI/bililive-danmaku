from bililive_danmaku.base import BililiveDanmakuError

__all__ = (
    "APIError",
    "AuthError",
    "ProtocolError",
)


class APIError(BililiveDanmakuError):
    """开放平台 HTTP API 调用失败或被拒绝时抛出。"""


class AuthError(BililiveDanmakuError):
    """长连接 ``OP_AUTH`` 握手被拒绝时抛出。"""


class ProtocolError(BililiveDanmakuError):
    """线路帧违反长连接协议时抛出。"""
