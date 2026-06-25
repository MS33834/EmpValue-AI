import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  // JWT 模式：发送 Bearer token
  if (authStore.useJwt && authStore.token) {
    config.headers['Authorization'] = `Bearer ${authStore.token}`
  } else {
    // 演示模式：通过 header 传递角色与用户 ID
    if (authStore.role) {
      config.headers['x-user-role'] = authStore.role
    }
    if (authStore.userId) {
      config.headers['x-user-id'] = authStore.userId
    }
  }
  return config
})

let isRefreshing = false
let refreshPromise = null

function redirectToLogin() {
  useAuthStore().logout()
  window.location.href = '/login'
}

api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status
    const isRefreshReq = originalRequest?.url?.includes('/auth/refresh')

    if (status === 401 && originalRequest && !originalRequest._retry && !isRefreshReq) {
      const authStore = useAuthStore()
      if (!authStore.useJwt) {
        redirectToLogin()
        return Promise.reject(new Error('登录已过期，请重新登录'))
      }
      originalRequest._retry = true
      try {
        if (!isRefreshing) {
          isRefreshing = true
          refreshPromise = authApi.refresh().finally(() => {
            isRefreshing = false
            refreshPromise = null
          })
        }
        const data = await refreshPromise
        const newToken = data?.token || data?.access_token
        if (newToken) {
          authStore.token = newToken
          localStorage.setItem('empvalue_token', newToken)
        }
        return api(originalRequest)
      } catch (refreshErr) {
        redirectToLogin()
        return Promise.reject(new Error('登录已过期，请重新登录'))
      }
    }

    if (status === 401 && !isRefreshReq) {
      redirectToLogin()
    }

    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default api

export const evaluationApi = {
  create: (payload) => api.post('/evaluations', payload),
  getJob: (jobId) => api.get(`/evaluations/jobs/${jobId}`),
  get: (id) => api.get(`/evaluations/${id}`),
  getEmployeeView: (id) => api.get(`/evaluations/${id}/employee-view`),
  getManagerView: (id) => api.get(`/evaluations/${id}/manager-view`),
  approve: (id, payload) => api.post(`/evaluations/${id}/approve`, payload),
  reject: (id, payload) => api.post(`/evaluations/${id}/reject`, payload),
  requestHrReview: (id, payload) => api.post(`/evaluations/${id}/request-hr-review`, payload),
  appeal: (id, payload) => api.post(`/evaluations/${id}/appeal`, payload),
  reEvaluate: (id, payload) => api.post(`/evaluations/${id}/re-evaluate`, payload),
  feedback: (id, payload) => api.post(`/evaluations/${id}/feedback`, payload),
  auditLogs: (id) => api.get(`/evaluations/${id}/audit-logs`),
}

export const managerApi = {
  pendingApprovals: () => api.get('/manager/pending-approvals'),
  dashboard: () => api.get('/manager/dashboard'),
  teamAnalytics: (teamId, members) => api.post(`/teams/${teamId}/analytics`, { members }),
}

export const hrApi = {
  auditQueue: () => api.get('/hr/audit-queue'),
}

export const employeeApi = {
  dashboard: (employeeId) => api.get(`/employees/${employeeId}/dashboard`),
  history: (employeeId) => api.get(`/employees/${employeeId}/history`),
}

export const inputApi = {
  create: (payload) => api.post('/inputs', payload),
  list: (employeeId, period) => api.get('/inputs', { params: { employee_id: employeeId, period } }),
}

export const adminApi = {
  modelStatus: () => api.get('/admin/model-status'),
  switchModel: (tier) => api.post('/admin/model-switch', { tier }),
  auditLogs: (params) => api.get('/admin/audit-logs', { params }),
}

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (payload) => api.post('/auth/register', payload),
  me: () => api.get('/auth/me'),
  refresh: () => api.post('/auth/refresh'),
  seedDemoUsers: () => api.post('/auth/seed-demo-users'),
}
