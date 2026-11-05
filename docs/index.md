# Bililive Danmaku

B 站直播弹幕转发服务：上游对接 [B 站直播开放平台](https://open-live.bilibili.com/)（互动项目），
对下游消费者提供带 token 鉴权的 WebSocket 弹幕订阅。

```{mermaid}
flowchart LR
    BILI[外部实体: B站直播开放平台]
    SYS((bililive_danmaku<br/>弹幕转发服务))
    CONSUMER[外部实体: 下游消费者<br/>持 token 订阅弹幕流]

    BILI -->|"长链事件: UpstreamEvent"| SYS
    SYS -->|"控制流: appStart / appHeartbeat / appEnd（签名 API）"| BILI
    CONSUMER -->|"订阅请求: room_id + token"| SYS
    SYS -->|"事件流: 原样 JSON 透传"| CONSUMER
```

## 它做什么

- **上游**：按配置的房间清单，为每个直播间维护一条开放平台互动项目长连接
  （签名 HTTP API + `OP_AUTH` 鉴权的 WebSocket + 双心跳保活），断线后按固定间隔自动重连；
- **下游**：暴露 `/ws?room_id=<id>&token=<t>` 订阅端点，消费者鉴权通过后持续收到
  该房间的弹幕事件——上游 JSON **原样透传**，不做包装与改写；同一房间支持多个订阅者并存。

## 它不做什么

- 不提供 HTTP REST 管理接口，token 撤销与房间增删通过修改配置并重启完成；
- 不持久化任何数据：运行状态 = 配置文件 + 进程内存注册表；
- 不做弹幕的解析消费——那是下游（本库的 `parse_event` 或你自己的代码）的事。

## 文档导航

```{toctree}
:maxdepth: 2
:caption: 使用文档

quickstart
configuration
deployment
api
```

## 索引

- [源码仓库](https://github.com/Mesail-AI/bililive-danmaku)
- [许可证](https://github.com/Mesail-AI/bililive-danmaku/blob/main/LICENSE)（MIT）
