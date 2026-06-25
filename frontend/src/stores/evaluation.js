import { defineStore } from 'pinia'
import { ref } from 'vue'
import { evaluationApi } from '@/api/client'

let cancelFlag = false

export function cancelPolling() {
  cancelFlag = true
}

export const useEvaluationStore = defineStore('evaluation', () => {
  const currentEvaluation = ref(null)
  const loading = ref(false)
  const error = ref('')

  async function createEvaluation(payload) {
    loading.value = true
    error.value = ''
    try {
      const res = await evaluationApi.create(payload)
      return res
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function pollJob(jobId, onUpdate) {
    cancelFlag = false
    const interval = 2000
    const maxAttempts = 60
    const maxTotalTimeout = 5 * 60 * 1000
    const startTime = Date.now()
    let consecutiveFailures = 0

    for (let i = 0; i < maxAttempts; i++) {
      if (cancelFlag) {
        throw new Error('评估任务已取消')
      }
      if (Date.now() - startTime > maxTotalTimeout) {
        throw new Error('评估任务超时，请稍后刷新页面查看结果')
      }
      let job
      try {
        job = await evaluationApi.getJob(jobId)
        consecutiveFailures = 0
      } catch (err) {
        consecutiveFailures += 1
        console.warn('轮询评估任务失败:', err.message)
        if (consecutiveFailures > 5) {
          throw err
        }
        await new Promise((resolve) => setTimeout(resolve, interval))
        continue
      }
      if (onUpdate) onUpdate(job)
      if (job.status === 'completed' || job.status === 'failed') {
        if (job.status === 'completed') {
          currentEvaluation.value = job.evaluation || null
        }
        return job
      }
      await new Promise((resolve) => setTimeout(resolve, interval))
    }
    throw new Error('评估任务超时，请稍后刷新页面查看结果')
  }

  function cancelEvaluation() {
    cancelPolling()
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
    pollJob,
    cancelEvaluation,
    approveEvaluation,
    rejectEvaluation,
    fetchAuditLogs,
  }
})
