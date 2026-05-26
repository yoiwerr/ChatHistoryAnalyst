# 第五课：Nginx 反向代理 —— 请求的分拣员

## 为什么需要 Nginx？

你的项目有三个端口：
- Streamlit 前端：`8501`
- FastAPI 后端：`8000`
- PostgreSQL 数据库：`5432`

没有 Nginx 的话，用户要访问前端得打 `http://IP:8501`，要调 API 得 `http://IP:8000`，而且 8501 和 8000 加起来得在安全组开两个端口，安全隐患翻倍。

Nginx 的作用：**统一从 80 端口接客，然后根据请求路径分发给正确的服务**。

```
                 ┌──────────┐
                 │  Nginx   │
    / ─────────→│  :80     │──→ streamlit:8501 (返回 HTML 页面)
    /api ──────→│          │──→ api:8000      (返回 JSON)
    /_stcore ──→│          │──→ streamlit:8501 (WebSocket)
                 └──────────┘
```

专业术语叫"反向代理"（reverse proxy）。"正向代理"是你代理客户端访问外面（科学上网属于这种），"反向代理"是代理外面访问内部服务。

---

## 逐块拆解 nginx/nginx.conf

```nginx
resolver 127.0.0.11 valid=30s ipv6=off;

server {
    listen 80;
    server_name _;
```

### `resolver 127.0.0.11`

- `127.0.0.11` 是 Docker 内嵌 DNS 服务器的地址。每个 Docker 容器自动配了这个 DNS
- Nginx 默认在启动时解析 `proxy_pass` 里的域名。但 Docker 容器可能还没启动！
- 加了这行后，Nginx 会在**每次请求时才做 DNS 解析**（配合后面的变量用法）
- `valid=30s`：解析结果缓存 30 秒。既不会每个请求都查 DNS（太慢），也不会用过期缓存（容器重启后 IP 会变）
- `ipv6=off`：只查 IPv4，省去 IPv6 的查找开销（Docker 网络通常不用 IPv6）

### `listen 80`

监听容器的 80 端口。结合 `docker-compose.yml` 里的 `ports: "80:80"`，最终效果是：服务器 80 端口 → 容器 80 端口 → Nginx 处理。

### `server_name _`

`_` 是一个"占位符"，意思是"不管请求里的域名是什么，我都接"。因为我们用 IP 访问，没有域名，用 `_` 最简单。

---

### Streamlit 路由

```nginx
location / {
    set $upstream streamlit:8501;
    proxy_pass http://$upstream;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
    proxy_buffering off;
}
```

#### `location /`

`/` 匹配**一切以 / 开头的请求**。但 Nginx 的 location 有优先级规则：
- `location /api`（前缀匹配，更长）优先级 > `location /`（前缀匹配，更短）
- 所以 `/api/v1/xxx` 会走 `/api` 的 location，`/index.html` 才会走 `/`

#### `set $upstream streamlit:8501;` + `proxy_pass http://$upstream;`

这是**运行时 DNS 解析**的关键写法。

**为什么用变量而不直接写 `proxy_pass http://streamlit:8501;`？**

```nginx
# 写法 A：直接写（传统写法）
proxy_pass http://streamlit:8501;
# Nginx 启动时解析 streamlit → 172.17.0.3
# 如果此时 streamlit 容器还没启动 → DNS 失败 → Nginx 崩溃

# 写法 B：用变量
set $upstream streamlit:8501;
proxy_pass http://$upstream;
# Nginx 不检查 DNS，每个请求到达时才解析
# streamlit 还没就绪？请求会报 502，但 Nginx 不会崩溃
# 几秒后 streamlit 起来了，DNS 解析成功，请求恢复正常
```

**这解决了我们部署时踩到的最大的坑**：Nginx 容器启动时 streamlit 可能还没就绪。

#### `proxy_http_version 1.1`

Nginx 默认用 HTTP/1.0 和上游通信。但 Streamlit 需要 HTTP/1.1（WebSocket 依赖 1.1 的 keep-alive）。这一行强制 Nginx 用 1.1。

#### `proxy_set_header Upgrade $http_upgrade;`

这行和下一行配合，实现**协议升级**。Streamlit 的前端页面加载后，会建立一条 WebSocket 连接（路径是 `/_stcore/stream`）来接收后端推送的数据更新。WebSocket 的机制是：

```
浏览器                               服务器
  │                                   │
  │ GET /_stcore/stream HTTP/1.1      │
  │ Upgrade: websocket                │  这个 Upgrade 头就是
  │ Connection: Upgrade               │  请求从 HTTP"升级"为 WebSocket
  │                                   │
  │ ← HTTP/1.1 101 Switching Protocols│  服务器同意升级
  │                                   │
  │ ←── WebSocket 双向消息流 ──→       │  不再是 HTTP 请求/响应模式
```

`proxy_set_header Upgrade $http_upgrade` 让 Nginx 把浏览器发来的 `Upgrade` 头**原样转发**给 Streamlit。如果丢了这行，WebSocket 升级会失败，Streamlit 页面会显示"Please wait..."然后报 `WebSocket connection failed`。

