# Changelog

本文件记录 EmpValue-AI 所有显著变更,格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [v1.0.0] - 2026-07-02

MVP 首个正式版本:覆盖 Phase 1-5 + 补完轮 + Phase 6 关键项。

### Phase 1:项目骨架与基础设施

- 初始化 FastAPI + LangGraph + SQLAlchemy + Chroma 向量库后端骨架
- 初始化 Vue 3 + Vite + Element Plus + ECharts 前端
- 配置 docker-compose(backend / frontend / redis),支持一键本地起服务
- SQLite 异步数据库 + Alembic 迁移基线

### Phase 2:评估核心链路

- 实现 daily_evaluation Prompt(v0.1),三视图输出(员工/主管/审计)
- LangGraph 评估图:输入清洗 → 多模态提取 → LLM 评估 → 结构化解析 → 持久化
- 模型路由器(ModelRouter):按硬件档位 L0/L1/L2/L3 选择本地或云端模型
- 多模态输入清洗:附件类型白名单、超大输入拦截、Prompt 注入护栏
- 输入护栏(InputGuard):拦截恶意指令、Prompt 注入、超大附件
- 输出护栏(OutputGuard):PII 脱敏、偏见检测

### Phase 3:审批流与权限

- 评估状态机:ai_drafted → manager_review → hr_audit → approved/rejected
- 审批服务(ApprovalService):FOR UPDATE 悲观锁保证状态转换原子性
- RBAC 鉴权:employee / manager / hr / admin 四角色,字段级可见性控制
- JWT 认证 + 演示模式(仅开发/测试,生产强制关闭)
- 高风险评估自动路由至 HR 复核队列
- 员工申诉流:approved/rejected → manager_review

### Phase 4:可观测性与安全加固

- Langfuse 链路追踪集成(trace/span)
- Prometheus 指标端点(/metrics),6 项核心业务指标定义
- 审计日志(AuditService):所有写操作与敏感查看行为入审计
- 生产就绪检查脚本(check_prod_readiness.py)
- 公平性审计脚本(fairness_audit.py)

### Phase 5:回归评估与质量门禁

- LLM 输出回归评估框架(eval/evaluate.py):dataset + 规则校验 + LLM judge
- Prompt 版本对比门禁(--compare v0.1):检测 pass 回归与分数偏移
- 566 单元测试 + 16 E2E 测试,覆盖率 93%
- Locust 性能测试脚本

### 补完轮

- LangGraph 原生 interrupt human-in-the-loop 审批流(evaluations-interrupt 接口)
- 团队分析聚合接口
- 员工成长看板与跨周期能力演进
- 管理端审计日志分页查询
- 模型档位手动切换接口(含审计)

### Phase 6:MVP 关键项

#### 任务队列抽象 + Redis 化(解除单实例约束)

- 新增 `core/job_queue.py`:JobQueue 抽象基类 + InMemoryJobQueue + RedisJobQueue
- `create_job_queue` 工厂按 `settings.redis_url` 自动选择,Redis 不可达时降级内存,不崩
- `api/routes.py` 将模块级 `job_store` Dict 迁移至 `job_queue`,保持 API 行为完全一致
- `api/deps.py` AppState 注入 job_queue,与其他共享资源同生命周期管理
- `core/config.py` 新增 `redis_url` 配置项
- Redis key 前缀 `empvalue:job:`,JSON 序列化,所有操作 try/except 降级
- 新增 19 项 job_queue 单元测试(fakeredis 覆盖 Redis 路径,不依赖真实 Redis)

#### 可观测性埋点(Prometheus 指标接入业务)

- `services/approval_service.py` transition 落库后埋点 `record_approval_transition`
- `services/evaluation_service.py` create_evaluation 埋点 `record_evaluation` + `observe_evaluation_duration`
- `api/routes.py` feedback / appeal 端点埋点 `record_feedback`
- 所有埋点 try/except 包裹,埋点失败不影响业务主流程
- 新增 `grafana/dashboard.json`:4 panel(评估吞吐 / 耗时分布 / 审批流转 / LLM 调用),数据源 Prometheus

#### CI/CD 流水线

- 新增 `.github/workflows/ci.yml`:lint(ruff + black) / backend-test / frontend-build / prompt-gate 四 job
- pip 与 npm 依赖缓存,push 到 main 与 PR 触发
- prompt-gate 跑 `python -m eval.evaluate --mock --compare v0.1`,exit 0 才通过
- 新增 `.pre-commit-config.yaml`:ruff / black / eslint / prettier / end-of-file-fixer / trailing-whitespace,仅作用于暂存文件(渐进式接入,不强制重排历史代码)
- 新增 `backend/ruff.toml`:lenient 规则集,CI 绿色 + 新增代码受约束
