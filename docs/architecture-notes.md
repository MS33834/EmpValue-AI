# 架构实现说明（Architecture Notes）

本文件记录 EmpValue-AI 项目在落地过程中，相对于《EmpValue-AI-Project-Plan.md》计划书的若干**架构实现偏差与演进决策**。目的是让计划书与实际实现保持可追溯的一致性，避免后续团队按计划书字面描述去寻找并不存在的代码而踩坑。

所有偏差均为**有意识的取舍**，已在下文给出理由、影响与后续演进路径。当前 MVP 阶段不引入重依赖，优先保证测试轻量与可移植性。

---

## 1. FEEDBACK_COLLECT 节点的实现方式（对应计划书 4.4）

### 计划书描述

《EmpValue-AI-Project-Plan.md》第 4.4 节描述的 Agent 工作流（LangGraph）如下：

```
[RAW_DATA] → [DATA_CLEANING] → [CONTEXT_RETRIEVAL] → [AI_PROCESSING]
→ [AI_DRAFTED] → [MANAGER_REVIEW] → [HR_AUDIT] → [APPROVED]
→ [FEEDBACK_COLLECT]   ← 收集员工反馈与申诉
```

其中 `[FEEDBACK_COLLECT]` 被画作评估主流程内的一个节点。

### 实际实现

**实际实现见本文件，未在 `backend/agent/graph.py` 中实现为图节点。** 反馈与申诉改由 **API 层端点** 实现，作为评估主流程之外的异步入口：

| 能力 | 实际实现端点（`backend/api/routes.py`） | 说明 |
|---|---|---|
| 员工提交反馈 | `POST /api/v1/evaluations/{evaluation_id}/feedback` | 写入 Feedback 表，type=feedback |
| 员工申诉 | `POST /api/v1/evaluations/{evaluation_id}/appeal` | 状态机回退到 manager_review，并写入 type=appeal 的 Feedback 记录 |
| 基于反馈重评 | `POST /api/v1/evaluations/{evaluation_id}/re-evaluate` | 收集原始输入 + 反馈，重新跑评估图生成新 AI 草稿 |
| 反馈查询 | `GET /api/v1/evaluations/{evaluation_id}/feedback`、`GET /api/v1/employees/{employee_id}/feedback` | 员工/管理端追踪申诉处理进度 |

### 偏差理由

1. **反馈是异步触发，而非评估流内节点。** 计划书把 FEEDBACK_COLLECT 画作 APPROVED 之后的串行节点，但实际业务中员工反馈/申诉发生在评估**发布之后**的任意时间点（可能数小时甚至数天后），且并非每条评估都会触发。若将其做成图内节点，主评估流会被迫阻塞等待一个大概率不发生的事件，语义错配。
2. **API 层实现更灵活。** 反馈入口需要独立的鉴权（员工只能对本人评估申诉）、审计日志、状态机回退与 Feedback 表持久化，这些都是 API 层的职责，而非图节点的职责。
3. **不阻塞主评估流。** 评估图跑完 APPROVED 即结束，员工反馈通过独立端点进入，由 `re-evaluate` 端点按需重新触发评估图，二者解耦。
4. **避免破坏现有测试。** `graph.py` 已被 526 个测试覆盖，强行插入 FEEDBACK_COLLECT 节点会破坏现有图结构与测试断言。

### 结论

计划书 4.4 的 FEEDBACK_COLLECT 节点在实现上**等价收敛**为 API 层的一组 REST 端点 + Feedback 表 + 状态机回退动作，功能完整且可审计。计划书的流程图应理解为业务流程图而非严格的图节点拓扑。

---

## 2. TestContainers 集成测试策略（对应计划书 L4）

### 计划书描述

计划书提到使用 TestContainers 进行集成测试（真实 PostgreSQL / ChromaDB 容器）。

### 实际实现

**当前 MVP 不引入 TestContainers 依赖。** 集成测试采用更轻量的方案：

- **数据库**：内存 SQLite（`aiosqlite`），通过 `core/database.py` 的 `AsyncSessionLocal` 在测试 fixture 中替换为内存引擎，无需真实 PostgreSQL 容器。
- **向量库**：`DummyEmbeddingFunction` + 内存 ChromaDB / 内存向量存储，避免依赖真实嵌入模型与持久化 ChromaDB 服务。
- **模型**：`MockProvider`（见 `eval/evaluate.py`），不调用真实 LLM API。

