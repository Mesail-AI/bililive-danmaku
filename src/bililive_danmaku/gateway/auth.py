"""下游静态 token 鉴权（Q5：config 预共享清单，校验通过即接入）。"""

from collections.abc import Iterable

__all__ = ("Authenticator",)


class Authenticator:
    """预共享 token 清单校验器。

    清单来自 ``AppConfig.server_tokens`` ，构造时固化为不可变集合；运行期
    不变，撤销 token 须改配置并重启网关。
    """

    def __init__(self, tokens: Iterable[str]) -> None:

        self._tokens = frozenset(tokens)

    def authenticate(self, token: str) -> bool:
        """校验单个 token 是否在清单内（严格全等）。"""

        return token in self._tokens
