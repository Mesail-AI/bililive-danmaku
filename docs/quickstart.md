# 快速开始

## 前置条件

- Python ≥ 3.12 与 [uv](https://docs.astral.sh/uv/)；
- 一个已开通「互动项目」的 B 站直播间：主播在直播间生成**主播身份码**（`id_code`）；
- 开放平台凭证：**项目 ID**（`app_id`，纯数字）、**access_key** / **access_key_secret**
  （在开放平台控制台成对申请）。

## 安装

```bash
git clone https://github.com/Mesail-AI/bililive-danmaku.git
cd bililive-danmaku
uv sync --dev
```

## 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入：下游订阅用的 `server_tokens`、房间清单（`room_id` +
该直播间的 `id_code`）、开放平台凭证三元组。本地开发保持 `server_host: 127.0.0.1`
默认值即可；`upstream_secret` 建议放 `.env`（平铺同名键覆盖，如 `upstream_secret=xxx`）。

完整字段说明见 [配置参数](configuration.md)。

## 启动

```bash
uv run app          # 等价于 python -m bililive_danmaku.entrypoint
```

看到 `Service started` 即表示网关就绪（上游连接在首个订阅者到来时才建立）。
`Ctrl-C` 优雅退出。

## 订阅

任一 WebSocket 客户端携带 `room_id` 与 `token` 连接即可：

```python
import aiohttp

async with aiohttp.ClientSession() as session:
    ws = await session.ws_connect(
        "ws://127.0.0.1:8181/ws?room_id=23058938&token=你的token"
    )
    async for msg in ws:
        print(msg.data)  # 上游事件原样 JSON，一行一帧
```

每条消息是上游事件的原样 JSON 对象（弹幕 `LIVE_OPEN_PLATFORM_DM`、礼物
`LIVE_OPEN_PLATFORM_SEND_GIFT` 等）。服务端只透传，解析交给消费方——
本库自带类型化解析：

```python
from bililive_danmaku.upstream import parse_event

event = parse_event(payload)   # 按cmd转为对应结构；未知命令返回 None
```

## 关闭语义

| 关闭码 | 含义 |
|-|-|
| `4401` | token 缺失或不匹配 |
| `4404` | `room_id` 缺失、非整数或不在预置房间清单 |
| `1011` | 该房间上游连接故障（自动重连中，可稍后重连） |
| `1001` | 服务端正常停机 |
