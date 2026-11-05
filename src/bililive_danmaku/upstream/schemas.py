"""哔哩哔哩开放平台 HTTP API 包络 schema。

只声明客户端消费的字段；msgspec 忽略未知键，因此上游新增字段不影响解码。
"""

from typing import Any

from bililive_danmaku.base.schemas import BaseStruct

__all__ = (
    "AppStartData",
    "GameInfo",
    "OpenPlatformResponse",
    "WebsocketInfo",
)


class OpenPlatformResponse(BaseStruct):
    """所有 ``/v2/app/`` API 响应共用的包络。"""

    code: int
    message: str
    request_id: str = ""
    data: dict[str, Any] | None = None


class GameInfo(BaseStruct):
    """``/v2/app/start`` 返回的互动项目标识。"""

    game_id: str


class WebsocketInfo(BaseStruct):
    """``/v2/app/start`` 返回的长连接接入数据。"""

    wss_link: list[str]
    auth_body: str


class AppStartData(BaseStruct):
    """``/v2/app/start`` 成功响应的 ``data`` 负载。"""

    game_info: GameInfo
    websocket_info: WebsocketInfo
