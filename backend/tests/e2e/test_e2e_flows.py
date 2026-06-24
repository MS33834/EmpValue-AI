# @pytestmark: playwright
"""
EmpValue-AI E2E 测试（Playwright）

前置条件：
    1. 后端服务运行在 http://localhost:8000
    2. 前端服务运行在 http://localhost:5173
    3. 已执行 POST /api/v1/auth/seed-demo-users 初始化演示账号

运行方式：
    pytest tests/e2e/ -v
    # 或直接用 playwright
    playwright test tests/e2e/
"""

import re

import pytest

pytestmark = pytest.mark.e2e

BASE_URL = "http://localhost:5173"
API_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def browser_context(playwright):
    """启动浏览器"""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()
    browser.close()


class TestLoginFlow:
    """登录流程 E2E"""

    def test_demo_login_employee(self, browser_context):
        """演示模式登录员工端"""
        page = browser_context
        page.goto(f"{BASE_URL}/login")

        # 切换到演示模式 tab
        page.get_by_role("tab", name="演示模式").click()

        # 选择员工角色
        page.get_by_placeholder("请选择角色").click()
        page.get_by_role("option", name="员工").click()

        # 点击进入系统
        page.get_by_role("button", name="进入系统").click()

        # 应跳转到员工页面
        page.wait_for_url("**/employee**", timeout=5000)
        assert "/employee" in page.url

    def test_jwt_login_employee(self, browser_context):
        """JWT 登录员工端（需后端运行 + 演示账号已初始化）"""
        page = browser_context
        page.goto(f"{BASE_URL}/login")

        # 确保在账号登录 tab
        page.get_by_role("tab", name="账号登录").click()

        # 填写邮箱密码
        page.get_by_placeholder("请输入邮箱").fill("employee@empvalue.ai")
        page.get_by_placeholder("请输入密码").fill("empvalue123")

        # 点击登录
        page.get_by_role("button", name="登录").click()

        # 应跳转到员工页面
        page.wait_for_url("**/employee**", timeout=10000)
        assert "/employee" in page.url


class TestEmployeeFlow:
    """员工操作流程 E2E"""

    def test_employee_submit_input(self, browser_context):
        """员工提交日报"""
        page = browser_context
        # 先登录
        page.goto(f"{BASE_URL}/login")
        page.get_by_role("tab", name="演示模式").click()
        page.get_by_placeholder("请选择角色").click()
        page.get_by_role("option", name="员工").click()
        page.get_by_role("button", name="进入系统").click()
        page.wait_for_url("**/employee**", timeout=5000)

        # 导航到输入页（如有）
        # 实际选择器需根据前端页面结构调整
        # page.click("text=提交日报")
        # page.fill("[data-testid=content]", "E2E 测试日报内容")
        # page.click("button:has-text('提交')")


class TestManagerFlow:
    """主管审批流程 E2E"""

    def test_manager_view_dashboard(self, browser_context):
        """主管查看仪表盘"""
        page = browser_context
        page.goto(f"{BASE_URL}/login")
        page.get_by_role("tab", name="演示模式").click()
        page.get_by_placeholder("请选择角色").click()
        page.get_by_role("option", name="主管").click()
        page.get_by_role("button", name="进入系统").click()
        page.wait_for_url("**/manager**", timeout=5000)
        assert "/manager" in page.url


class TestApiIntegration:
    """API 集成测试（通过 Playwright 发起请求）"""

    def test_health_check(self, browser_context):
        """健康检查"""
        page = browser_context
        response = page.request.get(f"{API_URL}/health")
        assert response.status == 200
        body = response.json()
        assert body["status"] == "ok"

    def test_auth_flow(self, browser_context):
        """认证全流程：注册 → 登录 → /me"""
        page = browser_context

        # 注册
        resp = page.request.post(
            f"{API_URL}/api/v1/auth/register",
            data={
                "user_id": "E2E001",
                "name": "E2E测试用户",
                "email": "e2e-test@empvalue.ai",
                "password": "e2etest123",
                "role": "employee",
            },
        )
        assert resp.status in (201, 409)  # 409 = 已存在

        # 登录
        resp = page.request.post(
            f"{API_URL}/api/v1/auth/login",
            data={"email": "e2e-test@empvalue.ai", "password": "e2etest123"},
        )
        assert resp.status == 200
        token = resp.json()["access_token"]

        # /me
        resp = page.request.get(
            f"{API_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status == 200
        assert resp.json()["user_id"] == "E2E001"

    def test_evaluation_interrupt_flow(self, browser_context):
        """interrupt 审批流 E2E"""
        page = browser_context

        # 登录获取 manager token
        resp = page.request.post(
            f"{API_URL}/api/v1/auth/login",
            data={"email": "manager@empvalue.ai", "password": "empvalue123"},
        )
        if resp.status != 200:
            pytest.skip("演示账号未初始化")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 启动 interrupt 评估
        resp = page.request.post(
            f"{API_URL}/api/v1/evaluations-interrupt",
            data={
                "employee_id": "E2E002",
                "period": "2026-W26",
                "raw_inputs": [
                    {"input_id": "e2e-001", "content": "E2E 测试 interrupt 流程"}
                ],
            },
            headers=headers,
        )
        assert resp.status == 200
        data = resp.json()
        assert data["status"] == "awaiting_review"
        thread_id = data["thread_id"]

        # 恢复审批
        resp = page.request.post(
            f"{API_URL}/api/v1/evaluations-interrupt/{thread_id}/resume",
            data={"action": "approve", "comment": "E2E 审批通过"},
            headers=headers,
        )
        assert resp.status == 200
        assert resp.json()["status"] == "approved"
