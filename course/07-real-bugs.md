# 第七课：实战排错 —— 这次部署踩过的四个坑

真实世界的部署没有一次性成功的。这一课还原我们这次部署遇到的四个 bug——每个都有完整的症状、根因分析、排查思路和修复方式。

---

## Bug 1：Docker Hub 拉不到镜像

### 症状

```
DeadlineExceeded: failed to resolve source metadata for
docker.io/library/python:3.12-slim:
dial tcp 66.220.149.32:443: i/o timeout
```

### 发生了什么

`docker compose build` 的第一步就是 `FROM python:3.12-slim`——需要从 Docker Hub 拉基础镜像。Docker Hub 的域名 `registry-1.docker.io` 解析出的 IP 是 `66.220.149.32`（在美国）。从中国服务器直接访问这个 IP：GFW 在 TCP 层就阻断了握手（SYN 包发出去没有 SYN-ACK 回来）。

### 排查过程

1. 首先怀疑是网络问题：`ping registry-1.docker.io` → timeout
2. 确认是 GFW 问题：Docker Hub 的 IP 被墙，这是国内部署的经典障碍
3. 解决方案：Docker 镜像加速器（registry mirror）

### 修复

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

同时更新 `Dockerfile`，加了 apt 和 pip 的国内源，避免 `apt-get install` 和 `pip install` 也卡住：

```dockerfile
# apt 阿里云镜像
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && ...

# pip 阿里云镜像
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ ...
```

### 教训

- 国内服务器部署，**第一件事就是配镜像加速**
- Docker Daemon 层（daemon.json）解决 `docker pull` 的链路
- Dockerfile 层（sed + pip -i）解决 `apt-get` 和 `pip` 的链路
- 两层都要配，缺一不可

---

## Bug 2：Nginx 启动失败 —— host not found in upstream

### 症状

```bash
docker compose ps
# nginx: Restarting (1) 23 seconds ago

docker logs chalab-nginx
# [emerg] host not found in upstream "streamlit" in /etc/nginx/conf.d/default.conf:7
```

Nginx 容器不停重启，每次都在同一行报错。

### 发生了什么

Nginx 配置文件里写的是：

```nginx
proxy_pass http://streamlit:8501;
```

默认行为：**Nginx 在启动时解析 `streamlit` 这个域名**。但此时 streamlit 容器可能还没完全就绪（或者 Docker DNS 还没注册这个名字）。DNS 解析失败 → Nginx 认为配置无效 → 拒绝启动 → 容器退出 → Docker 的 `restart: unless-stopped` 把它重新拉起 → 又失败 → 死循环。

### 为什么 `depends_on` 没防止这个问题？

```yaml
nginx:
    depends_on:
      - api
      - streamlit    # 等 streamlit 先启动
```

`depends_on` 只保证**容器先创建**——但容器创建 ≠ 服务就绪。Docker Compose 启动 streamlit 容器后，容器内的 Streamlit 进程需要几秒钟才能开始监听 8501 端口。而 Nginx 可能在 Streamlit 就绪之前就开始解析 DNS 了。

更核心的原因：即使 Streamlit 已经正常运行，Docker DNS 注册也有一瞬间的延迟。Nginx 的**启动时一次解析**模式在这种动态环境里是脆弱的。

### 修复

把 Nginx 改成**运行时解析**模式：

```nginx
resolver 127.0.0.11 valid=30s ipv6=off;

location / {
    set $upstream streamlit:8501;
    proxy_pass http://$upstream;
```

关键变化：用变量 `$upstream` 使得 Nginx 不在启动时解析 DNS，而是在**每个请求到达时才解析**。如果某一次解析失败，只影响那个请求（502），Nginx 进程不会退出。几秒后 DNS 就绪，后续请求自动恢复。

### 教训

- Docker Compose 的 `depends_on` 只管容器创建顺序，不管服务就绪时间
- 高可用配置应该**容忍瞬时故障**（Nginx 不崩溃，请求报 502 然后重试），而不是**假设一切完美**
- `resolver 127.0.0.11` 是 Docker 网络环境下的标准做法

---

## Bug 3：API 返回 404

### 症状

```
curl http://localhost/api/v1/imported_files
# {"detail":"Not Found"}

# 但直接调 API 容器是可以的：
docker compose exec nginx wget -qO- http://api:8000/api/v1/imported_files
# {"status":"success","imported_files":[]}
```

API 容器自己工作正常，但经过 Nginx 就 404。说明 Nginx 的转发有问题。

### 发生了什么

我们最初的 nginx 配置是：

```nginx
location /api {
    set $upstream api:8000;
    proxy_pass http://$upstream/api;    # ← 注意末尾的 /api
}
```

Nginx 的 `proxy_pass` 在**带变量**和**不带变量**时行为不同：

