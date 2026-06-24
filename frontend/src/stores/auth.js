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

  const isLoggedIn = computed(() => !!role.value)

  function login(selectedRole, id = null) {
    role.value = selectedRole
    userId.value = id || defaultUserId(selectedRole)
    localStorage.setItem('empvalue_role', selectedRole)
    localStorage.setItem('empvalue_user_id', userId.value)
  }

  function logout() {
    role.value = ''
    userId.value = ''
    localStorage.removeItem('empvalue_role')
    localStorage.removeItem('empvalue_user_id')
  }

  return {
    role,
    userId,
    isLoggedIn,
    login,
    logout,
  }
})
