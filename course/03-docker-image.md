# 第三课：Docker 镜像 —— Dockerfile 逐行精讲

上一课我们讲了请求怎么到达容器，这一课讲容器本身是怎么造出来的。

镜像就是容器的"源代码"。Dockerfile 就是写镜像的"编程语言"。

---

## 我们项目的 Dockerfile（完整 14 行）

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 国内镜像加速：Debian apt 源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 国内镜像加速：pip
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    dashscope fastapi langchain langchain-community langchain-openai \
    "langchain-postgres[async]" langchain-tavily langchain-text-splitters \
    psycopg2-binary pydantic python-dotenv requests streamlit uvicorn

COPY . .
```

14 行代码。但每一行的背后，都是一个精心设计的 Docker 机制。

---

## 第 1 行：`FROM python:3.12-slim`

### 这是什么

`FROM` 是 Dockerfile 的起点——"在我之前，先准备好什么"。

`python:3.12-slim` 是一个官方的 Python 镜像，存储在 Docker Hub 上。它包含了：
- Debian Linux 最小化系统
- Python 3.12 解释器
- `pip` 包管理器
- 基础的系统工具

### 为什么是 python:3.12-slim 而不是 python:3.12？

Python 官方提供了多个变体：

| 镜像 | 大小 | 包含内容 |
|------|------|----------|
| `python:3.12` | ~1 GB | Debian + Python + 编译工具链 + 文档 + 杂七杂八 |
| `python:3.12-slim` | ~150 MB | Debian 最小化版 + Python |
| `python:3.12-alpine` | ~50 MB | Alpine Linux(极简) + Python |

我们选 `slim` 是一个折中：
- `slim` 基于 Debian，包管理用 `apt-get`，兼容性最好
- 比完整版小 85%，但仍然包含了所有必要的系统库
- Alpine 虽然最小，但用的是 `musl libc`（不是标准的 `glibc`），有些 Python 包会出兼容问题，尤其是 `psycopg2` 这种数据库驱动

**一句话：150MB 足够小，Debian 足够稳。**

### 镜像分层存储

执行 `FROM python:3.12-slim` 时，Docker 不会重新造一个 Python——而是从 Docker Hub 下载已经做好的镜像层（layers）。

```
python:3.12-slim 镜像的层结构（简化）：
┌──────────────────────────┐
│ Layer 5: Python 3.12     │  ← 最后一个层
├──────────────────────────┤
│ Layer 4: pip, setuptools │
├──────────────────────────┤
│ Layer 3: ca-certificates │
├──────────────────────────┤
│ Layer 2: apt 包管理      │
├──────────────────────────┤
│ Layer 1: Debian 根文件系统│  ← 第一个层
└──────────────────────────┘
```

这个"分层"设计是 Docker 最核心的创新之一。每个层是只读的，Docker 用一个叫 **UnionFS（联合文件系统）** 的技术把它们叠加在一起。当你"修改"一个文件时，实际是在最上面加了一个新层，旧层还留着，只不过被新层"遮挡"了。

**这个设计带来的好处：**
1. 多个镜像可以共享相同的底层（比如都基于 python:3.12-slim，底层只需要存一份）
2. 重新构建时，没变的层可以直接用缓存，不用重建

---

## 第 2 行：`WORKDIR /app`

设置工作目录。相当于 `mkdir /app && cd /app`。

后续所有的 `RUN`、`COPY`、`CMD` 指令都在 `/app` 下执行。这是一个最佳实践——把所有项目文件集中在一个地方，不污染系统根目录。

---

## 第 3-6 行：第一个 `RUN` 块

```dockerfile
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

### 逐字拆解

| 命令 | 作用 |
|------|------|
| `sed -i 's/deb.../mirrors.../g'` | 把 Debian 的软件源从国外改成阿里云镜像。**不换这一行，国内服务器 `apt-get update` 要等 15 分钟甚至超时。** |
| `apt-get update` | 更新软件包列表 |
| `apt-get install -y --no-install-recommends` | 安装包，`-y` 是不问"确认吗"，`--no-install-recommends` 是只装必需的依赖 |
| `build-essential` | 编译器工具链（gcc, make 等）。很多 Python 包需要从 C 源码编译 |
| `libpq-dev` | PostgreSQL 的 C 语言客户端库。`psycopg2`（Python 连 PG 的驱动）需要它 |
| `rm -rf /var/lib/apt/lists/*` | 删除 apt 的包列表缓存。这些文件用完就没用了，删掉能省几十 MB |

### 为什么这些全写在一个 `RUN` 里，用 `&&` 连起来？

**因为每个 `RUN` 创建一个新镜像层。** 分三个 `RUN` 写的话：

```dockerfile
# 错误示范：三个 RUN = 三个层
RUN sed -i ...
RUN apt-get update && apt-get install...
RUN rm -rf /var/lib/apt/lists/*
```

第一个 RUN 改了源文件 → 创建一个层（含源文件）
第二个 RUN 下载安装包 → 创建一个层（含 `.deb` 安装缓存）
第三个 RUN 删缓存 → 创建一个层（但旧层里的缓存并没消失！）

**镜像的总大小 = 所有层的叠加。** 在第二层下载的缓存，虽然在第三层被"标记删除"，但数据还在第二层里，镜像大小没减少。

写成一行 `&& rm -rf` 则缓存在同一个层里被真实删除了，不进入镜像。

