"""弹幕转发网关：token 鉴权、URL 即订阅、按房间分发上游事件。"""

import contextlib
from collections.abc import AsyncGenerator
from typing import Final, Self

import anyio
import msgspec
import structlog
from aiohttp import web
from anyio import AsyncContextManagerMixin

from bililive_danmaku.base import BililiveDanmakuError
from bililive_danmaku.base.config import AppConfig, RoomConfig
from bililive_danmaku.upstream import BililiveClient

from .auth import Authenticator
from .session import Session

__all__ = ("Gateway",)

logger = structlog.stdlib.get_logger(__name__)

CLOSE_UNAUTHORIZED: Final[int] = 4401
CLOSE_ROOM_UNKNOWN: Final[int] = 4404
CLOSE_UPSTREAM_FAILED: Final[int] = 1011
CLOSE_GOING_AWAY: Final[int] = 1001

# 协议级 ping 间隔：探测半开连接，消费者失联至多 20s 被察觉。
WS_PING_INTERVAL: Final[float] = 20.0

_UPSTREAM_FAILURES = (BililiveDanmakuError, ConnectionError, TimeoutError, OSError)


class RoomHub:
    """单个房间的订阅会话集合与就绪状态。

    上游连接与分发由 :class:`Gateway` 的监督循环持有；hub 只承载会话集合与
    状态标记： ``sessions`` 是正在接收分发的会话， ``waiting`` 是上游未就绪
    期间挂起等待的会话（重连恢复后转入 ``sessions`` ，语义见 api.md）。
    """

    def __init__(self, room: RoomConfig) -> None:

        self.room = room
        self.client: BililiveClient | None = None
        self.sessions: set[Session] = set()
        self.waiting: set[Session] = set()

        self.ready = anyio.Event()
        self.subscribed = anyio.Event()

    def attach(self, session: Session) -> None:

        self.subscribed.set()

        if self.ready.is_set():
            self.sessions.add(session)

        else:
            self.waiting.add(session)

    def detach(self, session: Session) -> None:

        self.sessions.discard(session)
        self.waiting.discard(session)

    def activate(self) -> None:

        self.sessions |= self.waiting
        self.waiting.clear()
        self.ready.set()

    def deactivate(self) -> None:

        self.ready = anyio.Event()

    async def broadcast(self, payload: str) -> None:
        """向全部订阅会话推送一帧事件。

        投递为逐会话串行：最慢会话单帧最多拖慢同房间其他订阅者
        ``SEND_TIMEOUT`` （10 秒），之后该会话被剔除。单个会话投递失败
        （断开/慢消费者超时）只剔除该会话，不影响同房间其他订阅者；会话
        的断开由其自身处理协程收尾。
        """

        for session in tuple(self.sessions):
            try:
                await session.send(payload)

            except (ConnectionError, TimeoutError, OSError):
                self.sessions.discard(session)
                logger.debug("Session dropped on send failure.")


