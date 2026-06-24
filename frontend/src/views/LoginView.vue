<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <div class="login-header">EmpValue-AI</div>
      </template>
      <p class="login-subtitle">AI 驱动员工价值量化与成长系统</p>

      <el-form label-position="top" class="login-form">
        <el-form-item label="选择角色（演示模式）">
          <el-select v-model="selectedRole" placeholder="请选择角色" style="width: 100%">
            <el-option label="员工" value="employee" />
            <el-option label="主管" value="manager" />
            <el-option label="HR" value="hr" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" style="width: 100%" @click="handleLogin">
            进入系统
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const selectedRole = ref('employee')

function handleLogin() {
  auth.login(selectedRole.value)
  const redirectMap = {
    employee: '/employee',
    manager: '/manager',
    hr: '/hr',
    admin: '/admin',
  }
  router.push(redirectMap[selectedRole.value] || '/employee')
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
}
.login-card {
  width: 400px;
}
.login-header {
  text-align: center;
  font-size: 22px;
  font-weight: bold;
}
.login-subtitle {
  text-align: center;
  color: #606266;
  margin-bottom: 24px;
}
</style>