### 偏差理由

1. **沙箱环境无法运行 Docker-in-Docker。** CI 沙箱与本地开发环境通常不具备 Docker 守护进程，TestContainers 依赖 Docker API 启动容器，在沙箱中无法运行。
2. **TestContainers 是重依赖。** 它会拉起真实容器、占用端口与内存，单次测试启动耗时数十秒，显著拖慢 526 个测试的反馈循环。
3. **内存方案已能覆盖核心逻辑。** 当前测试重点验证业务逻辑（评估流、审批状态机、反馈链路、护栏），内存 SQLite + DummyEmbedding 足以覆盖；真实容器仅在验证数据库方言差异、ChromaDB 持久化、并发连接池等基础设施行为时才有必要。

### 演进路径

TestContainers 作为**生产环境可选增强**保留：当需要验证 PostgreSQL 方言特异性（如 JSONB 索引、并发锁）或 ChromaDB 真实持久化行为时，可在独立的 `tests/integration/` 目录下引入 TestContainers，并标注 `@pytest.mark.integration`，默认不纳入常规 CI 流水线，避免拖慢开发反馈循环。当前 MVP 阶段不引入。

---

## 3. 任务队列现状与演进路径（对应计划书 M3）

### 现状

`backend/api/routes.py` 中评估异步任务状态存储为**进程内内存字典**：

```python
# 评估异步任务状态存储（生产环境应替换为 Redis / 数据库）
job_store: Dict[str, Dict[str, Any]] = {}
```

`POST /api/v1/evaluations` 接收请求后生成 `job_id`，写入 `job_store`，并通过 FastAPI `BackgroundTasks` 在后台执行评估图，结果回写 `job_store`。`GET /api/v1/evaluations/jobs/{job_id}` 从 `job_store` 查询状态。

### 约束

- **单实例约束**：`job_store` 是进程内内存，**不支持多实例水平扩展**。若部署多个后端实例，请求可能落到 A 实例而任务状态在 B 实例，导致 404。
- **重启丢失**：进程重启后 `job_store` 清空，进行中的任务状态丢失。
- **无任务重试与死信**：内存字典无 TTL、无重试、无死信队列，任务失败仅记录状态，无自动恢复。

### 演进路径（Phase 6 计划）

`docker-compose.yml` 中**已预留 Redis 服务**，下一阶段（Phase 6）计划将任务队列迁移至 Redis：

1. **任务状态存储**：`job_store` 迁移到 Redis（Hash 结构），天然支持多实例共享与 TTL 过期。
2. **任务分发**：迁移到 `arq`（基于 Redis 的 asyncio 任务队列）或 `redis-stream`，获得任务重试、死信、优先级、并发控制等能力。
3. **接口预留**：当前 `job_store` 的读写已封装在 `_update_job` / `get_evaluation_job` 等函数/端点中，迁移时只需替换底层存储实现，API 契约不变。
4. **代码标记**：`routes.py` 中 `job_store` 定义处已加 `// TODO Phase 6: 迁移至 Redis 任务队列，见 docs/architecture-notes.md` 注释，便于后续定位。

### 当前阶段取舍

本轮（M3）**仅做文档说明 + 预留接口，不实际迁移**，原因：

- 迁移涉及 `routes.py`、`api/deps.py`、测试 fixture 的全面改造，会破坏现有 526 个测试，风险过高。
- MVP 单实例部署已能满足试点运行，Redis 迁移作为 Phase 6 的独立工作项推进更稳妥。

---

## 文件清单与引用

- 《EmpValue-AI-Project-Plan.md》第 4.4 节：Agent 工作流（含 FEEDBACK_COLLECT 节点描述）
- `backend/api/routes.py`：FEEDBACK_COLLECT 实际端点、`job_store` 定义
- `backend/agent/graph.py`：评估主流程图（不含 FEEDBACK_COLLECT 节点）
- `backend/eval/evaluate.py`：MockProvider、回归评估框架
- `docker-compose.yml`：Redis 服务预留
- `backend/tests/conftest.py`：内存 SQLite + DummyEmbedding 测试 fixture
