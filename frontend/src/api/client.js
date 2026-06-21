import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default api

export const evaluationApi = {
  create: (payload) => api.post('/evaluations', payload),
  get: (id) => api.get(`/evaluations/${id}`),
  approve: (id, payload) => api.post(`/evaluations/${id}/approve`, payload),
  reject: (id, payload) => api.post(`/evaluations/${id}/reject`, payload),
  auditLogs: (id) => api.get(`/evaluations/${id}/audit-logs`),
}

export const adminApi = {
  modelStatus: () => api.get('/admin/model-status'),
}
