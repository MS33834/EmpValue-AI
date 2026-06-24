# EmpValue-AI 开发计划书（完整版）

> **版本：** v1.0  
> **编写日期：** 2026-06-20  
> **协作团队：** 架构师、产品经理、程序员、安全合规、测试工程师  
> **适用范围：** 项目指导蓝图、简历项目仓库 README 参考

---

## 一、项目定位与愿景

### 1.1 定位

EmpValue-AI 是一套面向中大型企业的 AI 驱动员工价值量化与成长 Agent 系统。系统通过持续接收员工多维工作数据（日报、任务进度、代码贡献、会议记录、截图、语音等），利用大语言模型 Agent 进行自动化深度分析，输出：

- **员工视角：** 客观、建设性的成长反馈；
- **管理视角：** 尖锐、战略性的人才诊断与调配建议；
- **审计视角：** 可追溯、可解释的评估依据。

系统支持基于企业算力环境的弹性本地部署，并严格遵循“人机协同”的企业级审批流。

### 1.2 愿景

让每位员工获得客观、可执行的成长反馈；让管理者获得真实、带证据的人才决策支持；让企业以可审计、可解释的方式使用 AI 进行人才管理。

### 1.3 核心价值主张

1. **双视角输出分离：** 同一次推理同时生成建设性员工视图与尖锐管理视图。
2. **弹性双模部署：** 根据硬件自动选择本地小模型或云端大模型，平衡成本、性能与合规。
3. **人机协同决策：** AI 不直接产生人事决策，所有结果必须经过人工审批。

---

## 二、用户画像与核心场景

| 角色 | 核心诉求 | 使用频率 | 关键场景 |
|---|---|---|---|
| 普通员工 | 了解自身成长、获得具体改进建议 | 每周 | 查看周报反馈、能力雷达图 |
| 一线主管 | 识别团队风险、分配任务更合理 | 每周/每季 | 审批 AI 草稿、查看团队诊断 |
| HRBP | 确保评估公平、处理申诉 | 每月 | 复核异常评估、导出审计报告 |
| 高管/CTO | 识别高潜人才、组织效能 | 每季 | 查看团队 ROI 与人才分布 |
| 系统管理员 | 部署、配置、监控 | 持续 | 模型切换、权限管理、日志审计 |

### 2.1 用户故事（关键示例）

- **作为员工，** 我希望每周收到 AI 生成的成长反馈，了解具体优势和下周聚焦方向，而不是模糊的分数。
- **作为主管，** 我希望看到基于事实的团队成员风险诊断，帮助我决定是否调整任务分配。
- **作为 HR，** 我希望所有 AI 评估都有证据引用和审批记录，便于应对员工申诉。

---

## 三、成功指标（North Star Metrics）

| 维度 | 指标 | 目标 |
|---|---|---|
| 产品采用 | 员工周活跃率 | ≥ 70% |
| 输出质量 | 证据引用准确率（人工抽检） | ≥ 85% |
| 输出质量 | 结构化输出合规率 | ≥ 95% |
| 效率提升 | 主管评估耗时缩短 | ≥ 50% |
| 合规安全 | AI 直接决策占比为 0 | 100% 有人工确认 |
| 系统稳定 | API P99 延迟 | ≤ 3s |
| 成本可控 | 单次评估云端调用成本 | ≤ ¥0.5 |

---

## 四、系统架构设计

### 4.1 分层架构

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
│  PostgreSQL │ ChromaDB │ Redis │ 对象存储                           │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 各层职责

| 层级 | 核心职责 | 关键技术 |
|---|---|---|
| 前端交互层 | 员工录入、成长看板、主管审批、团队分析 | Vue 3、Element Plus、ECharts |
| API 网关层 | 身份认证、权限控制、限流、审计、路由 | FastAPI、JWT、RBAC |
| Agent 编排层 | 多节点工作流、状态机、工具调用、记忆检索 | LangGraph、LangChain |
| 模型抽象层 | 硬件探测、模型路由、自动降级、结果统一封装 | 自定义 ModelRouter |
| 数据与记忆层 | 持久化、向量记忆、缓存、对象存储 | PostgreSQL、ChromaDB、Redis |

### 4.3 ModelRouter 档位设计

