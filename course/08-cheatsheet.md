# 第八课：速查表

> 这个是干活时的快速参考，不用从头读，用到哪个查哪个。

---

## Docker 日常命令

### 容器生命周期

```bash
docker compose up -d              # 启动所有服务（后台）
docker compose down               # 停止所有服务并删除容器
docker compose down -v            # 停止所有服务 + 删除容器 + 删除数据卷（危险！）
docker compose restart api        # 只重启 API 容器
docker compose restart nginx      # 只重启 Nginx
docker compose up -d --build      # 重新构建镜像 + 启动（修改 Dockerfile 后）
docker compose stop               # 停止但不删除容器
docker compose start              # 重新启动已停止的容器
```

### 查看状态

```bash
docker compose ps                 # 查看所有容器的运行状态
docker compose ps -a              # 包括已停止的容器
docker compose logs -f            # 实时尾巴看所有容器日志
docker compose logs api           # 只看 API 的日志
docker compose logs --tail=50 api # API 最近 50 行日志
docker stats                      # CPU / 内存实时占用
docker compose exec api env       # 查看 API 容器的环境变量
```

### 进入容器内部

```bash
docker compose exec api bash           # 进 API 容器的 shell
docker compose exec postgres bash      # 进数据库容器的 shell
docker compose exec api python -c "..." # 在 api 容器里执行 Python 代码
```

### 镜像管理

```bash
docker images                     # 查看本地所有镜像
docker compose build --no-cache   # 强制重新构建（不用缓存）
docker system prune -a            # 清理未使用的镜像/容器/网络（腾空间用）
docker compose pull               # 拉取 docker-compose.yml 里的 image 更新
```

---

## 故障排查命令

### 容器起不来

```bash
docker compose logs chalab-nginx              # 看 Nginx 为什么崩溃
docker compose logs chalab-api --tail=100      # API 最后 100 行
docker compose logs chalab-postgres            # 数据库日志

# 如果容器状态是 "Restarting"：
docker inspect chalab-nginx | grep -A5 "State" # 看容器状态详情
```

### 网络问题

```bash
# 测试从宿主机到 Nginx
curl -v http://localhost

# 测试从宿主机直接到 API（跳过 Nginx）
curl http://localhost:8000/api/v1/imported_files    # API 没暴露端口，走不通是正常的

# 测试从 Nginx 容器内部到 API
docker compose exec nginx wget -qO- http://api:8000/api/v1/imported_files

# 测试从 API 容器到数据库
docker compose exec api python -c "import psycopg2; psycopg2.connect(host='postgres', dbname='chatdemopg', user='postgres', password='...')"

# 查看容器网络配置
docker network ls
docker network inspect chathistoryanalyst_default

# 查看端口占用
ss -tlnp | grep -E ':80|:8000|:8501|:5432'
```

### 数据库

```bash
# 连入 PostgreSQL
docker compose exec postgres psql -U postgres -d chatdemopg

# 常用 SQL
\dt                      # 列出所有表
SELECT * FROM langchain_pg_embedding LIMIT 5;
SELECT count(*) FROM langchain_pg_embedding;
\q                       # 退出
```

---

## 关键配置文件速查

### Dockerfile 核心模式

```dockerfile
FROM python:3.12-slim          # 基础镜像（最小够用原则）
WORKDIR /app                    # 工作目录
RUN ... && ... && rm -rf ...   # 合并写，清缓存
RUN pip install --no-cache-dir # 不缓下载包
COPY . .                        # 放最后（缓存友好）
```

### docker-compose.yml 核心模式

```yaml
services:
  db:
    image: xxx:tag             # 拉现成的镜像
    volumes:
      - named_vol:/data/dir    # 持久化数据
    healthcheck: ...           # 探活（给别的服务 depends_on 用）
    restart: unless-stopped

  app:
    build: .                   # 自己构建
    depends_on:
      db:
        condition: service_healthy  # 等 DB 真的就绪
    environment:
      KEY: ${FROM_ENV_FILE}    # 从 .env 读取
```

