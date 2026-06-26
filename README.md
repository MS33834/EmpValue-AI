# EmpValue-AI

AI 驱动员工价值量化与成长 Agent 系统。

EmpValue-AI 面向中大型企业，通过持续接收员工多维工作数据（日报、任务进度、代码贡献、会议记录、截图、语音等），利用大语言模型 Agent 进行自动化深度分析，输出：

- **员工视角：** 客观、建设性的成长反馈；
- **管理视角：** 尖锐、战略性的人才诊断与调配建议；
- **审计视角：** 可追溯、可解释的评估依据。

系统支持基于企业算力环境的弹性本地部署，并严格遵循“人机协同”的企业级审批流。

---

## 核心价值

1. **双视角输出分离：** 同一次推理同时生成建设性员工视图与尖锐管理视图。
2. **弹性双模部署：** 根据硬件自动选择本地小模型或云端大模型，平衡成本、性能与合规。
3. **人机协同决策：** AI 不直接产生人事决策，所有结果必须经过人工审批。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│              前端交互层 (Vue 3 + Element Plus)                 │
│  员工端 │ 主管端 │ HR端 │ 管理后台                               │
├─────────────────────────────────────────────────────────────┤
│              API 网关层 (FastAPI)                              │
│  RBAC │ 限流 │ 审计日志 │ 护栏拦截 │ 路由分发                       │
├─────────────────────────────────────────────────────────────┤
│              Agent 编排层 (LangGraph)                         │
│  状态机 │ 工具调用 │ 记忆检索 │ 人工中断点                          │
├─────────────────────────────────────────────────────────────┤
│              模型抽象层 (ModelRouter)                          │
│  硬件探测 │ 云端 API │ 本地 LM Studio │ 自动降级                       │
├─────────────────────────────────────────────────────────────┤
│              数据与记忆层                                       │
│  SQLite/PostgreSQL │ ChromaDB │ Redis（预留）                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3 + JavaScript + Vite + Element Plus + ECharts |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy |
| Agent 编排 | LangGraph |
| 向量记忆 | ChromaDB |
| 关系型数据库 | SQLite（默认）/ PostgreSQL（生产） |
| 缓存 | Redis（预留，当前任务状态为内存存储） |
| 可观测性 | Langfuse |
| 测试 | pytest + locust |
| 部署 | Docker Compose |

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/MS33834/EmpValue-AI.git
cd EmpValue-AI
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入模型 API Key 等配置
```

### 3. Docker Compose 一键启动

```bash
docker compose up -d --build
```

启动后访问：

- 前端：`http://localhost`
- 后端 API：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

### 4. 本地开发

**后端：**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**前端：**

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

---

## 项目目录

```
.
├── backend/              # FastAPI 后端 + LangGraph Agent
│   ├── agent/            # Agent 工作流与状态机
│   ├── api/              # REST API 路由
│   ├── auth/             # JWT 认证与 RBAC
│   ├── core/             # 配置、模型路由、数据库、护栏
│   ├── eval/             # LLM 回归评估
│   ├── memory/           # 向量记忆
│   ├── models/           # SQLAlchemy 数据模型
│   ├── prompts/          # Prompt 文件与版本
│   ├── schemas/          # Pydantic Schema
│   ├── services/         # 业务服务
│   └── tests/            # 单元测试、E2E 测试、性能测试
├── frontend/             # Vue 3 前端
│   ├── src/views/        # 员工/主管/HR 页面
│   └── src/components/   # 可视化组件
├── docs/                 # 项目文档
├── docker-compose.yml    # 部署编排
└── EmpValue-AI-Project-Plan.md  # 完整开发计划
```

---

## 测试

```bash
# 后端单元测试
cd backend
python -m pytest tests -q

# 使用 Mock Provider 跑通评估流程（无需 API Key）
python eval/evaluate.py --mock

# E2E 测试（需安装 Playwright 浏览器）
python -m pytest tests/e2e -q
```

---

## 文档索引

- [开发计划书](EmpValue-AI-Project-Plan.md)
- [Prompt 工程规范](docs/prompt-engineering-spec-v1.md)
- [企业部署手册](docs/deployment-guide.md)
- [安全合规白皮书](docs/security-compliance-whitepaper.md)
- [后端开发说明](backend/README.md)
- [前端开发说明](frontend/README.md)
- [API 文档](backend/docs/openapi.json)（FastAPI 自动生成的 OpenAPI 规范）

---

## 同步推送

本仓库同时托管在 GitHub 与 GitCode。完成修改后执行：

```bash
./sync.sh
```

---

## 许可证

MIT License
