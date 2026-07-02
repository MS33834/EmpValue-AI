# EmpValue-AI 后端

基于 Python 3.11 + FastAPI + LangGraph 构建的 AI 员工价值评估后端服务。

---

## 目录结构

```
backend/
├── agent/            # LangGraph Agent 工作流
│   ├── graph.py      # 评估状态机与 interrupt 审批流
│   ├── prompt_loader.py
│   ├── state.py
│   └── tools.py      # Agent 可调用的记忆/知识库工具
├── api/              # FastAPI 路由
│   ├── auth_routes.py
│   ├── deps.py
│   └── routes.py
├── auth/             # JWT 认证与 RBAC
│   ├── jwt_handler.py
│   ├── password.py
│   └── rbac.py
├── core/             # 基础设施
│   ├── config.py
│   ├── database.py
│   ├── embeddings.py
│   ├── model_router.py
│   ├── multimodal/   # 多模态清洗与抽取
│   ├── providers/    # 模型 Provider 抽象
│   └── tracing.py
├── data/             # 演示数据
├── eval/             # LLM 回归评估脚本
├── memory/           # 向量记忆封装
├── models/           # SQLAlchemy 数据模型
├── prompts/          # Prompt 文件
├── schemas/          # Pydantic Schema
├── services/         # 业务服务
└── tests/            # 测试用例
```

---

## 本地开发

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入模型 API Key
```

### 3. 启动服务

```bash
uvicorn main:app --reload --port 8000
```

---

## 数据库迁移

项目使用 [Alembic](https://alembic.sqlalchemy.org/) 管理数据库结构迁移。

### 常用命令

```bash
# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 升级到最新版本
alembic upgrade head

# 回退一个版本
alembic downgrade -1

# 根据模型变更自动生成迁移脚本
alembic revision --autogenerate -m "描述本次变更"
```

也可以使用封装脚本：

```bash
python scripts/migrate.py upgrade
python scripts/migrate.py current
python scripts/migrate.py history
python scripts/migrate.py revision -m "描述本次变更" --autogenerate
```

数据库连接串从 `core.config.get_settings().database_url` 读取，可通过环境变量 `DATABASE_URL` 覆盖。

---

## 主要 API 概览

### 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 邮箱 + 密码登录 |
| POST | `/api/v1/auth/register` | 注册新用户 |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| POST | `/api/v1/auth/seed-demo-users` | 初始化演示账号 |

### 评估核心

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/inputs` | 提交日报/任务/附件等原始输入 |
| POST | `/api/v1/evaluations` | 异步触发评估，返回 job_id |
| GET | `/api/v1/evaluations/jobs/{job_id}` | 查询评估任务状态 |
| GET | `/api/v1/evaluations/{id}` | 查询评估结果（按角色过滤） |
| POST | `/api/v1/evaluations/{id}/approve` | 主管审批通过 |
| POST | `/api/v1/evaluations/{id}/reject` | 驳回评估 |
| POST | `/api/v1/evaluations/{id}/feedback` | 员工反馈/申诉 |
| POST | `/api/v1/evaluations/{id}/re-evaluate` | 基于反馈重新评估 |

### 看板与分析

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/employees/{id}/dashboard` | 个人成长看板 |
| GET | `/api/v1/employees/{id}/history` | 跨周期能力演进 |
| GET/POST | `/api/v1/teams/{id}/analytics` | 团队分析 |
| GET | `/api/v1/manager/dashboard` | 主管工作台 |
| GET | `/api/v1/manager/pending-approvals` | 待审批列表 |
| GET | `/api/v1/hr/audit-queue` | HR 复核队列 |

### 管理后台

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/admin/model-status` | 模型状态与推荐档位 |
| POST | `/api/v1/admin/model-switch` | 手动切换模型档位 |
| GET | `/api/v1/admin/audit-logs` | 审计日志查询 |

### LangGraph 原生 interrupt 审批流

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/evaluations-interrupt` | 启动带 interrupt 的评估 |
| GET | `/api/v1/evaluations-interrupt/{thread_id}/state` | 查询中断状态 |
| POST | `/api/v1/evaluations-interrupt/{thread_id}/resume` | 恢复并提交审批决策 |

---

## 角色与权限

| 角色 | 权限 |
|---|---|
| employee | 查看自己的员工视图、提交输入、反馈申诉 |
| manager | 审批、查看管理视图、团队分析 |
| hr | 复核异常评估、查看审计日志 |
| admin | 模型切换、查看全部审计日志 |

---

## 测试

```bash
# 单元测试（默认跑批，pytest.ini 已通过 --ignore=tests/perf 自动排除性能测试）
python -m pytest tests -q

# 只跑 E2E 测试（pytest.ini 中注册了 e2e marker，需依赖运行中的服务）
python -m pytest -m e2e -q

# 只跑单测、显式排除 E2E
python -m pytest --ignore=tests/e2e -q

# 使用 Mock Provider 跑通评估流程（无需 API Key）
python eval/evaluate.py --mock

# E2E 测试（需安装 Playwright 浏览器）
python -m pytest tests/e2e -q

# 性能测试（locust 需单独起服务，不纳入常规跑批）
locust -f tests/perf/locustfile.py
```

> 备注：`pytest.ini` 中已配置 `addopts = --ignore=tests/perf`，即常规 `pytest tests` 会自动跳过 `tests/perf`；同时注册了 `e2e` marker，可用 `pytest -m e2e` 精确筛选 E2E 用例。`tests/perf` 为 locust 性能测试，需要先单独启动被测服务后再运行，故不纳入常规跑批。

---

## 模型档位

| 档位 | 场景 | 模型示例 |
|---|---|---|
| auto | 根据硬件自动推荐 | - |
| L0 | 云端大模型 | GPT-4o / DeepSeek-V3 |
| L1 | 边缘小模型 | Qwen2.5-0.5B |
| L2 | 标准本地模型 | Qwen2.5-7B |
| L3 | 本地旗舰模型 | Qwen2.5-14B |

---

## 环境变量说明

详见 [.env.example](.env.example)。