> **团队确认项：** 原方案中“Qwen3.5”系列尚未发布，已替换为当前可获取模型。

| 档位 | 模型示例 | 显存/内存要求 | 适用场景 | 输出能力 |
|---|---|---|---|---|
| L0-云端 | GPT-4o / Claude 3.5 / DeepSeek-V3 | 无本地要求 | 全模态深度分析、复杂推理 | 完整双视角 + 深度诊断 |
| L1-边缘 | Qwen2.5-0.5B / Qwen2.5-1.5B | ≤ 4GB | 纯文本摘要、简单规则打分 | 员工视图摘要 + 基础维度分 |
| L2-标准 | Qwen2.5-7B / DeepSeek-R1-7B | 8-16GB | 文本+表格分析、常规评估 | 完整员工视图 + 管理视图 |
| L3-本地旗舰 | Qwen2.5-14B / Llama 3.1-8B | ≥ 16GB | 全模态深度推理、画像生成 | 全功能 |

**降级策略：**

- 启动时探测硬件（CPU/GPU/内存），自动推荐默认档位；
- 运行时若显存不足或调用失败，自动降一档；
- 云端不可用时回退到 L3 或 L2；
- 管理员可手动锁定档位。

### 4.4 Agent 工作流（LangGraph）

```
[RAW_DATA]
   ↓
[DATA_CLEANING]          ← 多模态解析（OCR / ASR / 表格抽取）
   ↓
[CONTEXT_RETRIEVAL]      ← 调用 get_employee_history, query_company_kb
   ↓
[AI_PROCESSING]          ← 模型推理生成三视图
   ↓
[AI_DRAFTED]             ← 中断点：等待主管初审
   ↓
[MANAGER_REVIEW]         ← 可打回、可编辑、可驳回
   ↓
[HR_AUDIT]               ← 异常评估自动进入 HR 复核
   ↓
[APPROVED]               ← 正式发布，员工可见部分分发
   ↓
[FEEDBACK_COLLECT]       ← 收集员工反馈与申诉
```

**中断规则：**

1. 员工视图与管理视图必须在同一节点生成，保证逻辑一致性；
2. 主管初审为强制节点，不可跳过；
3. 当 `overall_score < 阈值` 或检测到高风险标记时，自动进入 HR 复核；
4. 员工申诉可触发重新评估流程。

---

## 五、核心数据结构设计

### 5.1 评估输出 Schema

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal
from datetime import datetime


class DimensionScore(BaseModel):
    """维度得分，强制引用原始证据"""
    dimension: str = Field(..., description="评估维度，如执行力、协作、创新")
    score: float = Field(..., ge=0, le=100, description="0-100 分")
    evidence: List[str] = Field(
        ...,
        min_length=1,
        description="引用原始数据片段，必须可追溯到具体输入"
    )
    improvement_actions: List[str] = Field(
        ...,
        min_length=1,
        description="具体可执行改进建议"
    )


class EmployeeView(BaseModel):
    """员工可见的建设性视图"""
    summary: str = Field(..., description="客观总结，无主观负面措辞")
    strengths: List[str] = Field(..., min_length=1)
    growth_areas: List[DimensionScore]
    next_week_focus: List[str] = Field(..., min_length=1, max_length=5)


class RiskFlag(BaseModel):
    """管理视图中的风险标记"""
    level: Literal["low", "medium", "high", "critical"]
    category: str
    description: str
    suggested_action: str


class ManagerView(BaseModel):
    """管理/HR 可见的尖锐诊断视图"""
    harsh_assessment: str = Field(..., description="尖锐但基于事实的诊断")
    risk_flags: List[RiskFlag]
    roi_analysis: str
    reallocation_suggestion: str
    hidden_issues: List[str] = Field(
        ...,
        description="员工不可见的判断，仅限管理/HR查看"
    )


class AuditInfo(BaseModel):
    """审计信息，保证可解释性"""
    model_name: str
    model_tier: Literal["L0", "L1", "L2", "L3"]
    confidence_score: float = Field(..., ge=0, le=1)
    raw_data_refs: List[str]
    triggered_rules: List[str]
    processing_time_ms: int
    prompt_version: str


