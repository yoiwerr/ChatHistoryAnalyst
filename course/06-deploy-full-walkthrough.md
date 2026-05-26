# 第六课：完整部署流程 —— 从 git push 到页面出现

这一课把前五课的知识串起来，按 TODO.md 的顺序走一遍完整部署，解释每步背后发生了什么。

---

## 部署全景图

```
你的本地开发机                     GitHub                       阿里云服务器
(Win11 + WSL)                   (git 远程仓库)                 (Ubuntu, 公网IP)
                                                                     │
┌──────────┐                    ┌──────────┐                  ┌───────▼───────┐
│ 写代码   │                    │ 存储代码 │                  │ 1. 装 Docker  │
│ git push │ ──── git push ──→ │ main分支 │ ←── git clone ── │ 2. git clone  │
└──────────┘                    └──────────┘                  │ 3. 配防火墙   │
                                                               │ 4. 一键部署   │
┌──────────┐                                                  │ 5. 验证       │
│ 你写     │                    ┌──────────┐                  └───────────────┘
│ Dockerfile│                   │  Docker  │                        │
│ compose  │                    │  Hub     │ ←── docker pull ───────┘
│ nginx    │                    │ (镜像库) │   python:3.12-slim
│ deploy   │                    │          │   nginx:alpine
└──────────┘                    └──────────┘   pgvector/pgvector:pg16
```

---

## 步骤 1：git push —— 把你的代码变成可传输的"包裹"

```bash
git add .
git commit -m "上线准备"
git push origin main
```

`git push` 做的事：
1. 计算每个文件变化的差分（diff）
2. 压缩差分数据
3. 通过 SSH/HTTPS 发送到 GitHub 的服务器
4. GitHub 更新远程仓库的 `main` 分支指针

这时候你的代码就有了一个**权威副本**在 GitHub 上。任何地方的任何机器，只要 `git clone` 或 `git pull` 就能拿到完全一样的代码。

**为什么用 git 而不是直接 scp 传文件？**
- Git 有**版本历史**：部署出错了可以 `git log` 看改动，或回滚到上一个版本
- Git 有**冲突解决**：多人协作时有合并机制
- Git 是最通用的传输方式：GitHub 全球 CDN，不管你服务器在哪，pull 都很快

---

## 步骤 2：安装 Docker —— 服务器端的"万能运行环境"

```bash
curl -fsSL https://get.docker.com | sudo bash
```

这个命令下载 Docker 官方安装脚本并执行。它做的具体事情：
1. 检测你的 Linux 发行版（Ubuntu/Debian/CentOS 等）
2. 添加 Docker 的 apt/yum 源
3. 安装 `docker-ce`（Docker 社区版）
4. 启动 `dockerd` 守护进程（后台一直跑着）
5. 创建 `docker` 用户组

`dockerd` 是 Docker 的核心进程。它常驻后台，负责：
- 管理所有镜像和容器
- 监听 `/var/run/docker.sock`（Docker CLI 通过这个 socket 和 daemon 通信）
- 管理网络（创建 docker0 网桥）
- 管理存储（创建 volumes）

```bash
sudo usermod -aG docker $USER
```

`docker` 组里的用户可以不用 `sudo` 执行 Docker 命令。原理：`docker.sock` 的权限是 `root:docker`，在 `docker` 组里就有权读写。

### 国内服务器特别步骤：镜像加速

```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF
sudo systemctl restart docker
```

Docker 默认从 `docker.io`（就是 Docker Hub）拉取镜像。Docker Hub 的服务器在国外，GFW 会阻断连接，表现为：

```
DeadlineExceeded: failed to resolve source metadata for
docker.io/library/python:3.12-slim: dial tcp 66.220.149.32:443: i/o timeout
```

**镜像加速器的工作原理：** 它在国内有一份 Docker Hub 热门镜像的缓存。Docker 拉镜像时先问加速器：
- 加速器有缓存 → 直接从国内服务器返回（快）
- 加速器没缓存 → 加速器替你去 Docker Hub 拉（它自己有梯子），拉回来缓存好再给你

`daemon.json` 是 Docker daemon 的配置文件，修改后必须 `systemctl restart docker` 生效。

---

## 步骤 3：开放防火墙 —— 让外面的人能找到你

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

云服务器的安全是**双重防火墙**架构：

```
公网 → [云平台安全组] → [服务器 ufw] → 你的程序
      阿里云/腾讯云控制台   服务器本地
```

**两层缺一不可。** 你经常在服务器上 `ufw allow` 了 80，但在阿里云控制台的安全组里没开 80，外面照样访问不到。

端口的决策：
- 80（HTTP）：必须开，网站入口
- 22（SSH）：必须开，不然你自己连不上服务器了
- **其他端口一律不开**——安全第一，最小暴露原则

---

## 步骤 4：git clone —— 把代码拉到服务器

```bash
git clone https://github.com/yoiwerr/ChatHistoryAnalyst.git ~/ChatHistoryAnalyst
```

服务器拿到的是和本地一模一样的代码。包括：
- `src/` 下所有 Python 代码
- `Dockerfile`
- `docker-compose.yml`
- `nginx/nginx.conf`
- `scripts/deploy.sh`
- `data/*.txt` 心理学参考数据

---

## 步骤 5：一键部署 —— deploy.sh 的执行时间线

```bash
./scripts/deploy.sh
```

### 5.1 生成 .env（约 30 秒，人工输入）

```bash
read -rp "DashScope API Key: " DASHSCOPE_KEY
cat > .env <<EOF
DASHSCOPE_API_KEY=${DASHSCOPE_KEY}
...
EOF
```

交互式读取你的 API Key，写入 `.env` 文件。`.env` 在 `.gitignore` 里——不会上传到 GitHub——所以每台服务器都需要单独创建。

