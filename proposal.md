# ChatHistoryAnalyst 部署方案

## 目标

将 ChatHistoryAnalyst 部署到阿里云/腾讯云 Ubuntu 服务器，作为个人项目合集网站的第一个展示项目。同一服务器后续会增加其他项目，通过路由区分。

## 当前状态

- 项目本地运行正常（FastAPI :8000 + Streamlit :8501 + PostgreSQL）
- 服务器：刚购买，Ubuntu 20.04/22.04，公网 IP
- 无域名，暂用 IP 访问
- 服务器内存待确认（建议 ≥2G，否则 PostgreSQL 吃力）

## 架构设计

```
                    ┌──────────────┐
                    │   Nginx :80  │  (统一入口 + 反向代理)
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
       / → 静态站      /chatlab →     /api → 
       (Portfolio      Streamlit      FastAPI
        主页)           :8501          :8000
                                          │
                                          ▼
                                   PostgreSQL :5432
                                   (pgvector)
```

- **Nginx**：统一 80 端口入口，反向代理到各服务
- **Portfolio 主页**：一个轻量静态 HTML 页，展示项目卡片，后续扩展
- **ChatHistoryAnalyst**：Streamlit 前端 + FastAPI 后端 + PostgreSQL，保持原样
- **全部 Docker 容器化**，`docker compose up -d` 一键启动

## 受影响的文件

### 新增文件

| 文件 | 用途 |
|------|------|
| `Dockerfile.backend` | FastAPI 后端镜像 |
| `Dockerfile.frontend` | Streamlit 前端镜像 |
| `docker-compose.yml` | 编排所有服务（Nginx + API + Streamlit + PostgreSQL） |
| `nginx/nginx.conf` | Nginx 反向代理配置 |
| `portfolio/index.html` | Portfolio 静态主页（项目合集入口） |
| `scripts/deploy.sh` | 一键部署脚本（服务器端执行） |
| `.dockerignore` | Docker 构建忽略规则 |

### 需修改的文件

| 文件 | 改动 |
|------|------|
| `src/rag_function.py` | 数据库连接从 localhost 改为环境变量 `DB_HOST` |
| `src/core_llm.py` | 确认 DashScope API key 从环境变量读取（已支持） |
| `.env.example` | 补充部署相关环境变量说明 |

### 不受影响

- 所有 skill 文件、tools、schemas、frontend 逻辑代码不变
- 项目核心功能零改动

## 实施步骤

1. **创建 Dockerfile**：backend（FastAPI）和 frontend（Streamlit）各一个
2. **编写 docker-compose.yml**：4 个 service（nginx、api、streamlit、postgres）
3. **配置 Nginx**：路由规则 `/` → portfolio，`/chatlab` → streamlit，`/api` → fastapi
4. **创建 Portfolio 主页**：简洁 HTML 页，展示 ChatHistoryAnalyst 卡片，预留其他项目位置
5. **编写 deploy.sh**：服务器上 clone 项目 → 配置 .env → docker compose up
6. **测试**：本地 docker compose 验证，确认无误后服务器部署

## 端口规划

| 服务 | 容器内端口 | 宿主机暴露 |
|------|-----------|-----------|
| Nginx | 80 | 80 |
| FastAPI | 8000 | 仅容器网络 |
| Streamlit | 8501 | 仅容器网络 |
| PostgreSQL | 5432 | 仅容器网络 |

## 注意事项

- `.env` 文件不上传到 Git，服务器手动创建
- PostgreSQL 数据挂载到宿主机目录，防止容器销毁丢失数据
- Streamlit 通过 Nginx 反代时需要配置 WebSocket 支持
- 知识库 `data/*.txt` 需要首次部署后手动导入：`docker compose exec api python import_knowledge.py`
- 服务器安全组需开放 80 端口
