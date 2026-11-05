# uv 官方镜像自带 uv 与 Python 3.12；构建需要 BuildKit（compose v2 默认启用）。
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 依赖层：仅复制清单（README.md 是 hatchling 打包的必需声明），锁未变时命中缓存
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-default-groups

# 项目层：源码变更不再重装依赖
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["python", "-m", "bililive_danmaku.entrypoint"]
