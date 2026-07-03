# EmpValue-AI

用大语言模型 Agent 给员工价值做量化评估，同时守住“AI 不替人下结论”这条线。

面向中大型企业，持续接收员工多维工作数据（日报、任务进度、代码贡献、会议记录、截图、语音），交给 LangGraph Agent 自动分析，一次推理同时产出三套视图：

- **员工视角：** 建设性成长反馈，给本人看；
- **管理视角：** 尖锐的人才诊断与调配建议，给主管 / HR 看；
- **审计视角：** 每条结论都带原始证据引用，可追溯、可解释。

三套视图刻意分离——同一个判断对员工说和给主管看，措辞和立场本就不该一样。部署上按企业算力在本地与云端间弹性切换，但所有评估结果必须经人工审批才能落地，这条是硬约束，不是 feature。

---

## 为什么这么设计

1. **双视角同源分离：** 一次推理同时生成员工视图和管理视图，逻辑一致；但语气、措辞、暴露范围严格隔离。员工看到的“成长空间”和主管看到的“ROI 下滑”来自同一份判断。
2. **弹性双模部署：** 按硬件自动在本地小模型与云端大模型间切换，保密和效果之间不留死结。
3. **AI 不做人事决策：** 合规底线，不是可选项。所有评估必须经主管审批，高风险项还要 HR 复核。

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

### 克隆仓库

```bash
git clone https://github.com/MS33834/EmpValue-AI.git
cd EmpValue-AI
```

### 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入模型 API Key 等配置
```

### Docker Compose 一键启动

```bash
docker compose up -d --build
```

启动后访问：

- 前端：`http://localhost`
- 后端 API：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

### 本地开发

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

> **Embedding 服务注意事项**
> 长期记忆走 ChromaDB + Embedding。**未配置 `EMBEDDING_API_KEY` 时，会自动回退到 `DummyEmbeddingFunction`（基于 md5 hash 的伪向量），该模式仅适合接口联调，检索结果无任何语义意义，不可用于真实检索与评估验证。生产环境必须配置真实的 Embedding 服务（如 OpenAI Embedding 或本地 Embedding 模型）。** 配置方式参见 `backend/.env.example` 与 [backend/README.md](backend/README.md)。

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
