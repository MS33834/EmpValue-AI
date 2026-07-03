# EmpValue-AI 项目路线图与演进计划

> **版本:** v2.0
> **编写日期:** 2026-07-02
> **维护方式:** 每完成一项将 `[ ]` 改为 `[x]`,每次更新同步推送仓库,确保进度实时可见
> **适用范围:** Phase 1-5 已交付成果总结 + Phase 6+ 演进规划

---

## 一、项目定位

EmpValue-AI 是面向中大型企业的 AI 驱动员工价值量化与成长 Agent 系统。通过持续接收员工多维工作数据(日报、任务进度、代码贡献、会议记录、截图、语音),利用大语言模型 Agent 自动化深度分析,输出员工视角(建设性成长反馈)、管理视角(尖锐人才诊断)、审计视角(可追溯可解释依据)三套视图,严格遵循"人机协同"企业级审批流。

核心价值:双视角输出分离、弹性双模部署(本地/云端)、人机协同决策(AI 不直接产生人事决策)。

---

## 二、Phase 1-5 已交付成果(特色概括)

> Phase 1-5 已全部完成并通过专家团队回溯审计：566 单测 + 16 E2E 全绿，覆盖率 93%，前端构建成功。各阶段交付如下。

### Phase 1:Prompt 与 Schema 联调（已完成）

- **Pydantic v2 Schema 强约束**:`EmployeeEvaluation` 强制 evidence 引用(min_length=1 + ≥10 字符)、overall_score 0-100、双视角分离字段
- **System Prompt 双视角语气分离**:员工视图建设性 + 管理视图尖锐诊断,同一节点生成保证逻辑一致
- **50 条人工标注测试集**:`eval/dataset.json` 覆盖 5 类员工画像
- **Prompt 工程规范 v1.0**:[docs/prompt-engineering-spec-v1.md](docs/prompt-engineering-spec-v1.md)

### Phase 2:后端与 Agent 核心（已完成）

- **LangGraph 双图工厂**:`create_evaluation_graph`(DB 状态机)+ `create_evaluation_graph_with_interrupt`(原生 interrupt 审批流)
- **完整节点链**:input_sanitizer → data_cleaning → retrieve_context → build_prompt → call_llm → parse_output → manager_review_gate → manager_review / hr_audit → finalize
- **ModelRouter 四档位**:L0 云端 / L1 边缘 / L2 标准 / L3 本地旗舰,硬件探测(psutil + torch + nvidia-smi)+ 自动降级
- **Provider 抽象**:BaseProvider + OpenAICompatibleProvider,MAX_RETRIES=3 指数退避
- **RBAC + 审批状态机**:VALID_TRANSITIONS 严格枚举 + 悲观锁 + appeal 回退,非法转换 400 拦截
- **ChromaDB 长期记忆**:跨周期能力演进追踪,DummyEmbeddingFunction 降级(无 API Key 时)
- **35 个 API 端点**:inputs CRUD、异步评估 job、evaluations CRUD、approve/reject/feedback/appeal/re-evaluate、manager/hr 队列、admin 模型管理、LangGraph interrupt 流
- **Alembic 迁移**:11 张表 + 索引 + 约束完整

### Phase 3:前端工程与数据闭环（已完成）

- **12 个 Vue3 视图**:员工(4:Dashboard/Input/History/Feedback)+ 主管(3:Dashboard/ApprovalDetail/TeamAnalytics)+ HR(2:Dashboard/AuditDetail)+ 管理员(2:Model/AuditLogs)+ Login
- **WCAG 2.1 AA 可访问性**:图表 role="img" + 文字摘要、aria-live 动态通告、aria-busy、对比度 ≥4.5:1、键盘可达
- **Element Plus 主题色统一**:#2563eb(WCAG AA 达标),CSS 变量全局覆盖
- **Vite manualChunks 拆分**:vue-core / element-plus / echarts 三 vendor chunk 分离,业务主包仅 56KB
- **水印防截图组件**:manager/hr/admin 视图显示,canvas 生成含用户标识 + 时间的纹理,aria-hidden 不破坏可访问性
- **E2E 16 测试**:Health/Auth/EmployeeFlow/EvaluationFlow/InterruptFlow/RBAC/HrAuditFlow/AppealFlow/FeedbackFlow/GuardrailFlow

### Phase 4:模拟数据、护栏与可观测性（已完成）

