# Bililive Danmaku

B 站直播弹幕转发服务：上游对接 [B 站直播开放平台](https://open-live.bilibili.com/)（互动项目），
对下游消费者提供带 token 鉴权的 WebSocket 弹幕订阅——每个直播间一条上游长链，多个消费者
按房间订阅同一份事件流。

## 特性

- **上游接入**：HMAC-SHA256 签名调开放平台 API（`/v2/app/start`、`/v2/app/heartbeat`、
  `/v2/app/end`），持有 `OP_AUTH` 鉴权的 WebSocket 长链，双心跳保活（ws 30s / 项目 20s）；
- **全量事件 schema**：弹幕、礼物、上舰、醒目留言、点赞、进入、开播/下播等 11 条命令的
  字段级类型化结构（[msgspec](https://msgspec.msgpack.io/) + Annotated 元数据约束），
  未知命令原样透传、上游扩容不破坏解码；
- **订阅网关**：静态 token 鉴权、`/ws?room_id=&token=` 即连即订、同房间多订阅者广播；
  上游连接按需懒建，断线后固定间隔自动重连；
- **配置化启动**：单一 `config.yaml`（+ 可选 `.env` 覆盖敏感项），启动期快速失败校验；
- **容器化部署**：uv 分层镜像 + Docker Compose，`SIGINT`/`SIGTERM` 优雅退出。

## 快速开始

前置：Python ≥ 3.12、[uv](https://docs.astral.sh/uv/)、一个已开通互动项目的直播间
（主播身份码）与开放平台凭证（app_id / access_key / access_key_secret）。

```bash
uv sync --dev

cp config.example.yaml config.yaml   # 填入 token、房间与凭证
uv run app
```

服务启动后，下游这样订阅（以 aiohttp 为例）：

```python
import aiohttp

async with aiohttp.ClientSession() as session:
    ws = await session.ws_connect(
        "http://127.0.0.1:8181/ws?room_id=23058938&token=你的token"
    )
    async for msg in ws:
        print(msg.data)  # 上游事件原样 JSON
```

## Docker 部署

```bash
cp config.example.yaml config.yaml   # server_host 需设为 0.0.0.0
make compose build && make compose up -d
```

## 文档

完整文档（快速开始、配置参数详解、部署指引）见 `docs/`：
本地 `make docs-build` 后打开 `docs/_build/html/index.html`，或访问 GitHub Pages 站点。

## 开发

```bash
make install     # 全新安装依赖
make check       # lint + 类型 + 全部测试
make test        # 单元测试
make docs-build  # 构建 Sphinx 文档
```

## 许可证

[MIT](LICENSE)
