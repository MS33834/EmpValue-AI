# EmpValue-AI 前端

基于 Vue 3 + Vite + Element Plus + ECharts 的员工价值评估系统前端。

## 页面说明

| 路由 | 角色 | 功能 |
|---|---|---|
| `/login` | 全部 | 演示模式角色选择登录 |
| `/employee` | 员工 | 个人成长看板 + 能力雷达图 |
| `/employee/input` | 员工 | 录入日报/任务进度，触发 AI 评估 |
| `/manager` | 主管/HR | 团队价值排行榜、风险分布 |
| `/manager/approval/:id` | 主管/HR | 评估审批详情页 |

## 本地开发

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://localhost:5173`，并通过 Vite proxy 将 `/api` 转发到 `http://localhost:8000`。

## 生产构建

```bash
npm run build
```

构建产物位于 `frontend/dist/`。

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `VITE_API_BASE_URL` | 后端 API 基础路径 | `/api/v1` |
