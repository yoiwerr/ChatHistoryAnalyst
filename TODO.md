# Deployment TODO — ChatLab 上线清单

按顺序从上往下做，做完一项勾一项。

---

## 步骤 1：把最新代码推到 GitHub

在本地开发机上执行：

```bash
cd ~/ChatHistoryAnalyst
git add .
git commit -m "上线准备：Streamlit 为主页，支持域名部署"
git push origin main
```

- [ ] 已推送

---

## 步骤 2：DNS 添加 A 记录

1. 登录你的域名服务商控制台（阿里云/腾讯云/Cloudflare 等）
2. 找到 **DNS 解析** 页面
3. 添加一条记录：

| 字段 | 值 |
|------|-----|
| 主机记录 | `@`（代表根域名） |
| 记录类型 | A |
| 记录值 | **你的服务器公网 IP** |
| TTL | 默认 600 |

4. 如果还需要 `www.你的域名.com`，再加一条 CNAME：

| 字段 | 值 |
|------|-----|
| 主机记录 | `www` |
| 记录类型 | CNAME |
| 记录值 | `@` |

5. 等 5-10 分钟，验证 DNS 生效：

```bash
ping 你的域名.com
# 应该返回你的服务器 IP
```

- [ ] DNS A 记录已添加
- [ ] ping 域名返回正确 IP

---

## 步骤 3：登录服务器，安装 Docker

SSH 登录服务器后执行：

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sudo bash

# 把自己加入 docker 组（之后不用 sudo）
sudo usermod -aG docker $USER

# 激活组权限（或直接重新 SSH 登录）
newgrp docker

# 安装 docker compose 插件
sudo apt update && sudo apt install docker-compose-plugin -y

# 检查安装
docker --version
docker compose version
```

- [ ] Docker 已安装
- [ ] docker compose 插件已安装

---

## 步骤 4：开放防火墙端口

```bash
# 服务器本地防火墙开放 80 端口
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

**此外，如果是阿里云/腾讯云，还需要在控制台操作：**

1. 进入 **安全组** 页面
2. 添加入方向规则：
   - 端口 `80`（HTTP），来源 `0.0.0.0/0`
   - 端口 `22`（SSH），来源 `0.0.0.0/0`
3. 保存

> HTTPS 配好后再回来加 443 端口。

- [ ] ufw 已开放 80
- [ ] 云控制台安全组已开放 80、22

---

## 步骤 5：克隆项目到服务器

```bash
# 用你的 GitHub 仓库地址替换 <your-repo-url>
git clone <your-repo-url> ~/ChatHistoryAnalyst
cd ~/ChatHistoryAnalyst
ls
# 确认能看到 Dockerfile、docker-compose.yml、scripts/ 等
```

- [ ] 项目已克隆到服务器

---

## 步骤 6：执行一键部署

```bash
cd ~/ChatHistoryAnalyst
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

脚本会依次：
1. 让你输入 API Key 和数据库密码，生成 `.env`
2. `docker compose build` 构建镜像
3. `docker compose up -d` 启动所有服务
4. 等待 API 就绪
5. 自动导入心理学知识库

如果 `.env` 已存在则会跳过输入，直接构建启动。

- [ ] 部署脚本执行成功
- [ ] 看到 "Deployment complete!"

---

## 步骤 7：验证部署

```bash
# 确认 4 个容器都在运行
cd ~/ChatHistoryAnalyst
docker compose ps
# 应该看到：chalab-nginx、chalab-streamlit、chalab-api、chalab-postgres

# 本地测试
curl http://localhost
# 应该返回 Streamlit 页面 HTML

curl http://localhost/api/v1/imported_files
# 应该返回 JSON（可能为空列表）
```

然后浏览器访问：`http://你的域名.com`

- [ ] 4 个容器全部 Running
- [ ] curl 测试通过
- [ ] 浏览器访问 ChatLab 界面正常

---

## 步骤 8：配置 HTTPS（用 Let's Encrypt 免费证书）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书并自动配置 nginx
sudo certbot --nginx -d 你的域名.com

# 按提示输入邮箱，同意条款，选择是否重定向 HTTP → HTTPS（建议选 2 redirect）
```

完成后 nginx 会自动加上 SSL。测试自动续期：

```bash
sudo certbot renew --dry-run
# 应该看到 "Congratulations"
```

最后在云控制台安全组添加端口 `443`（HTTPS）。

- [ ] certbot 已安装
- [ ] SSL 证书已获取
- [ ] `https://你的域名.com` 访问成功
- [ ] 安全组已开放 443
- [ ] 自动续期测试通过

---

## 完成后的访问地址

| 内容 | 地址 |
|------|------|
| ChatLab 主界面 | `https://你的域名.com` |
| API 文档 (Swagger) | `https://你的域名.com/api/docs` |
| API 接口 | `https://你的域名.com/api/v1/` |

---

## 日常维护命令

```bash
cd ~/ChatHistoryAnalyst

docker compose logs -f              # 实时查看所有日志
docker compose logs api             # 只看 API 日志
docker compose restart api          # 重启 API
docker compose restart streamlit    # 重启前端
docker compose down                 # 停止所有服务
docker compose up -d                # 启动所有服务
docker compose pull                 # 拉取最新基础镜像
docker compose up -d --build        # 重新构建并启动（更新代码后）
```

## 数据备份

```bash
# 备份数据库到本地文件
docker compose exec postgres pg_dump -U postgres chatdemopg > backup_$(date +%Y%m%d).sql

# 恢复（慎用）
docker compose exec -T postgres psql -U postgres chatdemopg < backup_20260523.sql
```