class EmployeeEvaluation(BaseModel):
    """一次完整的员工评估"""
    evaluation_id: str
    employee_id: str
    period: str
    overall_score: float = Field(..., ge=0, le=100)
    employee_view: EmployeeView
    manager_view: ManagerView
    audit: AuditInfo
    status: Literal[
        "draft",
        "manager_review",
        "hr_audit",
        "approved",
        "rejected"
    ]
    created_at: datetime
    approved_at: datetime | None
    approver_id: str | None
```

### 5.2 数据库核心表

| 表名 | 作用 |
|---|---|
| `users` | 员工/主管/HR 基础信息、角色、部门 |
| `evaluation_periods` | 评估周期定义（周/月/季/年） |
| `raw_inputs` | 日报、截图、语音、代码提交等原始输入 |
| `evaluations` | 评估结果主表 |
| `dimension_scores` | 维度得分明细 |
| `evidence_refs` | 证据与原始输入关联 |
| `approval_flows` | 审批状态机记录 |
| `memories` | 员工长期记忆向量 |
| `feedback` | 员工申诉与反馈 |
| `audit_logs` | 全量操作审计日志 |
| `company_kb` | 公司评分标准、培训材料、价值观等 |

---

## 六、API 接口设计

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/inputs` | 提交日报/截图/语音 |
| GET | `/api/v1/inputs/{id}` | 查询原始输入 |
| POST | `/api/v1/evaluations` | 触发评估（异步） |
| GET | `/api/v1/evaluations/{id}` | 查询评估结果（按角色过滤） |
| GET | `/api/v1/evaluations/{id}/employee-view` | 员工可见视图 |
| GET | `/api/v1/evaluations/{id}/manager-view` | 管理视图（RBAC） |
| POST | `/api/v1/evaluations/{id}/approve` | 主管审批通过 |
| POST | `/api/v1/evaluations/{id}/reject` | 打回重审 |
| POST | `/api/v1/evaluations/{id}/feedback` | 员工反馈/申诉 |
| GET | `/api/v1/employees/{id}/dashboard` | 个人成长看板 |
| GET | `/api/v1/employees/{id}/history` | 跨周期能力演进 |
| GET | `/api/v1/teams/{id}/analytics` | 团队分析（管理端） |
| GET | `/api/v1/admin/model-status` | 模型状态与当前档位 |
| POST | `/api/v1/admin/model-switch` | 手动切换模型档位 |

---

## 七、核心功能模块

### 7.1 弹性双模部署

- **保密模式（本地）：** 通过 LM Studio / Ollama 运行量化小模型，全程数据不出内网。
- **高效模式（云端）：** 对接外部顶尖 API，获得最强推理能力。
- **自动降级：** 系统根据设备内存/显存、网络状态、模型可用性自动选择档位。

### 7.2 双视角输出分离

一次 Agent 推理生成三套视图：

- **员工视图：** 客观总结、具体优势、成长建议、下周聚焦方向。全程无主观负面措辞。
- **管理视图：** 尖锐价值诊断、风险红旗、ROI 分析、人事调配建议、隐藏问题。
- **审计视图：** AI 置信度、引用的原始数据片段、触发的规则、使用的模型。

### 7.3 Agent 能力

- **工具调用：** Agent 自主调用 `get_employee_history`、`query_company_kb` 获取上下文。
- **长期记忆：** 基于 ChromaDB，实现员工跨周期能力演进追踪。
- **人机协同状态机：** RAW_DATA → AI_PROCESSING → AI_DRAFTED → MANAGER_REVIEW → HR_AUDIT → APPROVED。

### 7.4 反馈与申诉

- 员工可对评估结果提出反馈；
- 主管和 HR 可查看申诉并决定是否重新评估；
- 申诉记录进入审计日志。

---

## 八、技术栈选型

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3 + JavaScript + Element Plus + ECharts |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy |
| Agent 编排 | LangGraph |
| AI 运行环境 | LM Studio / Ollama（本地）、OpenAI / Anthropic / 阿里云百炼 / DeepSeek API（云端） |
| 本地大模型 | Qwen2.5 系列 / DeepSeek-R1-Distill / Llama 3.1 |
| 关系型数据库 | SQLite（默认）/ PostgreSQL 15+（生产） |
| 向量数据库 | ChromaDB |
| 缓存/任务队列 | Redis（预留，当前使用 FastAPI BackgroundTasks） |
| 可观测性 | Langfuse（Prometheus/Grafana 规划中） |
| 测试 | pytest + locust |
| 部署 | Docker Compose |

