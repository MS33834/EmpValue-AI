# EmpValue-AI 企业部署手册

> **版本：** v1.0  
> **适用对象：** 系统管理员、DevOps、安全合规人员  
> **目标：** 指导企业完成 EmpValue-AI 的内网/云端/混合部署

---

## 一、部署模式选择

| 模式 | 适用场景 | 数据是否出域 | 推荐规模 | 硬件要求 |
|---|---|---|---|---|
| **本地模式** | 高保密、无互联网环境 | 否 | ≤ 200 人 | 1× RTX 4090 / 64GB RAM |
| **云端模式** | 追求最强推理能力、快速试点 | 是 | 任意 | 应用服务器 16C32G |
| **混合模式** | 常规工作负载本地处理，复杂任务上云 | 部分 | 200-2000 人 | 本地 GPU + 云端 API |

> **建议：** 初次试点选择混合模式，常规评估使用本地 L2/L3 模型，复杂多模态分析调用云端 L0 模型。

---

## 二、环境准备

### 2.1 基础依赖

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- （可选）NVIDIA Container Toolkit（使用本地 GPU 时）

### 2.2 模型接入准备

**云端模型（L0）**

需准备以下任一 OpenAI 兼容接口：

- OpenAI API
- DeepSeek API
- 阿里云百炼
- 硅基流动

获取 API Key 后填入 `backend/.env` 的 `CLOUD_API_KEY`。

**本地模型（L1/L2/L3）**

推荐使用 LM Studio 或 Ollama：

1. 在内网服务器安装 LM Studio / Ollama；
2. 下载对应模型，如 `Qwen2.5-7B-Instruct`；
3. 启动本地 API 服务，默认地址 `http://localhost:1234/v1`；
4. 在 `backend/.env` 中配置 `LOCAL_BASE_URL` 与 `LOCAL_MODEL_L2`。

### 2.3 Embedding 服务

默认使用云端 Embedding（如 `text-embedding-3-small`）。如需本地部署：

- 使用 LM Studio / Ollama / Xinference 启动兼容接口；
- 在 `backend/.env` 中配置 `EMBEDDING_BASE_URL` 与 `EMBEDDING_MODEL`。

---

## 三、Docker Compose 部署

### 3.1 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/MS33834/EmpValue-AI.git
cd EmpValue-AI

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入实际 API Key 与模型地址

# 3. 启动全部服务
docker compose up -d --build
```

### 3.2 服务清单

| 服务 | 容器名 | 端口 | 说明 |
|---|---|---|---|
| backend | empvalue-backend | 8000 | FastAPI 后端 |
| frontend | empvalue-frontend | 80 | Vue3 前端（Nginx） |
| redis | empvalue-redis | 6379 | 缓存 |

### 3.3 持久化卷

| 卷名 | 用途 |
|---|---|
| empvalue_db_data | SQLite 数据库 |
| empvalue_chroma_data | 向量库 |
| empvalue_redis_data | Redis 数据 |
| empvalue_attachments | 本地附件（如上传的截图、语音、PDF） |

### 3.4 健康检查

```bash
curl http://localhost:8000/health
```

预期返回：

```json
{"status": "ok"}
```

### 3.5 数据库迁移（可选）

容器首次启动时会在 `lifespan` 中自动创建数据表（基于 SQLAlchemy metadata），因此快速体验无需手动迁移。

如需显式使用 Alembic 管理版本（推荐生产环境），配置文件位于 `backend/alembic.ini`，迁移脚本位于 `backend/alembic/versions/`：

```bash
# 进入 backend 目录后执行
cd backend
python scripts/migrate.py upgrade
# 或
alembic -c alembic.ini upgrade head
```

> `backend/alembic.ini` 中的数据库连接串会被 `backend/alembic/env.py` 自动替换为 `backend/.env` 里的 `DATABASE_URL`。

---

## 四、生产环境增强

### 4.1 使用 PostgreSQL 替代 SQLite

编辑 `backend/.env`：

```env
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/empvalue
```

并在 `docker-compose.yml` 中加入 PostgreSQL 服务：

```yaml
  postgres:
    image: postgres:15-alpine
    container_name: empvalue-postgres
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: empvalue
    volumes:
      - empvalue_pg_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  empvalue_pg_data:
```

### 4.2 使用 MinIO 作为对象存储

用于存储原始附件（截图、语音、PDF）。在 `docker-compose.yml` 中加入：

```yaml
  minio:
    image: minio/minio:latest
    container_name: empvalue-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - empvalue_minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    restart: unless-stopped

volumes:
  empvalue_minio_data:
```

### 4.3 启用 GPU（本地模型）

在 `docker-compose.yml` 的 backend 服务中添加：

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

并确保已安装 NVIDIA Container Toolkit。

### 4.4 HTTPS 与反向代理

生产环境应在 Nginx / Traefik / APISIX 后面部署，配置 TLS 1.3：

```nginx
server {
    listen 443 ssl http2;
    server_name empvalue.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.3;

    location / {
        proxy_pass http://empvalue-frontend;
    }

    location /api/ {
        proxy_pass http://empvalue-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 五、配置管理

### 5.1 环境变量清单

| 变量 | 必填 | 说明 |
|---|---|---|
| `MODEL_TIER` | 否 | 模型档位：auto / L0 / L1 / L2 / L3 |
| `CLOUD_API_KEY` | 使用云端时 | 云端模型 API Key |
| `CLOUD_BASE_URL` | 使用云端时 | 云端模型 Base URL |
| `CLOUD_MODEL` | 使用云端时 | 云端模型名 |
| `OPENAI_API_KEY` | 使用旧版 OpenAI 时 | 兼容旧命名，未配置 `CLOUD_*` 时兜底 |
| `OPENAI_BASE_URL` | 使用旧版 OpenAI 时 | 兼容旧命名 |
| `OPENAI_MODEL` | 使用旧版 OpenAI 时 | 兼容旧命名 |
| `LOCAL_BASE_URL` | 使用本地时 | 本地模型 API 地址 |
| `LOCAL_API_KEY` | 使用本地时 | 本地模型 API Key |
| `LOCAL_MODEL_L1` | 使用本地时 | L1 档位模型名 |
| `LOCAL_MODEL_L2` | 使用本地时 | L2 档位模型名 |
| `LOCAL_MODEL_L3` | 使用本地时 | L3 档位模型名 |
| `EMBEDDING_API_KEY` | 是 | Embedding 服务 Key |
| `EMBEDDING_BASE_URL` | 是 | Embedding 服务地址 |
| `EMBEDDING_MODEL` | 否 | Embedding 模型名，默认 `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | 否 | Embedding 维度，默认 `1536` |
| `DATABASE_URL` | 否 | 数据库连接串 |
| `VECTOR_STORE_DIR` | 否 | 向量库存储路径 |
| `ATTACHMENT_DIR` | 否 | 附件本地存储根目录 |
| `TEMPERATURE` | 否 | LLM 推理温度，默认 `0.1` |
| `MAX_TOKENS` | 否 | LLM 最大输出 token，默认 `4096` |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥，生产环境必须修改 |
| `JWT_ALGORITHM` | 否 | JWT 算法，默认 `HS256` |
| `JWT_EXPIRE_MINUTES` | 否 | Token 有效期，默认 `1440` |
| `AUTH_DEMO_MODE` | 否 | 演示模式，生产必须 `false` |
| `LANGFUSE_PUBLIC_KEY` | 否 | Langfuse 公钥 |
| `LANGFUSE_SECRET_KEY` | 否 | Langfuse 私钥 |
| `LANGFUSE_HOST` | 否 | Langfuse 地址 |

### 5.2 模型档位策略

```env
# 完全本地保密
MODEL_TIER=L2

# 混合：自动选择
MODEL_TIER=auto

# 云端最强能力
MODEL_TIER=L0
```

---

## 六、初始化与验证

### 6.1 创建演示账号

> 注意：`seed-demo-users` 接口仅在 `AUTH_DEMO_MODE=true` 时可用。启动前请在 `backend/.env` 中设置：
>
> ```env
> AUTH_DEMO_MODE=true
> ```
> 生产环境必须关闭演示模式并修改默认密码。

```bash
curl -X POST http://localhost:8000/api/v1/auth/seed-demo-users
```

默认账号：

| 邮箱 | 角色 | 默认密码 |
|---|---|---|
| employee@empvalue.ai | employee | empvalue123 |
| manager@empvalue.ai | manager | empvalue123 |
| hr@empvalue.ai | hr | empvalue123 |
| admin@empvalue.ai | admin | empvalue123 |

> 生产环境必须删除此接口并修改默认密码。

### 6.2 提交一条测试输入

```bash
curl -X POST http://localhost:8000/api/v1/inputs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <employee_token>" \
  -d '{
    "employee_id": "E1001",
    "period": "2026-W25",
    "type": "daily_report",
    "content": "本周完成了用户画像模块重构，性能提升40%；辅导两名新人完成Code Review。"
  }'
```

### 6.3 触发一次评估

```bash
curl -X POST http://localhost:8000/api/v1/evaluations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <employee_token>" \
  -d '{
    "employee_id": "E1001",
    "period": "2026-W25"
  }'
```

返回 `job_id`，通过 `/api/v1/evaluations/jobs/{job_id}` 查询结果。

---

## 七、监控与运维

### 7.1 日志查看

```bash
# 全部服务日志
docker compose logs -f

# 仅后端
docker compose logs -f backend
```

### 7.2 备份策略

| 数据 | 备份方式 | 频率 |
|---|---|---|
| SQLite / PostgreSQL | 数据库备份 | 每日 |
| ChromaDB 向量库 | 卷快照 | 每日 |
| Redis | AOF + RDB | 每日 |
| 原始附件 | MinIO/OSS 跨区域复制 | 实时 |

### 7.3 升级流程

```bash
# 1. 拉取新版本
git pull origin main

# 2. 重新构建并启动
docker compose down
docker compose up -d --build

# 3. 验证健康检查
curl http://localhost:8000/health
```

---

## 八、故障排查

### 8.1 后端无法启动

- 检查 `.env` 是否配置正确；
- 查看 `docker compose logs backend`；
- 确认数据库目录权限。

### 8.2 模型调用失败

- 检查 API Key 是否有效；
- 检查模型 Base URL 是否可达；
- 查看 `/api/v1/admin/model-status` 当前档位。

### 8.3 前端无法访问 API

- 确认 CORS 配置包含前端域名；
- 检查 Nginx 反向代理配置；
- 确认后端服务健康。

---

## 九、安全基线

- 所有服务仅暴露必要端口；
- 使用 TLS 1.3 加密传输；
- 数据库密码、API Key 通过环境变量或密钥管理服务注入；
- 定期更新基础镜像与依赖；
- 启用审计日志并归档。

---

## 十、获取支持

- 项目仓库：https://github.com/MS33834/EmpValue-AI
- 问题反馈：通过仓库 Issue 提交
