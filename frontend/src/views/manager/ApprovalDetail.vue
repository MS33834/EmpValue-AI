<template>
  <div class="approval-detail">
    <el-page-header @back="goBack" title="评估审批" />

    <el-card v-if="evaluation" class="detail-card">
      <template #header>
        <div class="card-header">
          <span>评估详情</span>
          <el-tag :type="statusType">{{ evaluation.status }}</el-tag>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="12">
          <h3>员工视图（建设性）</h3>
          <p><strong>总结：</strong>{{ employeeView.summary }}</p>
          <p><strong>优势：</strong>{{ (employeeView.strengths || []).join('；') }}</p>
          <p><strong>下周聚焦：</strong>{{ (employeeView.next_week_focus || []).join('；') }}</p>
        </el-col>
        <el-col :span="12">
          <h3>管理视图（尖锐诊断）</h3>
          <p><strong>总体判断：</strong>{{ managerView.harsh_assessment }}</p>
          <p><strong>ROI 分析：</strong>{{ managerView.roi_analysis }}</p>
          <p><strong>调配建议：</strong>{{ managerView.reallocation_suggestion }}</p>
          <p><strong>隐藏问题：</strong>{{ (managerView.hidden_issues || []).join('；') }}</p>
        </el-col>
      </el-row>

      <el-divider />

      <h3>风险标记</h3>
      <el-alert
        v-for="(flag, idx) in managerView.risk_flags || []"
        :key="idx"
        :title="`${flag.level} - ${flag.category}`"
        :description="flag.description"
        :type="riskType(flag.level)"
        show-icon
        class="risk-alert"
      />

      <el-divider />

      <h3>审批操作</h3>
      <el-form label-position="top">
        <el-form-item label="审批意见">
          <el-input v-model="comment" type="textarea" :rows="3" placeholder="请输入审批意见" />
        </el-form-item>
        <el-form-item>
          <el-button type="success" @click="approve">通过</el-button>
          <el-button type="danger" @click="reject">驳回</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-empty v-else description="未找到评估数据" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEvaluationStore } from '@/stores/evaluation'

const route = useRoute()
const router = useRouter()
const evalStore = useEvaluationStore()

const comment = ref('')
const evaluation = computed(() => evalStore.currentEvaluation)
const employeeView = computed(() => evaluation.value?.employee_view || {})
const managerView = computed(() => evaluation.value?.manager_view || {})

const statusType = computed(() => {
  const map = { approved: 'success', rejected: 'danger', ai_drafted: 'warning', hr_audit: 'warning' }
  return map[evaluation.value?.status] || 'info'
})

function riskType(level) {
  const map = { critical: 'error', high: 'warning', medium: 'warning', low: 'info' }
  return map[level] || 'info'
}

async function approve() {
  await evalStore.approveEvaluation(evaluation.value.evaluation_id, {
    current_status: evaluation.value.status,
    actor_id: 'M001',
    comment: comment.value,
  })
  router.push('/manager')
}

async function reject() {
  await evalStore.rejectEvaluation(evaluation.value.evaluation_id, {
    current_status: evaluation.value.status,
    actor_id: 'M001',
    comment: comment.value,
  })
  router.push('/manager')
}

function goBack() {
  router.push('/manager')
}
</script>

<style scoped>
.approval-detail {
  padding: 10px;
}
.detail-card {
  margin-top: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.risk-alert {
  margin-bottom: 12px;
}
</style>
