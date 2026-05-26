# 第四课：Docker Compose —— 多容器编排

一个容器 = 一个服务，但我们的项目有四个服务。如果手动管理四个容器，你得开四个终端，记住四个启动命令、四个网络配置、四个数据卷——在真实项目中这完全不可维护。

Docker Compose 就是解决"多个容器怎么协作"的工具。

---

## 先看我们的完整配置

`docker-compose.yml`（完整文件）：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: chalab-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${PGSQLPASSWORD}
      POSTGRES_DB: chatdemopg
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d chatdemopg"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: .
    container_name: chalab-api
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000
    environment:
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY}
      TAVILY_API_KEY: ${TAVILY_API_KEY}
      LANGSMITH_API_KEY: ${LANGSMITH_API_KEY}
      PGSQLPASSWORD: ${PGSQLPASSWORD}
      DB_HOST: postgres
      DB_PORT: "5432"
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  streamlit:
    build: .
    container_name: chalab-streamlit
    command: streamlit run front/frontend.py --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false
    environment:
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY}
      TAVILY_API_KEY: ${TAVILY_API_KEY}
      LANGSMITH_API_KEY: ${LANGSMITH_API_KEY}
      PGSQLPASSWORD: ${PGSQLPASSWORD}
      DB_HOST: postgres
      DB_PORT: "5432"
      API_BASE_URL: http://api:8000/api/v1
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: chalab-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - api
      - streamlit
    restart: unless-stopped

volumes:
  pgdata:
```

65 行 YAML，定义了 4 个服务 + 1 个数据卷。一行一行拆。

---

## `services:` —— 定义你的容器

YAML 缩进表示层级。`services:` 下的每一项是一个独立的 Docker 容器。四个服务之间的关系：

```
postgres
    ↑ depends_on (condition: service_healthy)
    ├── api
    └── streamlit
            ↑ depends_on (默认: service_started)
          nginx
```

### 服务 1：postgres（数据库）

```yaml
postgres:
    image: pgvector/pgvector:pg16
```

- **`image`** 而不是 `build`：这个服务不需要我们写 Dockerfile，直接从 Docker Hub 拉现成的镜像
- **`pgvector/pgvector:pg16`**：PostgreSQL 16 + pgvector 扩展的官方镜像。`pg16` 是 tag（标签），代表 PostgreSQL 版本 16

```yaml
    container_name: chalab-postgres
```

固定容器名。不用这个的话 Docker Compose 会自动生成一个带项目名+数字的名字（如 `chathistoryanalyst-postgres-1`），不好记。

```yaml
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${PGSQLPASSWORD}
      POSTGRES_DB: chatdemopg
```

- 这些环境变量会被 pgvector 镜像的启动脚本读取，自动创建用户、密码、数据库
- `${PGSQLPASSWORD}` 这个语法是 Docker Compose 的**变量替换**——运行时会从 `.env` 文件里读取真实值

```yaml
    volumes:
      - pgdata:/var/lib/postgresql/data
```

**这是整个配置里最容易被忽视但最危险的配置。**

`- pgdata:/var/lib/postgresql/data` 的意思是：
- `pgdata` 是一个 Docker **named volume（命名卷）**
- 它被挂载到容器内的 `/var/lib/postgresql/data`
- PostgreSQL 的所有数据（表、索引、向量）都写在这个目录里

**如果没有这行会怎样？**
容器的文件系统是临时的——容器删了，数据就没了。你导入的聊天历史、向量嵌入全部灰飞烟灭。

**有了 volume 之后**：
- Volume 存储在宿主机上，独立于容器
- 容器删了再来一个新的，挂载同一个 volume，数据都在
- `docker compose down` 不会删 volume，`docker compose down -v` 才会

Volume 的实际位置在宿主机上的 `/var/lib/docker/volumes/chathistoryanalyst_pgdata/_data/`（Docker 自动管理的，你一般不需要直接操作）。

```yaml
    restart: unless-stopped
```

`restart` 策略选项：

| 值 | 行为 |
|----|------|
| `no` | 默认，挂了就挂了，不重启 |
| `always` | 每次挂都重启（包括 Docker 自己重启后） |
| `on-failure` | 只有异常退出才重启（退出码非 0） |
| `unless-stopped` | 只要你没手动 `docker stop` 它，它就一直重启 |

`unless-stopped` 最实用：服务挂了自动拉起来，但你明确说停的时候不会死灰复燃。

```yaml
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d chatdemopg"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**健康检查**是 Docker Compose 的一个关键特性。简单说就是 Docker 每隔 5 秒问一次数据库"你还活着吗？"。

`pg_isready` 是 PostgreSQL 自带的探活工具。Docker 执行这个命令：
- 返回 0 → 健康
- 返回非 0 → 不健康

5 秒检查一次，连续 5 次失败后标记为 unhealthy。

**为什么需要 healthcheck？** 看 api 服务的 `depends_on`：

---

### 服务 2：api（FastAPI 后端）

```yaml
api:
    build: .
    container_name: chalab-api
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000
```

