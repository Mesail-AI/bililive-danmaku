import contextlib
import hmac
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from hashlib import md5, sha256
from typing import Any, Final, Self

import aiohttp
import anyio
import msgspec
import structlog
from anyio import AsyncContextManagerMixin

from bililive_danmaku.base.constants import BILILIVE_API_PREFIX
from bililive_danmaku.upstream.exceptions import APIError, AuthError, ProtocolError
from bililive_danmaku.upstream.proto import (
    OP_AUTH,
    OP_AUTH_REPLY,
    OP_HEARTBEAT,
    OP_HEARTBEAT_REPLY,
    OP_SEND_MSG_REPLY,
    Packet,
    pack,
    parse,
)
from bililive_danmaku.upstream.schemas import AppStartData, OpenPlatformResponse

__all__ = ("BililiveClient",)

logger = structlog.stdlib.get_logger(__name__)

# 心跳节奏以 blivedm 的 OpenLiveClient 为权威参照（官方 demo 与它一致）：
# 任一通道连续缺失约两次心跳，服务端就会丢弃该项目。
WS_HEARTBEAT_INTERVAL: Final[float] = 30.0
APP_HEARTBEAT_INTERVAL: Final[float] = 20.0

REQUEST_TIMEOUT: Final[float] = 10.0
# 安静的直播间每个 ws 心跳周期也至少会收到一次心跳回复。
RECV_TIMEOUT: Final[float] = WS_HEARTBEAT_INTERVAL + 5.0


def _decode_body(body: bytes) -> dict[str, Any]:

    try:
        return msgspec.json.decode(body, type=dict[str, Any])

    except msgspec.DecodeError as err:
        raise ProtocolError("Malformed long-connection JSON body.") from err


