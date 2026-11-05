"""全库共享的异常层级。

bililive_danmaku 的所有异常都派生自 :class:`BililiveDanmakuError`，调用方
用一个 ``except BililiveDanmakuError`` 就能捕获整个家族，同时仍可单独
处理具体失败。
"""

__all__ = ("BililiveDanmakuError",)


class BililiveDanmakuError(Exception):
    """bililive_danmaku 抛出的所有异常的基类。"""
