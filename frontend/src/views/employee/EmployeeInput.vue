<template>
  <div class="employee-input">
    <el-card>
      <template #header>
        <span>录入本周工作数据</span>
      </template>

      <el-form ref="formRef" label-position="top" :model="form" :rules="rules">
        <el-form-item label="评估周期" prop="period">
          <el-input v-model="form.period" placeholder="例如：2026-W25" @keyup.enter="submit" />
        </el-form-item>

        <el-form-item label="日报内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="6"
            placeholder="请描述本周工作内容、成果、遇到的阻塞等"
          />
        </el-form-item>

        <el-form-item label="任务进度">
          <el-input
            v-model="form.tasks"
            type="textarea"
            :rows="3"
            placeholder="例如：JIRA-2048 进度 100%；JIRA-2051 进度 60%"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="evalStore.loading || polling"
            :disabled="!isFormValid"
            @click="submit"
          >
            提交并生成评估
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 无障碍：评估结果在轮询中动态更新，用 role=status + aria-live 通告屏幕阅读器 -->
      <el-result
        v-if="resultVisible"
        role="status"
        aria-live="polite"
        :icon="resultIcon"
        :title="resultTitle"
        :sub-title="resultSubtitle"
      >
        <template #extra>
          <el-button type="primary" @click="goDashboard">查看成长看板</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useEvaluationStore, cancelPolling } from '@/stores/evaluation'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const evalStore = useEvaluationStore()
const auth = useAuthStore()

const formRef = ref(null)

// 计算当前 ISO 周期，例如 2026-W26
function currentIsoWeek() {
  const now = new Date()
  const target = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  const dayNum = (target.getUTCDay() + 6) % 7
  target.setUTCDate(target.getUTCDate() - dayNum + 3)
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4))
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3)
  const weekNum = 1 + Math.round((target - firstThursday) / (7 * 24 * 3600 * 1000))
  return `${target.getUTCFullYear()}-W${String(weekNum).padStart(2, '0')}`
}

const form = reactive({
  period: currentIsoWeek(),
  content: '',
  tasks: '',
})

const rules = {
  period: [
    { required: true, message: '请输入评估周期', trigger: 'blur' },
    {
      pattern: /^\d{4}-W(?:0[1-9]|[1-4]\d|5[0-3])$/,
      message: '周期格式不正确，例如：2026-W25',
      trigger: 'blur',
    },
  ],
  content: [{ required: true, message: '请输入日报内容', trigger: 'blur' }],
}

const isFormValid = computed(() => {
  return (
    /^\d{4}-W(?:0[1-9]|[1-4]\d|5[0-3])$/.test(form.period.trim()) &&
    form.content.trim().length > 0
  )
})

const resultVisible = ref(false)
const resultIcon = ref('success')
const resultTitle = ref('')
const resultSubtitle = ref('')
const polling = ref(false)

function genId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    ElMessage.warning('请检查表单填写是否正确')
    return
  }
  if (!auth.userId) {
    ElMessage.error('用户信息缺失，请重新登录')
    return
  }
  const rawInputs = [
    { input_id: `daily-${genId()}`, type: 'daily_report', content: form.content, attachments: [] },
  ]
  if (form.tasks.trim()) {
    rawInputs.push({
      input_id: `task-${genId()}`,
      type: 'task_progress',
      content: form.tasks,
      attachments: [],
    })
  }

  try {
    resultVisible.value = true
    resultIcon.value = 'info'
    resultTitle.value = '评估任务已提交'
    resultSubtitle.value = '正在后台生成，请稍候...'
    polling.value = true

    const { job_id } = await evalStore.createEvaluation({
      employee_id: auth.userId,
      period: form.period,
      raw_inputs: rawInputs,
    })

    const job = await evalStore.pollJob(job_id, (job) => {
      if (job.status === 'pending') {
        resultSubtitle.value = 'AI 正在处理中，请稍候...'
      }
    })

    if (job.status === 'failed') {
      throw new Error(job.error || '评估任务失败')
    }

    resultIcon.value = 'success'
    resultTitle.value = '评估已生成'
    resultSubtitle.value = `状态：${evalStore.currentEvaluation?.status}，综合得分：${evalStore.currentEvaluation?.overall_score}`
  } catch (err) {
    resultIcon.value = 'error'
    resultTitle.value = '生成失败'
    resultSubtitle.value = err.message
  } finally {
    polling.value = false
  }
}

function goDashboard() {
  router.push('/employee')
}

onBeforeUnmount(() => {
  cancelPolling()
})
</script>