**为什么不在代码里写死 API Key？** 因为代码要上传到 GitHub（公开仓库的话全人类都看见了）。`.env` 是每个部署环境的本地机密。

### 5.2 docker compose build（1-5 分钟）

```bash
docker compose build
```

Docker Compose 读取 `docker-compose.yml`，发现有 `build: .` 的服务（api 和 streamlit），开始构建：

```
1. 检查本地有没有 python:3.12-slim 镜像
   → 没有 → 从 Docker Hub / 镜像加速器拉取（约 1-2 分钟）

2. 逐层执行 Dockerfile:
   RUN apt-get install ...       # 下载系统包（约 30-60 秒）
   RUN pip install ...           # 下载 Python 包（约 1-2 分钟）
   COPY . .                      # 拷贝代码（< 1 秒）

3. 给构建好的镜像打标签:
   chathistoryanalyst-api:latest
   chathistoryanalyst-streamlit:latest
```

api 和 streamlit 用的是同一个 Dockerfile，所以 Docker 只会构建一次，然后给同一个镜像打两个标签。**注意**：`docker compose build` 是增量构建——如果代码没变（Dockerfile 和源码都没改），第二次 build 直接全缓存，秒级完成。

### 5.3 docker compose up -d（约 30 秒）

```bash
docker compose up -d
```

这是整个部署最核心的一条命令。它做的事：

```
docker compose up -d 的执行顺序：

1. 创建 Docker 网络 chathistoryanalyst_default
   → 子网 172.17.x.0/16
   → 内置 DNS 服务

2. 创建 volume chathistoryanalyst_pgdata
   → 实际路径：/var/lib/docker/volumes/chathistoryanalyst_pgdata/_data/

3. 启动 postgres 容器
   → 从 pgvector/pgvector:pg16 镜像启动
   → 设置环境变量（创建用户、密码、数据库）
   → 开始 healthcheck：每 5 秒执行 pg_isready

4. 等待 postgres 变为 healthy（最多 25 秒）

5. 启动 api 容器（depends_on postgres healthy）
   → uvicorn 开始监听 8000 端口
   → 内部地址：172.17.x.2:8000

6. 启动 streamlit 容器（depends_on postgres healthy）
   → streamlit 开始监听 8501 端口
   → 内部地址：172.17.x.3:8501

7. 启动 nginx 容器（depends_on api, streamlit started）
   → Nginx 读取配置，开始监听 80 端口
   → 宿主机 80 端口映射到这个容器

8. 所有容器 Running
```

`-d`（detach）参数让容器在**后台**运行。不加 `-d` 的话终端会打印所有容器的日志，你 Ctrl+C 就会停掉所有容器。

### 5.4 导入知识库（约 10 秒）

```bash
docker compose exec -T api python import_knowledge.py
```

这条命令在**已运行的 api 容器内部**执行 Python 脚本。`import_knowledge.py` 做的事：
1. 读取 `data/*.txt`（心理学参考资料）
2. 用 `langchain-text-splitters` 切成 500 字符的小块
3. 用 DashScope `text-embedding-v3` 做向量嵌入
4. 存入 PostgreSQL pgvector

**为什么要单独执行这一步，而不是放在 Dockerfile 里？**
因为这一步需要：
1. DashScope API Key（运行时才有）
2. PostgreSQL 数据库已就绪（容器启动后才有）

Dockerfile 构建时这两个条件都不满足。

---

## 步骤 6：验证部署

### 容器状态检查

```bash
docker compose ps
```

期望输出：四个容器 STATUS 全是 `Up`，postgres 后面带 `(healthy)`。

如果你看到某个容器的 STATUS 不是 `Up`，用 `docker logs <容器名>` 看日志。

### API 连通性验证

```bash
curl http://localhost/api/v1/imported_files
```

期望输出：`{"status":"success","imported_files":[]}`

`curl` 是一个命令行 HTTP 客户端。这一行验证了整条链路：
```
curl → localhost:80 → Docker 端口映射 → nginx 容器 → proxy_pass → api 容器 → FastAPI → 返回 JSON
```

如果返回 `{"detail":"Not Found"}`（我们踩过的坑）：说明请求到了 API，但路径错了——检查 nginx 的 proxy_pass 变量配置。

如果返回 `Connection refused`：说明 nginx 没起来——`docker logs chalab-nginx` 看原因。

### 浏览器访问

输入 `http://<公网IP>`，看到 ChatLab 粉色界面 → 部署成功。

---

## 本课小结

| 步骤 | 命令 | 耗时 | 做什么 |
|------|------|------|--------|
| 1. git push | `git push` | 5s | 代码上传到 GitHub |
| 2. 装 Docker | `curl get.docker.com \| bash` | 2min | 装 Docker daemon |
| 3. 镜像加速 | 写 daemon.json | 1min | 国内拉得动镜像 |
| 4. 开防火墙 | `ufw allow 80` | 10s | 外面能访问 |
| 5. 克隆代码 | `git clone` | 5s | 代码拉到服务器 |
| 6. 生成 .env | 交互输入 | 30s | API Key 就位 |
| 7. build | `docker compose build` | 3min | 构建镜像（有缓存秒过） |
| 8. up -d | `docker compose up -d` | 30s | 四个服务全部启动 |
| 9. 导入知识 | `docker compose exec` | 10s | 心理学参考数据入库 |
| 10. 验证 | `curl` + 浏览器 | 10s | 确认一切正常 |

总计：约 7 分钟，从头到尾不用手动配置任何 Python、PostgreSQL、Nginx。

**下一课**：这次部署踩过的四个真实 bug，以及怎么排查和修复的。