class BililiveClient(AsyncContextManagerMixin):
    """哔哩哔哩直播开放平台客户端：向上游订阅并逐项产出弹幕事件。

    对互动项目 HTTP API（ ``/v2/app/start`` 、心跳、 ``/v2/app/end`` ）做签名
    调用，持有完成 ``OP_AUTH`` 鉴权的 WebSocket 长连接，并解码其 16 字节
    帧协议。

    生命周期：随意构造，然后以异步上下文管理器运行——启动、双心跳循环与
    收尾都由它负责::

        client = BililiveClient(id_code=..., app_id=..., key=..., secret=...)

        async with client:
            async for event in client.events():
                ...

    ``start``/``shutdown`` 仍保留为公开方法，供自行管理任务组的调用方使用；
    不经上下文管理器运行时不会有心跳循环，服务端在连续缺失约两次心跳后会
    断开连接。没有自动重连：连接断开即结束上下文。

    Args:
        id_code: 主播身份码。主播在 B 站直播开放平台为直播间生成的随机码，
            项目凭它申请接入该直播间弹幕流的权限；主播重新开启互动项目时
            会生成新的身份码，旧码随之失效。
        app_id: 开放平台互动项目的项目 ID。它是纯数字，这里以字符串传入，
            请求体编码时转回整数；在开放平台控制台创建项目后获得。
        key: 访问凭证 access_key。与 ``secret`` 成对在开放平台控制台申请，
            以请求头 ``x-bili-accesskeyid`` 随每次 API 调用发送。
        secret: 访问凭证密钥 access_key_secret。与 ``key`` 成对申请，用于
            对请求头做 HMAC-SHA256 签名；必须保密，不可下发到不受信任的
            环境。
        host: 开放平台 API 域名。默认线上环境 ``https://live-open.biliapi.com`` 。
    """

    def __init__(
        self,
        id_code: str,
        app_id: str,
        key: str,
        secret: str,
        host: str = BILILIVE_API_PREFIX,
    ) -> None:

        self._id_code = id_code
        self._app_id = app_id
        self._key = key
        self._secret = secret
        self._host = host

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

        self._wss_link = ""
        self._auth_body = ""
        self._game_id = ""

        # 鉴权握手等待 auth 回复时，同一 ws 消息里捎带的其他帧不能丢：
        # 存入缓冲，由收包循环优先消费。
        self._pending: deque[Packet] = deque()

        self._running = False

    @property
    def running(self) -> bool:

        return self._running

    async def start(self) -> None:
        """启动互动项目并完成长连接鉴权。

        调用 ``/v2/app/start`` （服务端随之激活项目），打开长连接并完成
        ``OP_AUTH`` 握手。心跳循环不在这里启动——它们随异步上下文管理器
        全程运行。

        幂等：对已启动的客户端重复调用不做任何事。中途失败会回收已打开的
        资源，包括在 ``/v2/app/start`` 成功后尽力补一次项目结束调用。

        Raises:
            APIError: 开放平台 API 调用失败或被拒绝。
            AuthError: 长连接鉴权被拒绝。
            ProtocolError: 线路帧违反协议。
            ConnectionError: 长连接关闭或出错。
            TimeoutError: HTTP 调用或鉴权回复超出时限。
            ValueError: ``app_id`` 不是数字。
        """

        if self._running:
            return

        try:
            await self._app_start()
            await self._connect()

        except BaseException:
            with anyio.CancelScope(shield=True):
                await self._cleanup()

            raise

        self._running = True

    async def shutdown(self) -> None:
        """关闭长连接并结束互动项目。

        关闭 WebSocket，调用 ``/v2/app/end`` 并释放 HTTP 会话。项目结束
        调用失败时记日志并吞掉：心跳停止后平台会自行过期项目，没有可行动
        的损失。

        幂等：对已停止的客户端重复调用不做任何事。
        """

        if not self._running:
            return

        self._running = False

        with anyio.CancelScope(shield=True):
            await self._cleanup()

    async def events(self) -> AsyncGenerator[dict[str, Any], None]:
        """逐项产出长连接推送的弹幕负载。

        每个 ``OP_SEND_MSG_REPLY`` 帧产出一项——帧内携带的 JSON 对象，由
        msgspec 解析。心跳与鉴权回复在内部消费，永不产出。无法按 JSON
        对象解析的帧记日志并跳过，流继续消费后续消息；协议级违例与连接
        断开则终止流。

        流是单消费者的：同一时刻只能有一个任务迭代本生成器。产出的是上游
        原始 JSON——已知 ``cmd`` 取值的目录见
        :class:`bililive_danmaku.upstream.commands.Command`，类型化转换用
        :func:`bililive_danmaku.upstream.events.parse_event`；上游新增的未知
        命令原样透传，由下游按 ``event["cmd"]`` 自行分发。

        Raises:
            RuntimeError: 客户端未启动，或启动后已被关闭。
            TimeoutError: 在收包窗口（:data:`RECV_TIMEOUT`）内没有任何帧
                到达。
            ConnectionError: 长连接关闭或出错。
            ProtocolError: 线路帧违反协议。
        """

        if not self._running or self._ws is None:
            raise RuntimeError("Run `start` first.")

        while True:
            for packet in await self._recv_packets():
                if packet.op == OP_SEND_MSG_REPLY:
                    try:
                        yield _decode_body(packet.body)

                    except ProtocolError as err:
                        logger.warning("Skipping malformed danmaku frame", error=str(err))

                elif packet.op == OP_AUTH_REPLY:
                    try:
                        reply = _decode_body(packet.body)
                    except ProtocolError as err:
                        logger.warning("Skipping malformed auth reply", error=str(err))
                        continue

                    if reply.get("code") != 0:
                        logger.warning(
                            "Authentication rejected mid-stream",
                            code=reply.get("code"),
                        )

                    logger.debug("Late authentication reply received.")

                elif packet.op == OP_HEARTBEAT_REPLY:
                    logger.debug("Heartbeat reply received.")

                elif packet.op == OP_HEARTBEAT:
                    logger.debug("Heartbeat echo received.")

                else:
                    logger.debug("Unknown frame skipped", op=packet.op)

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self) -> AsyncGenerator[Self, None]:

        try:
            await self.start()

            async with anyio.create_task_group() as heartbeats:
                heartbeats.start_soon(self._heartbeat_ws)
                heartbeats.start_soon(self._heartbeat_app)
                yield self
                heartbeats.cancel_scope.cancel()

        finally:
            with anyio.CancelScope(shield=True):
                await self.shutdown()

    def _sign(self, body: str) -> dict[str, str]:
        # md5 在这里是协议要求（x-bili-content-md5），不是安全原语。
        body_md5 = md5(body.encode("utf-8")).hexdigest()  # noqa: S324

        headers = {
            "x-bili-timestamp": str(int(time.time())),
            "x-bili-signature-method": "HMAC-SHA256",
            "x-bili-signature-nonce": uuid.uuid4().hex,
            "x-bili-accesskeyid": self._key,
            "x-bili-signature-version": "1.0",
            "x-bili-content-md5": body_md5,
        }

        canonical = "\n".join(f"{name}:{headers[name]}" for name in sorted(headers))
        signature = hmac.new(
            self._secret.encode("utf-8"),
            canonical.encode("utf-8"),
            digestmod=sha256,
        ).hexdigest()

        headers.update(
            {
                "Authorization": signature,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        return headers

    async def _request(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> "OpenPlatformResponse":

        body = msgspec.json.encode(payload)
        url = f"{self._host}{path}"
        headers = self._sign(body.decode("utf-8"))

        try:
            async with self._ensure_session().post(
                url, data=body, headers=headers
            ) as response:
                response.raise_for_status()
                raw = await response.read()

        except (aiohttp.ClientError, TimeoutError) as err:
            raise APIError(f"Open platform request failed. path={path}") from err

        try:
            envelope = msgspec.json.decode(raw, type=OpenPlatformResponse)

        except msgspec.DecodeError as err:
            raise APIError(f"Malformed open platform response. path={path}") from err

        if envelope.code != 0:
            raise APIError(
                f"Open platform request rejected. path={path} code={envelope.code} "
                f"message={envelope.message} request_id={envelope.request_id}",
            )

        return envelope

    async def _app_start(self) -> None:

        envelope = await self._request(
            "/v2/app/start",
            {"code": self._id_code, "app_id": int(self._app_id)},
        )

        if envelope.data is None:
            raise APIError("Open platform response carries no data. path=/v2/app/start")

        try:
            data = msgspec.convert(envelope.data, type=AppStartData)

        except msgspec.ValidationError as err:
            raise APIError("Malformed /v2/app/start payload.") from err

        if not data.websocket_info.wss_link:
            raise APIError("Open platform returned no long-connection address.")

        self._game_id = data.game_info.game_id
        self._wss_link = data.websocket_info.wss_link[0]
        self._auth_body = data.websocket_info.auth_body
        logger.info("Open platform app started", game_id=self._game_id)

    async def _connect(self) -> None:

        session = self._ensure_session()

        with anyio.fail_after(REQUEST_TIMEOUT):
            self._ws = await session.ws_connect(self._wss_link)

        await self._ws.send_bytes(pack(op=OP_AUTH, body=self._auth_body.encode("utf-8")))

        # 鉴权回复可能与心跳回复等帧分批先后到达：循环收包直至找到回复，
        # 期间捎带的业务帧存入缓冲交给事件流，时限由外层 fail_after 把守。
        with anyio.fail_after(REQUEST_TIMEOUT):
            while True:
                for packet in await self._recv_packets():
                    if packet.op != OP_AUTH_REPLY:
                        self._pending.append(packet)
                        continue

                    reply = _decode_body(packet.body)
                    code = reply.get("code")

                    if code == 0:
                        logger.info(
                            "Long-connection authenticated",
                            game_id=self._game_id,
                        )
                        return

                    raise AuthError(
                        f"Long-connection authentication rejected. code={code!r} "
                        f"message={reply.get('message')!r}",
                    )

    async def _heartbeat_ws(self) -> None:

        while True:
            await anyio.sleep(WS_HEARTBEAT_INTERVAL)

            if self._ws is None or self._ws.closed:
                raise ConnectionError("Long connection unavailable for heartbeat.")

            await self._ws.send_bytes(pack(op=OP_HEARTBEAT))
            logger.debug("WebSocket heartbeat sent.")

    async def _heartbeat_app(self) -> None:

        while True:
            await anyio.sleep(APP_HEARTBEAT_INTERVAL)
            await self._request("/v2/app/heartbeat", {"game_id": self._game_id})
            logger.debug("App heartbeat sent", game_id=self._game_id)

    async def _recv_packets(self) -> list[Packet]:

        if self._pending:
            return [self._pending.popleft()]

        if self._ws is None:
            raise RuntimeError("Run `start` first.")

        with anyio.fail_after(RECV_TIMEOUT):
            message = await self._ws.receive()

        match message.type:
            case aiohttp.WSMsgType.BINARY:
                return parse(message.data)

            case aiohttp.WSMsgType.TEXT:
                raise ProtocolError("Unexpected text frame on the long connection.")

            case aiohttp.WSMsgType.ERROR:
                raise ConnectionError("Long-connection receive failed.") from message.data

            case _:
                raise ConnectionError("Long connection closed.")

    async def _cleanup(self) -> None:

        if self._ws is not None and not self._ws.closed:
            await self._ws.close()

        self._ws = None

        if self._game_id:
            try:
                await self._request(
                    "/v2/app/end",
                    {"game_id": self._game_id, "app_id": int(self._app_id)},
                )

            except APIError:
                logger.warning("Project end call failed", game_id=self._game_id)

            self._game_id = ""

        if self._session is not None:
            await self._session.close()
            self._session = None

    def _ensure_session(self) -> aiohttp.ClientSession:

        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            )

        return self._session