---

## 九、开发阶段与里程碑

### Phase 1：Prompt 与 Schema 联调（2-3 周）

- [ ] 完成 Pydantic Schema 与校验规则
- [ ] 在 LM Studio 部署 Qwen2.5-7B 作为基准模型
- [ ] 编写 System Prompt，重点调试双视角语气分离
- [ ] 建立 50 条人工标注测试集，评估证据引用准确率
- [ ] 输出：《Prompt 工程规范 v1.0》

### Phase 2：后端与 Agent 核心搭建（4-5 周）

- [ ] 实现 ModelRouter 与 Provider 抽象层
- [ ] 用 LangGraph 搭建带中断点的审批状态机
- [ ] 定义并实现 Agent 的 Tools 接口
- [ ] 接入 ChromaDB 长期记忆
- [ ] 完成 RBAC、审批流、审计日志
- [ ] API 单元测试覆盖率 ≥ 70%

### Phase 3：前端工程与数据闭环（3-4 周）

- [ ] Vue3 搭建员工端、主管端、HR 端页面
- [ ] 对接 FastAPI，跑通“录入 → AI 清洗 → 审批 → 入库”全流程
- [ ] UI/UX 走查与可访问性检查
- [ ] 前端端到端测试覆盖核心流程

### Phase 4：模拟数据、护栏与可观测性（2-3 周）

- [ ] 生成 5 类典型员工画像 Mock 数据（劳模、摸鱼、明星、新人、瓶颈期）
- [ ] 加入输入 Prompt 注入防护与输出 PII 脱敏
- [ ] 集成 Langfuse 追踪 Agent 执行轨迹
- [ ] 红队测试：Prompt 注入、越狱、偏见、幻觉

### Phase 5：试点部署与迭代（持续）

- [ ] 选择 1-2 个团队进行内部试点
- [ ] 收集主管与员工反馈
- [ ] 建立反馈闭环，持续优化 Prompt
- [ ] 输出：《企业部署手册》《安全合规白皮书》

---

## 十、测试策略

| 测试类型 | 工具/方法 | 关注点 |
|---|---|---|
| 单元测试 | pytest | 服务层、Schema 校验、工具函数 |
| 集成测试 | pytest + TestContainers | API 接口、数据库、向量库交互 |
| 端到端测试 | Playwright | 核心用户流程 |
| LLM 评估 | LLM-as-a-Judge + 人工抽检 | 证据引用、语气分离、幻觉率 |
| 红队测试 | 手动 + 自动化 | Prompt 注入、越狱、偏见 |
| 性能测试 | locust | 并发评估、模型降级 |
| 安全测试 | 依赖扫描 + 代码审计 | 漏洞、PII 泄露 |

---

## 十一、安全、合规与护栏

### 11.1 数据安全

- **数据分类：** 原始输入与评估结果均为“高敏感”数据。
- **加密：** 传输 TLS 1.3，静态数据 AES-256。
- **租户隔离：** 向量库与数据库按企业/租户隔离。
- **本地模式：** 数据不出内网，模型运行在 LM Studio。

### 11.2 内容安全

- **输入护栏：** 防 Prompt 注入、恶意文件、超大输入、非工作相关内容过滤。
- **输出护栏：** PII 脱敏、歧视性表述检测、极端负面措辞拦截。
- **幻觉控制：** 强制 evidence 引用，无证据不得出结论。

### 11.3 法律合规

- **人机协同声明：** 所有 AI 输出标注“AI 生成，仅供参考，最终决策由人作出”。
- **员工知情权：** 评估前告知员工数据用途、查看权限、申诉渠道。
- **公平性审计：** 定期抽样检查不同性别/年龄/职级群体的评分偏差。
- **数据留存：** 原始输入保留 2 年，评估结果保留 5 年，删除需审批。

### 11.4 管理视图特殊控制

- 管理视图仅限主管、HR、高管查看；
- 所有查看行为计入审计日志；
- 关键页面增加水印，防止截图泄露。

---

## 十二、资源与成本估算

