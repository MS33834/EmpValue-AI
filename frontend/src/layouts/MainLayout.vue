<template>
  <el-container class="main-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">EmpValue-AI</div>
      <el-menu
        :default-active="activeMenu"
        class="menu"
        router
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
        </template>

        <template v-if="auth.role === 'manager' || auth.role === 'hr' || auth.role === 'admin'">
          <el-menu-item index="/manager">
            <el-icon><UserFilled /></el-icon>
            <span>团队诊断</span>
          </el-menu-item>
        </template>

        <el-menu-item @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="header-title">{{ pageTitle }}</span>
        <span class="header-role">当前角色：{{ roleLabel }}</span>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
