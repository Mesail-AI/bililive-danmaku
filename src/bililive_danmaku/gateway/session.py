"""下游订阅会话：一条绑定房间的 ws 连接。"""

from typing import Final

import anyio
from aiohttp import web

__all__ = ("Session",)

# 单帧投递的上限时间：慢消费者超过它即被剔除，不拖死同房间的分发循环。
SEND_TIMEOUT: Final[float] = 10.0


class Session:
    """一条下游订阅会话。

    只被所属房间的分发循环写入（:meth:`send`），被自身处理协程读取（探测
    断开）。发送超时或连接失效由调用方剔除会话，会话自身不做重连。
    服务端发起的关闭（:meth:`mark_close`）由处理协程在收包循环结束后亲自
    执行——跨 task 直接 close 会与 handler 返回路径竞速，关闭码会被
    aiohttp 协议层的默认 1000 覆盖。
    """

    def __init__(self, ws: web.WebSocketResponse) -> None:

        self._ws = ws
        self._close_code: int | None = None

    async def send(self, payload: str) -> None:

        with anyio.fail_after(SEND_TIMEOUT):
            await self._ws.send_str(payload)

    def mark_close(self, code: int) -> None:

        self._close_code = code

    async def ws_close(self, code: int) -> None:

        await self._ws.close(code=code)

    @property
    def requested_close_code(self) -> int | None:

        return self._close_code