- **5 类员工画像 Mock 数据**:劳模/摸鱼/明星/新人/瓶颈期,`scripts/run_mock_evaluations.py` 跑通 LangGraph
- **输入护栏 6 函数**:Prompt 注入(中/英)+ 编码绕过 + 零宽字符(NFKC + BYPASS_CHARS)+ base64/hex/url 解码 + 附件白名单
- **输出护栏 6 函数**:PII 脱敏(手机/邮箱/身份证)+ 偏见检测(7 维度)+ 幻觉标记 + 员工视图负面词过滤
- **多模态抽取 6 类**:Text/Table/Image/Audio/Pdf/Unknown,路径遍历防护
- **Langfuse 可观测**:LangfuseTracer + NoOp 降级
- **Prometheus 指标**:6 业务指标(评估计数/耗时/审批流转/反馈/LLM 调用/活跃任务)+ `/metrics` 端点
- **红队测试 50 用例 8 大类**:PromptInjection/Jailbreak/Bypass/Boundary/Bias/PII/Hallucination/Attachment + SchemaStability 50 次参数化

### Phase 5:试点部署与迭代（已完成）

- **试点 Runbook**:[docs/pilot-runbook.md](docs/pilot-runbook.md) 含 Go/No-Go 就绪清单、4 周执行节奏、反馈闭环、Prompt 门禁、回滚预案、退出标准
- **反馈闭环工程化**:appeal 端点写 type=appeal 的 Feedback 记录,`/employees/{id}/feedback` 端点追踪申诉处理进度,前端反馈面板带状态映射
- **Prompt 版本回归门禁**:`evaluate.py --compare v0.1`,VersionedPromptLoader + compare_versions,exit code 供 CI
- **LLM-as-Judge 评估框架**:[backend/eval/llm_judge.py](backend/eval/llm_judge.py) 证据/语气/幻觉三维度 + MockJudge 启发式 + CLI
- **公平性审计自动化**:[backend/scripts/fairness_audit.py](backend/scripts/fairness_audit.py) 群体评分偏差 + 阈值告警 + CLI
- **生产守护**:`core/config.py` validator(EMPVALUE_ENV=production 禁止 demo_mode)+ [check_prod_readiness.py](backend/scripts/check_prod_readiness.py) 检查 demo/JWT/DB/TLS
- **企业部署手册**:[docs/deployment-guide.md](docs/deployment-guide.md) 含 docker-compose.prod.yml(PG/MinIO/GPU)
- **安全合规白皮书**:[docs/security-compliance-whitepaper.md](docs/security-compliance-whitepaper.md) 13 项合规清单

### 补完轮（回溯审计后，已完成）

- **数据集生成脚本**:[scripts/generate_dataset.py](backend/scripts/generate_dataset.py) 5 类画像批量生成,CLI + 可 import
- **Prompt v0.2 版本快照**:[prompts/versions/daily_evaluation_v0.2.md](backend/prompts/versions/daily_evaluation_v0.2.md),--compare 门禁演练通过
- **HR 复核详情页**:[HRAuditDetail.vue](frontend/src/views/hr/HRAuditDetail.vue) 补齐第 12 视图,完整 HR 复核闭环
- **架构实现说明**:[docs/architecture-notes.md](docs/architecture-notes.md) FEEDBACK_COLLECT 节点 API 化、TestContainers 取舍、任务队列演进
- **生产 Compose override**:[docker-compose.prod.yml](docker-compose.prod.yml) PostgreSQL + MinIO + GPU

### 质量基线(实测)

| 指标 | 数值 |
|---|---|
| 单元/集成测试 | 566 passed |
| 端到端测试 | 16 passed |
| 红队测试 | 50 passed |
| 代码覆盖率 | 93% |
| 后端代码 | 7,259 行 Python |
| 测试代码 | 7,162 行 Python(测试/业务 ≈ 0.99:1) |
| 前端代码 | 2,900+ 行 Vue/JS |
| API 端点 | 35 个 |
| 文档 | 6 份(deployment-guide/pilot-runbook/prompt-spec/security-whitepaper/architecture-notes + 本路线图) |

---

## 三、Phase 6+ 演进计划

> 以下为从当前阶段开始的后续步骤,结合前面成果扩展完善。每完成一项勾选,每次更新同步推送仓库。

### Phase 6:生产化与横向扩展(进行中)

#### 6.1 任务队列 Redis 化(解除单实例约束)

- [x] 实现 `core/job_queue.py` 抽象层,兼容内存(测试)与 Redis(生产)双后端 (完成日期: 2026-07-02)
- [x] 将 `api/routes.py` 的 `job_store: Dict` 迁移至 JobQueue,保持 API 不变 (完成日期: 2026-07-02)
- [x] 补 `tests/test_job_queue.py` 覆盖入队/出队/更新/删除/工厂选择 (完成日期: 2026-07-02)
- [x] docker-compose.prod.yml 启用 redis,docker-compose 已预留 redis 服务 (完成日期: 2026-07-02)
- [ ] 输出任务队列 ADR(arq vs redis-stream 选型,当前用裸 redis.asyncio 实现)

