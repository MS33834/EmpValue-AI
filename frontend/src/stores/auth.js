import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const role = ref(localStorage.getItem('empvalue_role') || '')
  const userId = ref(localStorage.getItem('empvalue_user_id') || '')

  const isLoggedIn = computed(() => !!role.value)

  function login(selectedRole, id = 'U001') {
    role.value = selectedRole
    userId.value = id
    localStorage.setItem('empvalue_role', selectedRole)
    localStorage.setItem('empvalue_user_id', id)
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