**不带变量：** Nginx 做前缀替换
```
请求 /api/v1/imported_files
location /api 匹配
proxy_pass http://api:8000/api
→ 去掉前缀 /api → 剩余 /v1/imported_files
→ 拼上 proxy_pass 里的 /api → /api/v1/imported_files ✅
→ 转发到 http://api:8000/api/v1/imported_files
```

**带变量：** Nginx 完全替换 URI
```
请求 /api/v1/imported_files
location /api 匹配
proxy_pass http://$upstream/api   (因为 $upstream 是变量)
→ 整个请求 URI 被替换为 proxy_pass 里的 /api ❌
→ 转发到 http://api:8000/api
→ FastAPI 没有 /api 这个路由 → 404
```

Nginx 文档里对此行为的描述非常隐晦，绝大多数人不会注意到变量改变了 URI 替换逻辑。

### 修复

```nginx
proxy_pass http://$upstream;    # 去掉 /api，全路径透传
```

### 教训

- Nginx 的 `proxy_pass` 行为在加变量后会改变——这是文档里的一个细节陷阱
- Bug 3 是修复 Bug 2 时引入的（为了运行时 DNS 解析加了变量，顺手还写了路径尾缀）
- **每修一个 bug 都要重新做回归测试**——让 `curl` 走一遍完整链路

---

## Bug 4：80 端口被占用

### 症状

```bash
docker compose up -d
# Error response from daemon:
# failed to bind host port 0.0.0.0:80/tcp: address already in use
```

### 发生了什么

Docker 想占用宿主机的 80 端口（`ports: "80:80"`），但 80 端口已经被另一个程序占用了。用 `ss -tlnp | grep :80` 一看：

```
LISTEN 0 511 0.0.0.0:80  users:(("nginx",pid=3276,fd=6))
```

服务器上已经跑着一个宿主机的 Nginx。这是阿里云 ECS 的部分镜像预装的——他们可能在初始化脚本里装了 Nginx 做默认页面。

### 排查

```bash
# 1. 查看谁在用 80 端口
ss -tlnp | grep :80

# 2. 查看具体进程
systemctl status nginx

# 3. 确认这是预装的还是你自己装的
apt list --installed | grep nginx
```

### 修复

两个方案：

**方案 A**：停掉宿主机的 nginx，让 Docker 的 nginx 接管 80
```bash
sudo systemctl stop nginx
sudo systemctl disable nginx
```
注意 `disable` 很重要——否则服务器重启后宿主机 nginx 又起来了，Docker nginx 又被挡住。

**方案 B**：改 Docker nginx 的端口映射（比如 `8080:80`），让两者共存。但这对用户不友好——访问还得带端口号。

我们选了方案 A，因为我们的 nginx 在 Docker 里更好管理，而且和整个项目放在一起。

### 教训

- 云服务器的系统镜像可能在初始化时装了 nginx / apache 等
- 部署前先检查：`ss -tlnp | grep -E ':80|:443'`
- 即使决定了占端口，也要记得 `systemctl disable` 防重启复燃

---

## 排错方法论总结

这四个 bug 代表了部署中最常见的几类问题：

| 问题类型 | 例子 | 排查思路 |
|----------|------|----------|
| 网络不通 | Docker Hub 超时 | ping → 确认墙 → 找镜像/代理 |
| 服务启动顺序 | Nginx DNS 失败 | 看日志 → 确认依赖 → 改运行时解析 |
| 配置细节 | proxy_pass 404 | 二分法定位（直连容器 vs 经 Nginx）→ 看文档细节 |
| 资源冲突 | 端口被占 | `ss -tlnp` 定位占用者 → 停掉或换端口 |

**通用的三步排错法：**

1. **定位问题在哪一层**：比如 404，是 Nginx 没转到？还是 API 没处理？
   - 直接 curl API 容器 → 正常 → 问题在 Nginx 层
2. **看日志**：`docker logs <容器名>` 永远是最快的诊断方式
3. **最小化复现**：简化配置到只剩下问题相关的部分，快速试错

---

## 本课小结

| Bug | 根因 | 修复 |
|-----|------|------|
| Docker Hub 超时 | GFW 阻断了到美国 Docker Hub 的连接 | daemon.json 配国内镜像 + Dockerfile 改 apt/pip 源 |
| Nginx 反复重启 | 启动时 DNS 解析失败，进程直接退出 | resolver + 变量实现运行时解析 |
| API 返回 404 | proxy_pass 带变量 + 带 URI，路径被完全替换 | 去掉 URI 路径后缀 |
| 80 端口冲突 | 宿主机预装了 nginx 占着 80 | systemctl stop + disable 宿主机 nginx |

**下一课**：速查表 —— 常用命令、关键配置、快速排错。