- **`build: .`**：用当前目录的 Dockerfile 构建镜像。注意 api 和 streamlit 共用一个 Dockerfile，build 出来的镜像也一样，只是启动命令不同
- **`command`**：覆盖 Dockerfile 里的默认启动命令。这里指定用 uvicorn 启动 FastAPI
- **`--host 0.0.0.0`**：监听所有网络接口。如果在容器里用 `--host 127.0.0.1`，容器外的 Nginx 就访问不到它

```yaml
    depends_on:
      postgres:
        condition: service_healthy
```

这是整个配置里最精妙的设计之一。

普通的 `depends_on` 只保证"容器启动了"——但 PostgreSQL 进程启动了不等于数据库准备好接受连接了。数据库启动有个过程：初始化数据目录 → 启动 WAL → 加载共享内存 → 开始监听连接。这个过程通常要 2-5 秒。

**`condition: service_healthy`** 告诉 Docker："等 postgres 的 healthcheck 通过之后，再启动 api"。

没有这个条件的话，api 容器比 PG 就绪先起来，FastAPI 连不上数据库，可能直接崩溃。

---

### 服务 3：streamlit（前端）

```yaml
streamlit:
    build: .
    container_name: chalab-streamlit
    command: streamlit run front/frontend.py --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false
```

- `--server.enableCORS false`：禁用 CORS 检查，因为前端请求是通过 Nginx 代理过来的，源地址不是浏览器直接到 Streamlit
- `--server.enableXsrfProtection false`：禁用 CSRF 保护，因为在 Nginx 反向代理下这个保护会误拦正常请求

这两个关闭都是有理由的——不是偷懒。安全检查由 Nginx 层负责。

**为什么 `API_BASE_URL: http://api:8000/api/v1`？** 在 Docker 网络内，前端访问后端不走 Nginx，而是直接用 Docker 内部 DNS：`api:8000`。这样更快（少一跳），也更可靠（Nginx 挂了 API 还能用——虽然没人直接调 API）。

---

### 服务 4：nginx（反向代理）

```yaml
nginx:
    image: nginx:alpine
```

- `nginx:alpine`：基于 Alpine Linux 的 Nginx 镜像，**只有 ~10MB**。Nginx 本身就不需要什么系统依赖，用最小的镜像就行

```yaml
    ports:
      - "80:80"
```

只有 nginx 有 `ports`！其他三个服务都没有。这就是**单一入口**模式——所有外部流量必须经过 Nginx，内部服务不直接对外。

```yaml
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

这行把宿主机上的 `./nginx/nginx.conf`（项目目录下的 Nginx 配置）挂载到容器内的 `/etc/nginx/conf.d/default.conf`（Nginx 默认读取的配置位置）。

末尾的 **`:ro`** 是 **read-only**，意味着容器内不能修改这个文件。这是一个安全措施——万一 Nginx 被攻破，攻击者也改不了配置。

---

## `volumes:` —— 声明命名卷

```yaml
volumes:
  pgdata:
```

这是 Docker Compose 里**声明**一个命名卷。没有这行，Docker Compose 不知道 `pgdata` 是什么，引用它的 postgres 服务会报错。

Docker 会自动在宿主机上创建这个卷的实际存储位置。

---

## 变量替换：`${}` 和 `.env` 文件

docker-compose.yml 里大量的 `${XXX}` 会被 Docker Compose 在启动时替换成真实值。

读取优先级（由高到低）：
1. Shell 环境变量（`export DASHSCOPE_API_KEY=xxx`）
2. `.env` 文件（项目目录下的文件）
3. docker-compose.yml 中 `environment` 节写死的值

所以 `deploy.sh` 的第一件事就是让你输入 API Key，生成 `.env` 文件：

```bash
cat > .env <<EOF
DASHSCOPE_API_KEY=${DASHSCOPE_KEY}
TAVILY_API_KEY=${TAVILY_KEY}
PGSQLPASSWORD=${PG_PASS}
EOF
```

---

## `deploy.sh` 的三个核心命令

```bash
docker compose build      # 构建两个本地镜像 (api, streamlit)
docker compose up -d      # 启动所有服务（后台运行）
docker compose exec -T api python import_knowledge.py  # 导入知识库
```

- **`build`**：只有 `build: .` 的服务（api、streamlit）需要构建，`image:` 的服务（postgres、nginx）是直接拉现成的
- **`up -d`**：`-d` = detached（后台）模式。不加 `-d` 的话终端会被日志刷屏
- **`exec -T api python import_knowledge.py`**：在已运行的 api 容器里执行一条 Python 命令。`-T` 是 no-TTY（不需要交互式终端）

---

## 本课小结

| 你学到的 | 一句话解释 |
|----------|-----------|
| `services` | 每个 service = 一个容器 = 独立运行的进程 |
| `build: .` vs `image:` | 一个自己构建，一个拉现成的 |
| `depends_on` + healthcheck | 不只要等容器启动，要等服务真正就绪 |
| `volumes` | 数据持久化——容器删了数据不丢 |
| `ports` | 只有 nginx 暴露端口，其他走内部网络 |
| `restart: unless-stopped` | 挂了自己拉起来，除非你主动关 |
| `${VAR}` 变量替换 | compose 启动时从 .env 或环境变量读真实值 |
| docker compose up -d | 一条命令启动全部服务 |

**下一课**：Nginx 反向代理的原理，以及在变量模式下踩的一个坑。
