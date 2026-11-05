# 部署指引

推荐以 Docker Compose 部署。镜像基于 uv 官方 Python 3.12 镜像分层构建：
`uv.lock` 未变时依赖层命中缓存，源码变更只重跑项目层。

## 部署步骤

1. **准备配置**（宿主机仓库根）：

   ```bash
   cp config.example.yaml config.yaml
   ```

   编辑 `config.yaml`：填入真实 token / 房间 / 凭证，并把 `server_host` 设为
   `"0.0.0.0"`（否则容器只监听内部回环，宿主机无法访问）。`upstream_secret`
   可改放 `.env`。

2. **解开卷挂载**：编辑 `compose.yaml`，取消 `volumes` 两行的注释
   （`config.yaml` 与 `.env` 以只读方式挂入容器）。注意：**必须先在宿主准备好
   这两个文件再 `up`**——宿主路径不存在时 Docker 会把挂载点静默创建成空目录。

3. **构建并启动**：

   ```bash
   make compose build
   make compose up -d
   make compose logs        # 观察日志（Ctrl-C 退出查看，不影响服务）
   ```

4. **验证**：日志出现 `Service started`（含 host/port/rooms 数量）即就绪；
   用任一 ws 客户端连 `ws://<宿主机>:<GATEWAY_PORT>/ws?room_id=<id>&token=<t>` 订阅。

宿主机端口默认映射 `8181`，可用环境变量覆盖：`GATEWAY_PORT=9000 make compose up -d`。

## 停止与更新

```bash
make compose down      # 停止并移除容器（订阅连接以 1001 正常关闭）
make compose restart   # 重启
```

改配置（token、房间、凭证）后需 `make compose up -d --force-recreate` 使其生效——
配置进程内只读，服务不会热加载。

## 优雅退出

容器接收 `SIGTERM`（`docker compose stop` / 编排器停机）后：向全部订阅连接发送
`1001`（Going Away）关闭帧 → 关闭监听 → 逐房间结束互动项目（`/v2/app/end`）→
退出。停机宽限受 compose 默认超时约束，正常在数秒内完成。

## 升级

```bash
git pull
make compose build
make compose up -d --force-recreate
```

依赖未变时仅重跑项目层，秒级完成。

## 常见问题

- **容器反复重启**：查看 `make compose logs`——多为 `Configuration invalid`（配置
  校验失败，常见于 `server_host` 未设 `0.0.0.0` 或凭证缺失），修正配置后
  `make compose up -d --force-recreate`。
- **订阅收到 1011**：该房间上游故障（凭证失效、主播关闭互动项目等）；服务端在
  自动重连，恢复后重连订阅即可。
- **`IsADirectoryError` 读配置失败**：在宿主文件不存在时执行了 `up`（Docker 把
  挂载点创建成了空目录）——`make compose down`、删除仓库根被创建的
  `config.yaml` / `.env` 目录、备好真实文件后再 `up`。