#### 其他 header

| Header | 作用 |
|--------|------|
| `Host $host` | 把原始请求的 Host 头传给上游。Streamlit 用它判断请求来源 |
| `X-Real-IP` | 告诉上游：真实客户端的 IP 是什么（否则上游只能看到 Nginx 的 IP）|
| `X-Forwarded-For` | 代理链的完整 IP 列表：如果前面还有代理（如 CDN），这行把每一跳都记录 |
| `X-Forwarded-Proto` | 告诉上游原始请求是 HTTP 还是 HTTPS |

#### `proxy_read_timeout 86400`

让 Nginx 等 86400 秒（24 小时）才断开。Streamlit 的 WebSocket 是长连接，默认 60 秒超时的话，用户开着页面不动一会就断掉了。

#### `proxy_buffering off`

Nginx 默认会缓冲上游的响应——等响应收全了再一次性发给客户端。这对静态文件很好，但对 Streamlit 的实时流式响应是灾难：用户会看到页面白屏好久然后一下子全出现。关掉缓冲让响应实时流过来。

---

### WebSocket 路由

```nginx
location /_stcore {
    set $upstream streamlit:8501;
    proxy_pass http://$upstream;
    ...
}
```

Streamlit 的 WebSocket 端点路径是 `/_stcore/stream`。`location /_stcore` 专门匹配这个路径，和主页路由 `/` 区分开来。

注意这里 `proxy_pass` 也是不带 URI 的，因为我们用了变量——如果带了 URI（`http://$upstream/_stcore`），会把整个请求路径都替换成 `/_stcore`，导致 `/_stcore/stream` 变成 `/_stcore`，WebSocket 就会连错地址。

---

### API 路由

```nginx
location /api {
    set $upstream api:8000;
    proxy_pass http://$upstream;
    proxy_read_timeout 300s;
    ...
}
```

`proxy_read_timeout 300s`：API 请求的超时是 5 分钟（300 秒）。AI 分析一个聊天记录可能要几十秒到几分钟，不能设太短。但和 Streamlit 的 24h 不同——API 请求不应该无限等待。

---

## `proxy_pass` 变量模式的坑（实战教训）

这是我们踩过的一个坑，值得单独讲。

**Nginx 的 `proxy_pass` 有两种行为模式：**

### 模式 A：不带变量

```nginx
proxy_pass http://streamlit:8501;     # 不带 URI
# 请求 /hello → 转发给 http://streamlit:8501/hello

proxy_pass http://streamlit:8501/;    # 带 /
# 请求 /hello → 转发给 http://streamlit:8501/hello

proxy_pass http://streamlit:8501/xxx; # 带 /xxx
# 请求 /hello → 转发给 http://streamlit:8501/xxxhello
#               location / 的 / 被替换成了 /xxx
```

规则：如果 proxy_pass 带了 URI 路径，Nginx 会把 location 匹配到的部分替换成这个 URI。

### 模式 B：带变量

**加了变量，规则就完全不同：**

```nginx
set $upstream streamlit:8501;
proxy_pass http://$upstream;          # 不带 URI
# 请求 /hello → 转发给 http://streamlit:8501/hello  ✅

proxy_pass http://$upstream/api;      # 带 URI（我们最初的写法）
# 请求 /api/v1/xxx → 转发给 http://api:8000/api      ❌ 整个路径被替换！
```

**关键区别：带变量时，如果有 URI，整个原始路径被完全替换为 proxy_pass 里的 URI，不再做前缀匹配替换。**

所以我们最初写了：

```nginx
location /api {
    set $upstream api:8000;
    proxy_pass http://$upstream/api;   # ← BUG! 所有 /api/xxx 都变成 /api
}
```

请求 `/api/v1/imported_files` → 转发给 `http://api:8000/api`（丢失了 `/v1/imported_files`）

修复就是去掉 URI：

```nginx
location /api {
    set $upstream api:8000;
    proxy_pass http://$upstream;        # ← 修复！全路径透传
}
```

请求 `/api/v1/imported_files` → 转发给 `http://api:8000/api/v1/imported_files` ✅

---

## 本课小结

| 你学到的 | 一句话解释 |
|----------|-----------|
| Nginx 的作用 | 单一入口（80 端口），按路径分发给不同服务 |
| `resolver 127.0.0.11` | 用 Docker 内嵌 DNS，运行时解析容器地址 |
| WebSocket 升级 | `Upgrade` + `Connection` 头让 HTTP 升级成双向通信 |
| `proxy_buffering off` | Streamlit 实时响应不能缓冲 |
| `proxy_read_timeout` | 不同路径设不同超时（前端 24h，API 5min） |
| proxy_pass 变量 + URI 的坑 | 带变量 + 带 URI = 完全替换原始路径 ← 血的教训 |

**下一课**：完整部署流程，一步一步走给你看。
