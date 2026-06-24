import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function defaultUserId(role) {
  const map = {
    employee: 'E1001',
    manager: 'M001',
    hr: 'HR001',
    admin: 'ADMIN001',
  }
  return map[role] || 'U001'
}

export const useAuthStore = defineStore('auth', () => {
  const role = ref(localStorage.getItem('empvalue_role') || '')
  const userId = ref(localStorage.getItem('empvalue_user_id') || '')
  const name = ref(localStorage.getItem('empvalue_name') || '')
  const token = ref(localStorage.getItem('empvalue_token') || '')
  // 是否使用 JWT 真实认证；false 表示演示模式（header 伪造角色）
  const useJwt = ref(!!token.value)

  const isLoggedIn = computed(() => !!role.value)

  function loginWithToken(tokenValue, payload) {
    token.value = tokenValue
    role.value = payload.role
    userId.value = payload.user_id
    name.value = payload.name || ''
    useJwt.value = true
    localStorage.setItem('empvalue_token', tokenValue)
    localStorage.setItem('empvalue_role', payload.role)
    localStorage.setItem('empvalue_user_id', payload.user_id)
    localStorage.setItem('empvalue_name', name.value)
  }

  function loginDemo(selectedRole, id = null) {
    role.value = selectedRole
    userId.value = id || defaultUserId(selectedRole)
    name.value = ''
    token.value = ''
    useJwt.value = false
    localStorage.setItem('empvalue_role', selectedRole)
    localStorage.setItem('empvalue_user_id', userId.value)
    localStorage.removeItem('empvalue_token')
    localStorage.removeItem('empvalue_name')
  }

  // 兼容旧调用：默认走演示模式
  function login(selectedRole, id = null) {
    loginDemo(selectedRole, id)
  }

  function logout() {
    role.value = ''
    userId.value = ''
    name.value = ''
    token.value = ''
    useJwt.value = false
    localStorage.removeItem('empvalue_role')
    localStorage.removeItem('empvalue_user_id')
    localStorage.removeItem('empvalue_name')
    localStorage.removeItem('empvalue_token')
  }

  return {
    role,
    userId,
    name,
    token,
    useJwt,
    isLoggedIn,
    login,
    loginWithToken,
    loginDemo,
    logout,
  }
})
