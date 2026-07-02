<template>
  <el-container class="main-layout">
    <!-- 安全合规：管理视图水印防截图（仅 manager/hr/admin 显示，employee 隐藏） -->
    <Watermark v-if="['manager', 'hr', 'admin'].includes(auth.role)" />
    <!-- 无障碍：跳转到主内容，键盘用户可快速跳过导航 -->
    <a href="#main-content" class="skip-link">跳转到主内容</a>
    <el-aside width="220px" class="sidebar">
      <div class="logo" role="heading" aria-level="1">EmpValue-AI</div>
      <el-menu
        :default-active="activeMenu"
        class="menu"
        router
        aria-label="主导航"
        background-color="#1f2937"
        text-color="#e5e7eb"
        active-text-color="#67c23a"
      >
        <template v-if="auth.role === 'employee'">
          <el-menu-item index="/employee">
            <el-icon><TrendCharts /></el-icon>
            <span>成长看板</span>
          </el-menu-item>
          <el-menu-item index="/employee/input">
            <el-icon><Document /></el-icon>
            <span>录入日报</span>
          </el-menu-item>
          <el-menu-item index="/employee/history">
            <el-icon><Timer /></el-icon>
            <span>历史评估</span>
          </el-menu-item>
          <el-menu-item index="/employee/feedback">
            <el-icon><ChatDotRound /></el-icon>
            <span>反馈申诉</span>
          </el-menu-item>
        </template>

        <template v-if="auth.role === 'hr' || auth.role === 'admin'">
          <el-menu-item index="/hr">
            <el-icon><View /></el-icon>
            <span>HR复核</span>
          </el-menu-item>
        </template>

        <template v-if="auth.role === 'manager' || auth.role === 'admin'">
          <el-menu-item index="/manager">
            <el-icon><UserFilled /></el-icon>
            <span>团队诊断</span>
          </el-menu-item>
        </template>

        <template v-if="auth.role === 'manager' || auth.role === 'hr' || auth.role === 'admin'">
          <el-menu-item index="/manager/team">
            <el-icon><DataAnalysis /></el-icon>
            <span>团队分析</span>
          </el-menu-item>
        </template>

        <template v-if="auth.role === 'admin'">
          <el-menu-item index="/admin">
            <el-icon><Setting /></el-icon>
            <span>模型管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/audit-logs">
            <el-icon><Tickets /></el-icon>
            <span>审计日志</span>
          </el-menu-item>
        </template>

        <el-menu-item aria-label="退出登录" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header" role="banner">
        <span class="header-title">{{ pageTitle }}</span>
        <span class="header-role" aria-live="polite">当前角色：{{ roleLabel }}</span>
      </el-header>
      <el-main id="main-content" class="main-content" tabindex="-1">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Watermark from '@/components/Watermark.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)

const roleLabel = computed(() => {
  const map = { employee: '员工', manager: '主管', hr: 'HR', admin: '管理员' }
  return map[auth.role] || auth.role
})

const pageTitle = computed(() => route.meta.title || 'EmpValue-AI')

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}
/* 无障碍：跳转链接默认隐藏，键盘聚焦时显现 */
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 1000;
  padding: 8px 16px;
  /* 无障碍：加深底色使白色文字对比度达到 AA（原 #409eff 对白文字仅约 2.8:1） */
  background: #2563eb;
  color: #fff;
  border-radius: 0 0 4px 0;
  text-decoration: none;
  font-size: 14px;
}
.skip-link:focus {
  left: 0;
}
/* 主内容区获得焦点时去除默认轮廓偏移，保留可见焦点环 */
#main-content:focus {
  outline: none;
}
.sidebar {
  background-color: #1f2937;
  color: #fff;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-size: 18px;
  font-weight: bold;
  border-bottom: 1px solid #374151;
}
.menu {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  z-index: 10;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
.header-role {
  font-size: 14px;
  color: #606266;
}
.main-content {
  background-color: #f3f4f6;
  overflow-y: auto;
}
</style>