### nginx.conf 核心模式

```nginx
resolver 127.0.0.11 valid=30s ipv6=off;  # Docker DNS + 运行时解析

server {
    listen 80;
    server_name _;                        # IP 访问用占位符

    location / {
        set $upstream app:port;
        proxy_pass http://$upstream;      # 不带 URI！否则路径被替换
        proxy_set_header Upgrade $http_upgrade;  # WebSocket 支持
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;         # 长连接：24h
        proxy_buffering off;              # 实时流式响应
    }

    location /api {
        set $upstream api:port;
        proxy_pass http://$upstream;      # 注意：不带 /api 后缀
    }
}
```

---

## .env 文件模板

```bash
DASHSCOPE_API_KEY=sk-xxx        # 阿里 DashScope（Qwen 模型）
TAVILY_API_KEY=tvly-xxx         # Tavily 搜索
LANGSMITH_API_KEY=              # LangSmith 可观测性（可空）
PGSQLPASSWORD=your-password     # PostgreSQL 密码
```

---

## 部署检查清单

完整部署后，按顺序确认每一项：

```bash
# 1. 四个容器全部 Running
docker compose ps
# ✅ chalab-postgres   Up (healthy)
# ✅ chalab-api        Up
# ✅ chalab-streamlit  Up
# ✅ chalab-nginx      Up

# 2. Nginx 能访问 Streamlit
curl -I http://localhost
# ✅ HTTP/1.1 200 OK

# 3. API 能响应
curl http://localhost/api/v1/imported_files
# ✅ {"status":"success","imported_files":[...]}

# 4. 知识库已导入
docker compose exec postgres psql -U postgres -d chatdemopg \
  -c "SELECT count(*) FROM langchain_pg_embedding;"
# ✅ 返回一个数字（> 0 说明数据在）

# 5. 外部可访问
# 浏览器打开 http://<公网IP>
# ✅ 看到 ChatLab 粉色界面
```

---

## 常见错误速查

| 错误信息 | 原因 | 修复 |
|----------|------|------|
| `DeadlineExceeded ... docker.io` | Docker Hub 被墙 | 配镜像加速（daemon.json） |
| `host not found in upstream` | Nginx 在服务就绪前就尝试解析 DNS | 用 `resolver` + 变量 |
| `address already in use` | 端口被占用 | `ss -tlnp` 找占用者，停掉它 |
| `{"detail":"Not Found"}` | proxy_pass 带变量时的 URI 问题 | 去掉 proxy_pass 里的路径后缀 |
| `apt-get update` 超时 | Debian 源被墙 | Dockerfile 里 sed 改成阿里云源 |
| `pip install` 超时 | PyPI 被墙 | `pip install -i mirrors.aliyun.com` |
| WebSocket 连不上 | Nginx 没转发 Upgrade 头 | 加 `proxy_set_header Upgrade` |
| 页面加载后 "Please wait" | WebSocket 断了 | 检查 `proxy_buffering off` 和超时配置 |

---

## 阅读路线建议

| 如果你想... | 优先读 |
|-------------|--------|
| 理解 Docker 到底是什么 | 第 1 课 |
| 理解浏览器→服务器的完整数据路径 | 第 2 课 |
| 理解 Dockerfile 每一行的作用 | 第 3 课 |
| 理解 docker-compose.yml 如何编排多容器 | 第 4 课 |
| 理解 Nginx 反向代理的配置细节 | 第 5 课 |
| 从头到尾部署一遍 | 第 6 课 |
| 学习真实 bug 的排查思路 | 第 7 课 |
| 干活时快速查命令 | 第 8 课（本课） |

按照 1→2→3→4→5→6→7→8 顺序读是最完整的路径，大概 4-5 小时。
