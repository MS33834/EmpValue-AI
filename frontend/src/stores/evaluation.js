import { defineStore } from 'pinia'
import { ref } from 'vue'
import { evaluationApi } from '@/api/client'

export const useEvaluationStore = defineStore('evaluation', () => {
  const currentEvaluation = ref(null)
  const loading = ref(false)
  const error = ref('')

  async function createEvaluation(payload) {
    loading.value = true
    error.value = ''
    try {
      const res = await evaluationApi.create(payload)
      currentEvaluation.value = res.evaluation || null
      return res
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function approveEvaluation(id, payload) {
    return evaluationApi.approve(id, payload)
  }

  async function rejectEvaluation(id, payload) {
    return evaluationApi.reject(id, payload)
  }

  async function fetchAuditLogs(id) {
    return evaluationApi.auditLogs(id)
  }

  return {
    currentEvaluation,
    loading,
    error,
    createEvaluation,
    approveEvaluation,
    rejectEvaluation,
    fetchAuditLogs,
  }
})