**一句话：`RUN` 合并到一行 = 镜像更小。**

---

## 第 8-11 行：第二个 `RUN` —— 安装 Python 依赖

```dockerfile
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    dashscope fastapi langchain langchain-community langchain-openai \
    "langchain-postgres[async]" langchain-tavily langchain-text-splitters \
    psycopg2-binary pydantic python-dotenv requests streamlit uvicorn
```

### 逐标记拆解

| 标记 | 作用 |
|------|------|
| `--no-cache-dir` | 不保存 pip 下载缓存。同样是为了减小镜像体积 |
| `-i https://mirrors.aliyun.com/pypi/simple/` | pip 源换成阿里云。不用这行国内基本装不上 |
| `--trusted-host mirrors.aliyun.com` | pip 默认只信任 HTTPS 的官方源。阿里云虽然也是 HTTPS，但证书域名对不上，所以要加这个 |

### 为什么 psycopg2-binary 而不是 psycopg2？

- `psycopg2`：需要本地编译，依赖 `libpq-dev`、`gcc`
- `psycopg2-binary`：预编译好的二进制包，开箱即用

因为我们已经在上一行装了 `libpq-dev`，两者都可以。用 `binary` 版少一次 C 编译，构建更快。

### 包清单说明

```
dashscope         ← 阿里灵积平台 SDK，我们用它调用 Qwen 模型
fastapi           ← Python Web 框架，REST API
langchain         ← AI Agent 开发框架，我们用它构建三个 Skill Agent
langchain-community      ← LangChain 社区集成
langchain-openai         ← LangChain 的 OpenAI 兼容接口（DashScope 用的是兼容协议）
langchain-postgres[async]← LangChain 的 PGVector 集成，[async] 表示支持异步
langchain-tavily         ← Tavily 搜索引擎集成
langchain-text-splitters ← 文本切片工具
psycopg2-binary   ← PostgreSQL Python 驱动
pydantic          ← 数据校验（FastAPI 的核心依赖）
python-dotenv     ← 读取 .env 文件
requests          ← HTTP 客户端
streamlit         ← 前端 UI 框架
uvicorn           ← ASGI 服务器，跑 FastAPI
```

---

## 第 13 行：`COPY . .`

把当前目录（项目根目录）的所有文件拷贝到容器的 `/app` 下。

第一个 `.` = 宿主机上的项目根目录
第二个 `.` = 容器的 `/app`（因为前面 `WORKDIR /app`）

### 一个重要的优化原则

你有没有注意到，`COPY . .` 在最后一行？

```dockerfile
FROM python:3.12-slim        # 很少变
RUN apt-get install ...       # 偶尔变（加了新系统依赖才会变）
RUN pip install ...           # 偶尔变（加了新 pip 包才会变）
COPY . .                      # 经常变（每次改代码都变）
```

这是刻意安排的。Docker 构建镜像时，从上往下逐层执行。**如果某一层的输入没变，Docker 会直接使用缓存，跳过重建。**

如果把 `COPY . .` 放前面：

```dockerfile
# 错误示范
COPY . .                      # 代码每次改，这层每次都重建
RUN pip install ...           # 这层也得重建（因为上层变了）← 浪费！
```

你只改了一行 Python 代码，却要重新下载安装所有 pip 包——因为 Docker 缓存从 `COPY` 行的位置断掉了。

**把变化频率高的放后面 = 最大化缓存利用 = 构建更快**。

---

## build 过程的完整视图

当你执行 `docker compose build` 时，发生了什么：

```
Step 1/5: FROM python:3.12-slim
  → 拉取 python:3.12-slim（或从本地缓存加载）

Step 2/5: WORKDIR /app
  → 设置工作目录

Step 3/5: RUN apt-get update && apt-get install ... && rm -rf ...
  → 创建临时容器 → 执行命令 → 保存为新镜像层 → 删除临时容器
  → 耗时主要由网络决定（国内需要阿里云镜像加速）

Step 4/5: RUN pip install ...
  → 同上，但注意 --no-cache-dir 避免了 pip 缓存进入镜像

Step 5/5: COPY . .
  → 将当前目录内容拷贝到镜像

最后：命名镜像为 chathistoryanalyst-api 和 chathistoryanalyst-streamlit
```

你看到的输出对应这些步骤：

```
#10 [api 3/5] RUN apt-get update && ...   ← 系统包安装（最耗时，因为要下载）
#10 CACHED                                 ← 如果源代码没变，直接用缓存！
```

---

## 本课小结

| 你学到的 | 一句话解释 |
|----------|-----------|
| `FROM` | 指定基础镜像，所有 Dockerfile 的第一行 |
| slim 镜像 | 完整版 vs 瘦身版的取舍 —— 选最小的够用的 |
| 镜像分层 | 每个指令一个层，层是只读的，用 UnionFS 叠加 |
| RUN 合并写 | 多个 RUN 用 `&&` 连起来 → 一个层 → 更小的镜像 |
| COPY 放最后 | 把最不常变的放前面 → 最大化缓存 → 构建更快 |
| `--no-cache-dir` | pip 不保留下载缓存 → 镜像更小 |
| 国内镜像源 | 阿里云 apt/pip 源是部署在中国服务器的第一道坎 |

**下一课**：Docker Compose 怎么把 4 个容器编排在一起？