#### 6.2 真实 Embedding 接入与检索质量验证

> 需真实 API Key,沙箱无法跑通,留待 Phase 7 真实模型联调阶段一并验证。

- [ ] 接入真实 Embedding 服务(OpenAI text-embedding-3-small / 阿里云 / 本地 BGE)
- [ ] 用 `eval/llm_judge.py` 跑一轮真实检索质量基线,记录 evidence 可溯源性分数
- [ ] 对比 DummyEmbedding 与真实 Embedding 的检索召回率,写入 architecture-notes.md
- [ ] 补 README 生产 Embedding 配置示例,移除 Dummy 演示警告中的"不可用"措辞

#### 6.3 可观测性闭环(Prometheus + Grafana)

- [x] 在 approval_service / evaluation_service / feedback 端点埋点调用 `core/metrics.py` 便捷函数 (完成日期: 2026-07-02)
- [x] 编写 Grafana Dashboard JSON(评估吞吐/耗时分布/审批流转/LLM 调用/活跃任务) (完成日期: 2026-07-02)
- [ ] docker-compose.prod.yml 增加 grafana 服务,预置 Dashboard + Prometheus 数据源
- [ ] 文档补充告警规则(评估失败率 >5%、P99 >3s、LLM 调用失败率 >10%)

#### 6.4 CI/CD 流水线

- [x] 配置 GitHub Actions:lint(ruff)+ 单测 + 前端构建 + --compare Prompt 门禁 (完成日期: 2026-07-02)
- [x] 加 pre-commit hook(ruff/black/eslint/prettier,渐进式仅检查暂存文件) (完成日期: 2026-07-02)
- [x] 生成 CHANGELOG.md(Keep a Changelog 格式,v1.0.0 记录 Phase 1-6) (完成日期: 2026-07-02)
- [ ] 发布 v1.0.0 tag(待 CI 首次绿后打)
- [ ] 配置 GitCode CI(或镜像 GitHub Actions)

### Phase 7:真实模型联调与质量基线

#### 7.1 真实 LLM 联调

- [ ] 接入至少 2 个云端模型(DeepSeek-V3 / Qwen-Max)跑 50 条 dataset
- [ ] 接入 1 个本地模型(Qwen2.5-7B via LM Studio)跑 50 条 dataset
- [ ] 记录各档位 L0/L2/L3 的输出质量(证据准确率/语气分离/幻觉率)
- [ ] 输出《模型选型与档位推荐报告》

#### 7.2 LLM-as-Judge 真实评估

- [ ] 用真实 LLM 替换 MockJudge 跑 `eval/llm_judge.py`,记录三维分数
- [ ] 与人工抽检(20 条)对比,校准 Judge 评分一致性
- [ ] 设定质量门禁:evidence 分 ≥85 才允许发布 Prompt 版本

#### 7.3 Prompt 迭代至 v0.3

- [ ] 基于真实模型反馈优化 Prompt(如强化证据引用约束、改善语气分离)
- [ ] 归档 `daily_evaluation_v0.3.md`,跑 `--compare v0.2` 门禁
- [ ] 记录 v0.1 → v0.2 → v0.3 质量演进曲线

### Phase 8:多模态与集成扩展

#### 8.1 真实多模态接入

- [ ] 接入 OCR(PaddleOCR / 阿里云)处理截图工作证据
- [ ] 接入 ASR(Whisper / 阿里云)处理语音日报
- [ ] 补 `tests/test_multimodal.py` 真实文件用例(图片/音频/PDF)
- [ ] 文档补多模态置信度阈值与人工复核开关

#### 8.2 IM / 代码仓库集成

- [ ] 调研飞书/钉钉机器人接入(日报自动采集)
- [ ] 调研 GitLab/GitHub 代码贡献采集(commit/PR/Code Review)
- [ ] 输出集成 ADR,选定首期集成对象

#### 8.3 对象存储落地

- [ ] 后端集成 S3 兼容客户端(boto3 / minio-py)
- [ ] 附件上传改走 MinIO,`ATTACHMENT_DIR` 切换至 S3 endpoint
- [ ] 补 `tests/test_attachment_storage.py` 覆盖上传/下载/删除/签名 URL

### Phase 9:试点运行与持续迭代

#### 9.1 内部试点启动

