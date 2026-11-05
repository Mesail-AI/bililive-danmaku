import re
from pathlib import Path
from typing import ClassVar, Self

import dotenv

from bililive_danmaku.base.constants import BASE_DIR, BILILIVE_API_PREFIX
from bililive_danmaku.base.schemas import BaseStruct

__all__ = ("AppConfig", "RoomConfig")


StrPath = str | Path


class RoomConfig(BaseStruct):
    """单个直播间的接入参数。

    ``room_id`` 是 B 站直播间号，下游订阅时的 ``room_id`` 查询参数据此匹配；
    ``id_code`` 是该直播间的主播身份码——开放平台按房间授权的凭据，由各主播
    在自己的直播间生成。
    """

    room_id: int
    id_code: str


class AppConfig(BaseStruct):
    """服务启动参数总表。

    ``server_host``/``server_port`` 是网关监听地址与端口；``server_host``
    默认仅绑定本机回环地址，对外暴露需显式配置。 ``server_tokens`` 是下游
    预共享 token 清单，非空强制；运行期只读，撤销 token 须改配置并重启。
    ``rooms`` 是房间注册表，非空强制且 ``room_id`` 不得重复。
    ``upstream_app_id``/``upstream_key``/``upstream_secret`` 是开放平台凭证
    三元组（app_id 为纯数字字符串，编码时转回整数）；``upstream_host`` 默认
    线上环境。 ``reconnect_interval`` 是上游断线后的固定重连间隔（秒）。
    密钥类字段（ ``upstream_secret`` 与各房间的 ``id_code`` ）建议经 ``.env``
    提供，与配置文件同名键平铺覆盖。
    """

    _instance: ClassVar[Self | None] = None

    server_tokens: list[str]
    rooms: list[RoomConfig]
    upstream_app_id: str
    upstream_key: str
    upstream_secret: str

    server_host: str = "127.0.0.1"
    server_port: int = 8181
    upstream_host: str = BILILIVE_API_PREFIX
    reconnect_interval: float = 5.0

    def __post_init__(self) -> None:

        if not self.server_tokens:
            raise ValueError("server_tokens must not be empty.")

        # 空/纯空白 token 会让"缺 token 参数"的握手（取到空串）直接命中
        # 清单，构成鉴权旁路。
        if any(not token.strip() for token in self.server_tokens):
            raise ValueError("server_tokens contains blank token.")

        if not self.rooms:
            raise ValueError("rooms must not be empty.")

        if any(room.room_id <= 0 for room in self.rooms):
            raise ValueError("rooms contains non-positive room_id.")

        if any(not room.id_code for room in self.rooms):
            raise ValueError("rooms contains empty id_code.")

        room_ids = [room.room_id for room in self.rooms]

        if len(room_ids) != len(set(room_ids)):
            raise ValueError("rooms contains duplicate room_id.")

        if not re.fullmatch(r"[0-9]+", self.upstream_app_id):
            raise ValueError(
                f"upstream_app_id must be numeric. upstream_app_id={self.upstream_app_id!r}",
            )

        if not self.upstream_key:
            raise ValueError("upstream_key must not be empty.")

        if not self.upstream_secret:
            raise ValueError("upstream_secret must not be empty.")

        if not 1 <= self.server_port <= 65535:
            raise ValueError(
                f"server_port out of range. server_port={self.server_port}",
            )

        if self.reconnect_interval <= 0:
            raise ValueError(
                f"reconnect_interval must be positive. "
                f"reconnect_interval={self.reconnect_interval}",
            )

    @classmethod
    def load_file(
        cls,
        config: "StrPath" = "config.yaml",
        env: "StrPath" = ".env",
    ) -> Self:
        """读取配置文件并合并 ``.env`` 覆盖，进程内只加载一次。

        单例语义：首个成功加载的结果缓存在类上，后续调用无论传入什么
        路径都返回同一实例；需要重新加载时清空 ``cls._instance`` （测试
        的 ``reset_app_config_singleton`` fixture 即此用途）。

        Raises:
            FileNotFoundError: 配置文件不存在。
            ValueError: 后缀不受支持。
            msgspec.ValidationError: 字段缺失或类型不符。
            ValueError: ``__post_init__`` 校验未通过。
        """

        if cls._instance is not None:
            return cls._instance

        confile = BASE_DIR / config if isinstance(config, str) else config

        if not confile.exists():
            raise FileNotFoundError(f"Config file not found: {confile!s}")

        obj = confile.read_text(encoding="utf-8")

        match confile.suffix:
            case ".yaml" | ".yml":
                cls._instance = cls.from_yaml(obj)
            case ".json":
                cls._instance = cls.from_json(obj)
            case ".toml":
                cls._instance = cls.from_toml(obj)
            case _ as suffix:
                raise ValueError(f"Unsupported config file suffix: {suffix}")

        # 缓存的是合并 env 后的最终配置——否则单例缓存的是文件原始值，
        # 每次调用都会重新读盘并产生新对象。
        cls._instance = cls.from_dict({**cls._instance.to_dict(), **cls.load_env(env)})

        return cls._instance

    @classmethod
    def load_env(cls, env: "StrPath") -> dict[str, str]:

        envfile = BASE_DIR / env if isinstance(env, str) else env

        if not envfile.exists():
            return {}

        values = dotenv.dotenv_values(envfile)

        return {key: value for key, value in values.items() if value is not None}
