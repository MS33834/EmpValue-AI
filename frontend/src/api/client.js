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
  if (authStore.role) {
    config.headers['x-user-role'] = authStore.role
  }
  if (authStore.userId) {
    config.headers['x-user-id'] = authStore.userId
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      import('@/stores/auth').then(({ useAuthStore }) => {
        useAuthStore().logout()
        window.location.href = '/login'
      })
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
  switchModel: (payload) => api.post('/admin/model-switch', payload),
}