- [ ] 按 [pilot-runbook.md](docs/pilot-runbook.md) Go/No-Go 清单完成就绪检查
- [ ] 选定 1-2 个试点团队(建议 20-50 人),完成数据导入与账号开通
- [ ] 试点首周每日巡检:评估质量抽检 + 系统稳定性监控 + 用户反馈收集
- [ ] 输出《试点周报》模板,记录指标(周活跃率/证据准确率/申诉数/通过率)

#### 9.2 反馈闭环持续优化

- [ ] 试点 4 周后输出《试点总结报告》:达成退出标准 / 遗留问题 / 推广建议
- [ ] 基于试点反馈迭代 Prompt 至 v1.0(正式版)
- [ ] 公平性审计月度运行,记录群体评分偏差趋势
- [ ] 申诉处理 SLA 监控(72 小时内响应率)

#### 9.3 推广与规模化

- [ ] 试点通过后扩展至 3-5 个团队
- [ ] 输出《规模化部署 Runbook》(多团队数据隔离/权限矩阵/培训材料)
- [ ] 建立内部 Prompt 工程师认证流程(Prompt 变更需通过 --compare 门禁 + 人工评审)

### Phase 10:企业级增强(长期)

#### 10.1 多租户与权限矩阵

- [ ] 数据库表加 tenant_id,实现租户隔离
- [ ] RBAC 细化至数据级(员工只能看自己,主管只能看本团队)
- [ ] 向量库按 tenant 分 collection

#### 10.2 高级分析

- [ ] 团队 ROI 分析仪表盘(季度趋势/人才九宫格/风险预警)
- [ ] 员工成长路径推荐(基于历史评估 + 能力雷达)
- [ ] 离职风险预测模型(集成管理视图 risk_flags 历史)

#### 10.3 合规与审计增强

- [ ] 数据留存策略自动化(原始输入 2 年/评估 5 年,到期归档)
- [ ] 水印防截图增强(动态水印 + 截图检测 SDK 调研)
- [ ] GDPR / 个保法合规审计脚本(数据主体权利:查询/导出/删除)
- [ ] 年度第三方安全审计对接

---

## 四、进度追踪规则

1. **勾选规则**:每完成一项,将 `[ ]` 改为 `[x]`,并在项后补 `(完成日期: YYYY-MM-DD,提交: <commit-hash>)`
2. **同步规则**:每次勾选变更必须 commit 并推送 GitHub + GitCode 两个仓库
3. **验证规则**:勾选前必须跑通相关测试,确保"能运行、能跑通、测试无误"
4. **新增规则**:演进中发现新需求,在对应 Phase 末尾追加 `- [ ]` 项,记录于提交信息

---

## 五、技术债与已知限制

> 以下为当前架构的已知限制,非阻塞但需在规模化前处理。

| 项 | 现状 | 影响 | 计划 |
|---|---|---|---|
| job_store 内存态 | 单实例约束 | 多副本不可用 | Phase 6.1 |
| DummyEmbedding | 无 API Key 时伪向量 | 检索无语义意义 | Phase 6.2 |
| Redis 未消费 | docker-compose 预留未用 | 资源浪费 | Phase 6.1 |
| TestContainers 未引入 | 内存 SQLite 替代 | 隔离性弱 | 不引入(架构说明已记录) |
| FEEDBACK_COLLECT 节点 | API 层替代 | 架构与原计划不同 | 文档已说明(architecture-notes.md) |
| 前端 element-plus chunk 1.07MB | 全量引入 | 首屏加载 | 按需引入(Phase 10 评估) |

---

## 六、文档索引

| 文档 | 路径 | 说明 |
|---|---|---|
| 项目路线图(本文档) | PROJECT-ROADMAP.md | Phase 1-5 总结 + Phase 6+ 计划 |
| 企业部署手册 | [docs/deployment-guide.md](docs/deployment-guide.md) | 部署模式/Compose/生产增强/运维 |
| 试点 Runbook | [docs/pilot-runbook.md](docs/pilot-runbook.md) | Go/No-Go/执行节奏/反馈闭环 |
| Prompt 工程规范 | [docs/prompt-engineering-spec-v1.md](docs/prompt-engineering-spec-v1.md) | System Prompt 设计与版本管理 |
| 安全合规白皮书 | [docs/security-compliance-whitepaper.md](docs/security-compliance-whitepaper.md) | 护栏/合规/审计/法律 |
| 架构实现说明 | [docs/architecture-notes.md](docs/architecture-notes.md) | 节点 API 化/TestContainers/任务队列演进 |

---

> 活文档，随项目演进持续更新；每次更新同步推送两个仓库。