class Gateway(AsyncContextManagerMixin):
    """弹幕转发网关。

    按 ``AppConfig`` 预置的房间清单管理上游连接——每个直播间一个
    :class:`BililiveClient`，首个订阅者到来时懒建，断线后按固定间隔
    重连；对下游提供 ``/ws?room_id=&token=`` 订阅端点：静态 token 鉴权、
    URL 即订阅、按房间广播上游事件（协议见 docs/api.md）。

    生命周期：::

        config = AppConfig.load_file()

        async with Gateway(config) as gateway:
            ...

    网关停止时：关闭监听与全部下游连接，逐房间收尾上游客户端。
    """

    def __init__(self, config: AppConfig) -> None:

        self._config = config
        self._auth = Authenticator(config.server_tokens)
        self._hubs = {room.room_id: RoomHub(room) for room in config.rooms}

        self._runner: web.AppRunner | None = None

        self._running = False

    @property
    def running(self) -> bool:

        return self._running

    @property
    def addresses(self) -> list[tuple[str, int]]:
        """已绑定的监听地址（host, port）；网关未启动时为空。"""

        if self._runner is None:
            return []

        return [(str(host), int(port)) for host, port in self._runner.addresses]

    async def start(self) -> None:
        """构建 aiohttp 应用并开始监听。

        幂等：对已启动的网关重复调用不做任何事。

        Raises:
            OSError: 监听地址/端口不可用。
        """

        if self._running:
            return

        app = web.Application()
        app.router.add_get("/ws", self._handle_ws)

        # 会话已在 shutdown 里逐个收尾，这里的超时只是异常兜底。
        runner = web.AppRunner(app, shutdown_timeout=5.0)

        try:
            await runner.setup()

            site = web.TCPSite(
                runner,
                self._config.server_host,
                self._config.server_port,
            )

            await site.start()

        except BaseException:
            await runner.cleanup()
            raise

        self._runner = runner
        self._running = True
        logger.info(
            "Gateway listening",
            host=self._config.server_host,
            port=self._config.server_port,
            rooms=len(self._hubs),
        )

    async def shutdown(self) -> None:
        """停止监听并收尾全部上游连接。

        先以 1001（Going Away）收尾全部下游会话（含挂起中的）——
        ``runner.cleanup()`` 对在线连接既不发关闭帧、又会按默认 60 秒
        ``shutdown_timeout`` 拖慢停机——随后关闭监听站点，逐房间收尾上游
        客户端。上游收尾失败只记日志：心跳停止后平台自行过期项目。幂等。
        """

        if not self._running:
            return

        self._running = False

        with anyio.CancelScope(shield=True):
            for hub in self._hubs.values():
                for session in tuple(hub.sessions) + tuple(hub.waiting):
                    hub.sessions.discard(session)
                    hub.waiting.discard(session)
                    session.mark_close(CLOSE_GOING_AWAY)

                    with contextlib.suppress(ConnectionError, OSError):
                        await session.ws_close(CLOSE_GOING_AWAY)

            if self._runner is not None:
                await self._runner.cleanup()
                self._runner = None

            for hub in self._hubs.values():
                if hub.client is not None:
                    try:
                        await hub.client.shutdown()

                    except BililiveDanmakuError as err:
                        logger.warning(
                            "Upstream shutdown failed",
                            room_id=hub.room.room_id,
                            error=str(err),
                        )

                    hub.client = None

    async def _supervise(self, hub: RoomHub) -> None:
        """单个房间的上游监督循环。

        挂起等待首个订阅者（懒连），随后确保上游连接可用并泵送事件；上游
        失败时通知存量订阅者、按 ``reconnect_interval`` 固定间隔重连，直至
        网关停止。
        """

        room_id = hub.room.room_id

        await hub.subscribed.wait()
        logger.info("Room supervisor started", room_id=room_id)

        while True:
            client = self._build_client(hub)

            # 心跳循环随客户端上下文启停（网关必须经上下文托管客户端，
            # 否则 ws/项目心跳一次都不会发出，连接将被平台周期性断开）。
            try:
                async with client:
                    hub.client = client
                    hub.activate()
                    logger.info("Upstream ready", room_id=room_id)

                    await self._pump(hub, client)

            except anyio.get_cancelled_exc_class():
                with anyio.CancelScope(shield=True):
                    await self._retire(hub, client)

                raise

            except _UPSTREAM_FAILURES as err:
                await self._handle_upstream_failure(hub, client, room_id, err)

            except BaseExceptionGroup as eg:
                # 心跳任务组会把 pump 异常包成 ExceptionGroup——拆包分流：
                # 上游故障按断线处置，其余异常保持 fail-loud 上抛。
                matched, rest = eg.split(_UPSTREAM_FAILURES)

                if matched is None:
                    raise

                if rest is not None:
                    raise rest from eg

                await self._handle_upstream_failure(
                    hub, client, room_id, matched.exceptions[0]
                )

            finally:
                hub.deactivate()
                hub.client = None

            await anyio.sleep(self._config.reconnect_interval)

    def _build_client(self, hub: RoomHub) -> BililiveClient:

        return BililiveClient(
            id_code=hub.room.id_code,
            app_id=self._config.upstream_app_id,
            key=self._config.upstream_key,
            secret=self._config.upstream_secret,
            host=self._config.upstream_host,
        )

    async def _handle_upstream_failure(
        self,
        hub: RoomHub,
        client: BililiveClient,
        room_id: int,
        err: BaseException,
    ) -> None:

        logger.warning("Upstream interrupted", room_id=room_id, error=str(err))

        with anyio.CancelScope(shield=True):
            await self._retire(hub, client)

    async def _pump(self, hub: RoomHub, client: BililiveClient) -> None:

        async for event in client.events():
            payload = msgspec.json.encode(event).decode("utf-8")
            await hub.broadcast(payload)

    async def _retire(self, hub: RoomHub, client: BililiveClient) -> None:
        """收尾一次上游失效：以 1011 关闭存量订阅，再收尾上游客户端。"""

        logger.debug(
            "Retiring room sessions",
            room_id=hub.room.room_id,
            sessions=len(hub.sessions),
        )

        for session in tuple(hub.sessions):
            hub.sessions.discard(session)
            session.mark_close(CLOSE_UPSTREAM_FAILED)

            try:
                await session.ws_close(CLOSE_UPSTREAM_FAILED)

            except (ConnectionError, OSError) as err:
                logger.debug(
                    "Session close failed",
                    room_id=hub.room.room_id,
                    error=str(err),
                )

        try:
            await client.shutdown()

        except BililiveDanmakuError as err:
            logger.warning(
                "Upstream shutdown failed",
                room_id=hub.room.room_id,
                error=str(err),
            )

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        """``/ws`` 订阅端点：token 鉴权 → 房间校验 → 挂起等待上游就绪 →
        停留至消费者断开。分发由房间监督循环完成，本协程只读连接。
        """

        if not self._auth.authenticate(request.query.get("token", "")):
            return await self._reject(request, CLOSE_UNAUTHORIZED, "unauthorized")

        try:
            room_id = int(request.query.get("room_id", ""))

        except ValueError:
            room_id = -1

        hub = self._hubs.get(room_id)

        if hub is None:
            return await self._reject(request, CLOSE_ROOM_UNKNOWN, "room unknown")

        ws = web.WebSocketResponse(heartbeat=WS_PING_INTERVAL)
        await ws.prepare(request)

        session = Session(ws)
        hub.attach(session)
        logger.info("Session attached", room_id=room_id, peer=request.remote)

        # 上游未就绪时会话挂在 hub.waiting（挂起等待，语义见 docs/api.md），
        # 本协程必须始终读取 ws：aiohttp 的心跳 pong 处理依赖收包循环，
        # 停在别处等就绪会被心跳判死、连接以 1006 裸断。
        try:
            async for _ in ws:
                pass

        except anyio.get_cancelled_exc_class():
            raise

        except (ConnectionError, TimeoutError, OSError):
            logger.debug("Subscription connection closed", room_id=room_id)

        finally:
            hub.detach(session)
            logger.info("Session detached", room_id=room_id)

        # 服务端发起的关闭（上游失效等）由本协程补上关闭帧：retire 与本段
        # 存在调度竞速，谁后到谁以 1011 关闭；两者都不会发出 1000。
        if not ws.closed:
            await ws.close(code=session.requested_close_code or CLOSE_UPSTREAM_FAILED)

        return ws

    async def _reject(
        self,
        request: web.Request,
        code: int,
        message: str,
    ) -> web.WebSocketResponse:

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.close(code=code, message=message.encode("utf-8"))

        return ws

    @contextlib.asynccontextmanager
    async def __asynccontextmanager__(self) -> AsyncGenerator[Self, None]:

        try:
            await self.start()

            async with anyio.create_task_group() as tasks:
                for hub in self._hubs.values():
                    tasks.start_soon(self._supervise, hub)

                yield self
                tasks.cancel_scope.cancel()

        finally:
            with anyio.CancelScope(shield=True):
                await self.shutdown()
