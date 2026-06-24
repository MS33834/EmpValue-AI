"""
EmpValue-AI 性能测试（Locust）

运行方式：
    locust -f tests/perf/locustfile.py --host http://localhost:8000

测试场景：
    1. 员工提交日报输入
    2. 触发异步评估
    3. 轮询评估任务状态
    4. 查询评估详情
    5. 登录获取 JWT token
"""

import json
import random
import uuid

from locust import HttpUser, between, task


class EmpValueUser(HttpUser):
    """模拟员工/主管用户行为"""

    wait_time = between(1, 3)
    weight = 1

    def on_start(self):
        """登录获取 token（JWT 模式）"""
        # 尝试 JWT 登录
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "employee@empvalue.ai", "password": "empvalue123"},
            name="/auth/login",
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("access_token")
            self.role = data.get("role", "employee")
            self.user_id = data.get("user_id", "E1001")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # 降级到演示模式
            self.token = None
            self.role = random.choice(["employee", "manager", "hr", "admin"])
            self.user_id = f"U{random.randint(1000, 9999)}"
            self.headers = {
                "x-user-role": self.role,
                "x-user-id": self.user_id,
            }

    @task(3)
    def submit_input(self):
        """提交日报输入"""
        payload = {
            "employee_id": self.user_id,
            "period": "2026-W26",
            "type": "daily_report",
            "content": f"性能测试日报 {uuid.uuid4().hex[:8]}：完成了模块开发与测试",
        }
        self.client.post(
            "/api/v1/inputs",
            json=payload,
            headers=self.headers,
            name="/inputs",
        )

    @task(2)
    def trigger_evaluation(self):
        """触发异步评估"""
        payload = {
            "employee_id": self.user_id,
            "period": "2026-W26",
            "raw_inputs": [
                {
                    "input_id": f"perf-{uuid.uuid4().hex[:8]}",
                    "content": "性能测试：完成需求开发，修复 2 个 Bug",
                }
            ],
        }
        resp = self.client.post(
            "/api/v1/evaluations",
            json=payload,
            headers=self.headers,
            name="/evaluations",
        )
        if resp.status_code == 200:
            job_id = resp.json().get("job_id")
            if job_id:
                # 轮询一次任务状态
                self.client.get(
                    f"/api/v1/evaluations/jobs/{job_id}",
                    headers=self.headers,
                    name="/evaluations/jobs/[job_id]",
                )

    @task(1)
    def get_dashboard(self):
        """查询员工仪表盘"""
        self.client.get(
            f"/api/v1/employees/{self.user_id}/dashboard",
            headers=self.headers,
            name="/employees/[id]/dashboard",
        )

    @task(1)
    def health_check(self):
        """健康检查（无鉴权）"""
        self.client.get("/health", name="/health")


class EmpValueManagerUser(HttpUser):
    """模拟主管审批行为"""

    wait_time = between(2, 5)
    weight = 1

    def on_start(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "manager@empvalue.ai", "password": "empvalue123"},
            name="/auth/login",
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {"x-user-role": "manager", "x-user-id": "M001"}

    @task(2)
    def get_pending_approvals(self):
        """查询待审批列表"""
        self.client.get(
            "/api/v1/manager/pending-approvals",
            headers=self.headers,
            name="/manager/pending-approvals",
        )

    @task(1)
    def get_manager_dashboard(self):
        """主管仪表盘"""
        self.client.get(
            "/api/v1/manager/dashboard",
            headers=self.headers,
            name="/manager/dashboard",
        )

    @task(1)
    def get_team_analytics(self):
        """团队分析"""
        self.client.post(
            "/api/v1/teams/team-1/analytics",
            json={"members": ["E1001", "E1002", "E1003"]},
            headers=self.headers,
            name="/teams/[id]/analytics",
        )
