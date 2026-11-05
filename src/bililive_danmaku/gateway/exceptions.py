from bililive_danmaku.base import BililiveDanmakuError

__all__ = ("GatewayError",)


class GatewayError(BililiveDanmakuError):
    """网关服务内部错误的基类。"""