| 项目 | 本地部署（50人团队） | 云端混合（500人团队） |
|---|---|---|
| 推理节点 | 1× RTX 4090 / 64GB RAM | 4× A10 / Kubernetes |
| 应用服务器 | 1× 16C32G | 3× 16C32G |
| 数据库/向量库 | 1× 8C16G | 托管 PostgreSQL + Milvus |
| 云端 API 成本 | ¥0 | 约 ¥2,000-5,000/月 |
| 开发人力 | 1 架构 + 2 后端 + 1 前端 + 1 测试 | 翻倍 |
| 开发周期 | 10-12 周 MVP | 16-20 周 |

---

## 十三、风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 模型幻觉导致评估不公 | 高 | 强制 evidence 引用 + 人工审批 + 申诉机制 |
| 员工抵触、信任危机 | 高 | 透明沟通、员工视图建设性、管理视图受限 |
| 本地硬件性能不足 | 中 | 自动降级到云端或更小模型 |
| 法律法规变化 | 中 | 法律顾问介入、保留人工最终决策权 |
| 数据泄露 | 高 | 加密、租户隔离、本地模式、最小权限 |
| 集成复杂度高 | 中 | 先支持文件上传，再逐步集成 IM/代码仓库 |
| 多模态识别错误 | 中 | OCR/ASR 结果人工复核开关、置信度标注 |

---

## 十四、团队协作与职责

| 角色 | 负责人 | 核心职责 |
|---|---|---|
| 产品经理 | 待定 | 需求定义、用户故事、 success metrics、试点推进 |
| 架构师 | 待定 | 系统架构、ModelRouter、技术选型、性能设计 |
| 后端工程师 | 待定 | FastAPI、LangGraph Agent、数据库、API 实现 |
| 前端工程师 | 待定 | Vue3 三端页面、数据可视化、交互设计 |
| 安全合规 | 待定 | 护栏设计、合规审查、审计策略、法律声明 |
| 测试工程师 | 待定 | 测试策略、LLM 评估、自动化测试、红队测试 |
| Prompt 工程师 | 待定 | System Prompt、Schema 联调、输出质量优化 |

**协作机制：**

- 每周五 16:00 项目周会，同步进度与阻塞；
- 所有技术决策以 ADR（Architecture Decision Record）记录；
- Prompt 版本使用 Git 管理，每次变更需经过 LLM 评估集回归；
- 安全合规从 Phase 1 开始介入，不后置。

---

## 十五、简历亮点（可直接参考）

- **架构设计：** 设计支持云端 API 与本地 LM Studio 双模切换的弹性架构，基于 ModelRouter 实现硬件探测与多档模型动态路由，满足企业数据保密与边缘计算需求。
- **智能体工程：** 基于 LangGraph 构建带 Human-in-the-loop 中断机制的多节点 Agent 工作流，集成 Function Calling 与向量长期记忆，实现员工跨周期能力演进追踪。
- **AI 产品思维：** 创新设计双视角输出 Schema，通过 Pydantic 强制约束模型同步生成建设性员工视图与尖锐管理视图，实现评估结果的精准权限分发。
- **企业级合规：** 建立输入/输出护栏、审计日志、公平性抽检与申诉机制，确保 AI 不直接产生人事决策，满足企业合规与信任要求。

---

## 十六、下一步行动

1. **Phase 1 启动：** Prompt 工程师产出《员工日报评估 System Prompt v0.1》。
2. **模型选型确认：** 团队共同确定本地基线模型（建议 Qwen2.5-7B-Instruct）与云端备选 API。
3. **合规前置：** 安全合规与 HR、法务共同制定《AI 评估知情同意书》与《人工最终决策声明》。
4. **原型验证：** 用 10 条真实（脱敏）日报跑通 Schema 输出，验证证据引用与双视角分离效果。
5. **技术预研：** 确认 ASR 方案（Whisper / 阿里云 / 科大讯飞）与 OCR 方案（PaddleOCR / 阿里云）。

---

**附录：**

- 附录 A：待产出的文档清单
- 附录 B：LLM 评估集规范
- 附录 C：ADR 模板
- 附录 D：安全合规检查清单

> 本文档为团队协作产物，后续版本更新需由产品经理牵头，各角色评审后合并。
