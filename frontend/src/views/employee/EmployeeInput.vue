<template>
  <div class="employee-input">
    <el-card>
      <template #header>
        <span>录入本周工作数据</span>
      </template>

      <el-form label-position="top" :model="form">
        <el-form-item label="评估周期">
          <el-input v-model="form.period" placeholder="例如：2026-W25" />
        </el-form-item>

        <el-form-item label="日报内容">
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
          <el-button type="primary" :loading="evalStore.loading || polling" @click="submit">
            提交并生成评估
          </el-button>
        </el-form-item>
      </el-form>

      <el-result
        v-if="resultVisible"
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
import { reactive, ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useEvaluationStore, cancelPolling } from '@/stores/evaluation'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const evalStore = useEvaluationStore()
const auth = useAuthStore()

const form = reactive({
  period: '2026-W25',
  content: '',
  tasks: '',
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
  if (!form.period.trim()) {
    ElMessage.warning('请输入评估周期')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请输入日报内容')
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
      employee_id: auth.userId || 'E1001',
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
