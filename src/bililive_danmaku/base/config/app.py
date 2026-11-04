from pathlib import Path
from typing import ClassVar, Self

import dotenv

from bililive_danmaku.base.constants import BASE_DIR
from bililive_danmaku.base.schemas import BaseStruct

__all__ = ("AppConfig",)


StrPath = str | Path


class AppConfig(BaseStruct):
    _instance: ClassVar[Self | None] = None

    @classmethod
    def load_file(
        cls,
        config: "StrPath" = "config.yaml",
        env: "StrPath" = ".env",
    ) -> Self:

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

        return cls.from_dict({**cls._instance.to_dict(), **cls.load_env(env)})

    @classmethod
    def load_env(cls, env: "StrPath") -> dict[str, str | None]:

        if cls._instance is not None:
            return cls._instance

        envfile = BASE_DIR / env if isinstance(env, str) else env

        if not envfile.exists():
            raise FileNotFoundError(f"Env file not found: {envfile!s}")

        return dotenv.dotenv_values(envfile)
