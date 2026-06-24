<template>
  <div class="employee-history">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>综合得分趋势</span>
              <el-button size="small" @click="loadData">刷新</el-button>
            </div>
          </template>
          <v-chart
            v-if="trendPeriods.length"
            class="trend-chart"
            :option="trendOption"
            autoresize
          />
          <el-empty v-else description="暂无历史评估数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>历史评估明细</span>
          </template>
          <el-table
            :data="evaluations"
            style="width: 100%"
            row-key="evaluation_id"
            empty-text="暂无历史评估"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-detail">
                  <h4>维度得分详情</h4>
                  <el-table
                    :data="row.employee_view?.growth_areas || []"
                    border
                    style="width: 100%"
                  >
                    <el-table-column prop="dimension" label="维度" />
                    <el-table-column prop="score" label="得分" sortable />
                    <el-table-column label="依据">
                      <template #default="{ row: area }">
                        {{ (area.evidence || []).join('；') || '—' }}
                      </template>
                    </el-table-column>
                    <el-table-column label="改进建议">
                      <template #default="{ row: area }">
                        {{ (area.improvement_actions || []).join('；') || '—' }}
                      </template>
                    </el-table-column>
                  </el-table>
                  <p v-if="row.employee_view?.summary" class="summary">
                    <strong>总结：</strong>{{ row.employee_view.summary }}
                  </p>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="period" label="周期" />
            <el-table-column prop="overall_score" label="综合得分" sortable />
            <el-table-column label="状态">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { employeeApi } from '@/api/client'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

const auth = useAuthStore()
const loading = ref(false)
const evaluations = ref([])

const statusMap = {
  ai_drafted: { label: 'AI草稿', type: 'info' },
  manager_review: { label: '主管审核中', type: 'warning' },
  hr_audit: { label: 'HR复核中', type: 'warning' },
  approved: { label: '已审批', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
}

function statusType(status) {
  return statusMap[status]?.type || 'info'
}

function statusLabel(status) {
  return statusMap[status]?.label || status || '未知'
}

const trendPeriods = computed(() => {
  return [...evaluations.value].reverse().map((e) => e.period)
})

const trendScores = computed(() => {
  return [...evaluations.value].reverse().map((e) => e.overall_score)
})

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: trendPeriods.value,
    boundaryGap: false,
  },
  yAxis: { type: 'value', min: 0, max: 100 },
  series: [
    {
      name: '综合得分',
      type: 'line',
      data: trendScores.value,
      smooth: true,
      areaStyle: { color: 'rgba(103, 194, 58, 0.2)' },
      lineStyle: { color: '#67c23a' },
      itemStyle: { color: '#67c23a' },
    },
  ],
}))

async function loadData() {
  loading.value = true
  try {
    const data = await employeeApi.history(auth.userId)
    evaluations.value = data.evaluations || []
  } catch (err) {
    console.error('加载历史评估失败:', err)
    ElMessage.error('加载历史评估失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.mt-20 {
  margin-top: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.trend-chart {
  width: 100%;
  height: 320px;
}
.expand-detail {
  padding: 12px 24px;
}
.expand-detail h4 {
  margin: 0 0 12px 0;
}
.summary {
  margin-top: 12px;
  color: #374151;
  line-height: 1.6;
}
</style>
