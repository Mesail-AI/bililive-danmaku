"""网关服务入口：加载配置 → 配置 structlog → 运行网关直至收到退出信号。

容器/命令行启动方式（二选一）::

    app                                   # pyproject [project.scripts]
    python -m bililive_danmaku.entrypoint

配置从工作目录读取（ ``config.yaml`` + 可选 ``.env`` ，见
:class:`AppConfig.load_file`）；容器部署时 ``server_host`` 需设为
``0.0.0.0`` 才能对外监听。
"""

import logging
import signal

import anyio
import msgspec
import structlog

from bililive_danmaku.base.config import AppConfig
from bililive_danmaku.gateway import Gateway

logger = structlog.stdlib.get_logger(__name__)


def configure_logging() -> None:
    """INFO 起滤；渲染沿用 structlog 26 的默认控制台链（时间戳 + 级别 +
    键值对）。需要 JSON 输出时在此调整处理器链。
    """

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


async def serve(config: AppConfig) -> None:
    """运行网关直至收到 ``SIGINT``/``SIGTERM`` 。

    anyio 的信号接收器是**同步**上下文管理器 + 异步迭代器（ ``_SignalReceiver``
    只实现 ``__enter__``/``__exit__`` 与 ``__aiter__`` ），因此用 ``with`` 进入、
    ``async for`` 消费。信号触发后先退出监听，再经上下文管理器收尾：关闭监听、
    断开全部下游连接、逐房间收尾上游客户端（见 :class:`Gateway`）。
    """

    async with Gateway(config):
        with anyio.open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
            logger.info(
                "Service started",
                host=config.server_host,
                port=config.server_port,
                rooms=len(config.rooms),
            )

            async for sig in signals:
                logger.info("Shutdown signal received", signal=sig.name)
                return


def startup() -> None:
    configure_logging()

    try:
        config = AppConfig.load_file()
    except (OSError, ValueError, msgspec.ValidationError) as err:
        # OSError 覆盖配置缺失与不可读（含 compose 在宿主文件缺失时把
        # 挂载点创建成目录的 IsADirectoryError 情形）。
        logger.error("Configuration invalid, exiting", error=str(err))
        raise SystemExit(1) from err

    anyio.run(serve, config)
    logger.info("Service stopped")
