# 配置参数

配置由单一 `config.yaml`（也支持 `.json` / `.toml`）承载，可选 `.env` 平铺覆盖
顶层标量字段。进程启动时一次性加载并校验，任何缺失、类型不符或约束不满足都会
**立即退出（exit 1）**，不带病运行。

## 字段总表

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|-|-|-|-|-|
| `server_tokens` | `list[str]` | 是 | — | 下游订阅用的预共享 token 清单；元素去空格后必须非空。运行期只读，撤销 token 须改配置并重启 |
| `rooms` | `list[RoomConfig]` | 是 | — | 房间注册表；`room_id` 全局唯一且为正整数，`id_code` 非空 |
| `upstream_app_id` | `str` | 是 | — | 开放平台互动项目的项目 ID，纯数字字符串（请求体编码时转回整数） |
| `upstream_key` | `str` | 是 | — | 开放平台 access_key，随每次 API 调用经 `x-bili-accesskeyid` 头发送 |
| `upstream_secret` | `str` | 是 | — | 开放平台 access_key_secret，用于 HMAC-SHA256 请求头签名；须保密 |
| `server_host` | `str` | 否 | `"127.0.0.1"` | 网关监听地址；默认仅绑本机回环，容器部署须设 `0.0.0.0` |
| `server_port` | `int` | 否 | `8181` | 网关监听端口（1–65535） |
| `upstream_host` | `str` | 否 | `"https://live-open.biliapi.com"` | 开放平台 API 域名（线上环境） |
| `reconnect_interval` | `float` | 否 | `5.0` | 上游断线后的固定重连间隔（秒），正值 |

### RoomConfig（`rooms` 列表项）

| 字段 | 类型 | 必填 | 说明 |
|-|-|-|-|
| `room_id` | `int` | 是 | B 站直播间号；下游订阅时的 `room_id` 查询参数据此匹配 |
| `id_code` | `str` | 是 | 该直播间的主播身份码——开放平台按房间授权的凭据，由主播在直播间生成；重新开启互动项目后旧码失效 |

## 配置文件示例

```yaml
server_tokens:
  - "下游订阅用的 token"
rooms:
  - room_id: 23058938
    id_code: "该直播间的主播身份码"
upstream_app_id: "123456"
upstream_key: "access_key"
upstream_secret: "access_key_secret"
server_host: "0.0.0.0"   # 容器部署必须
```

（可直接以仓库根的 `config.example.yaml` 为起点。）

## `.env` 覆盖规则

`.env`（工作目录下）以**平铺同名键**覆盖配置文件的顶层标量字段，适合放敏感项：

```text
upstream_secret=真实的 access_key_secret
```

注意：覆盖只对**顶层标量字段**生效——`rooms[].id_code` 是嵌套字段，无法经
`.env` 覆盖，需直接写入 `config.yaml`。

## 校验规则

启动期逐项校验，任一失败即退出：

- `server_tokens` 非空，且元素去空格后非空（防止空 token 鉴权旁路）；
- `rooms` 非空、`room_id` 为正且不重复、`id_code` 非空；
- `upstream_app_id` 为纯数字、`upstream_key` / `upstream_secret` 非空；
- `server_port` 在 1–65535、`reconnect_interval` 为正。

## 运行期语义

- 配置进程内只读：撤销 token、增删房间均需**改配置并重启**；
- `rooms` 是上游连接的注册表：服务只为清单内的房间建立上游连接，
  不在清单中的 `room_id` 订阅会被拒绝（关闭码 `4404`）。
