<template>
  <div class="employee-dashboard">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>我的成长看板</span>
          </template>
          <div v-if="evalStore.currentEvaluation">
            <h3>{{ evalStore.currentEvaluation.period }} 评估总结</h3>
            <p class="summary">{{ employeeView.summary }}</p>

            <h4>优势</h4>
            <ul>
              <li v-for="(s, idx) in employeeView.strengths" :key="idx">{{ s }}</li>
            </ul>

            <h4>成长方向</h4>
            <el-timeline>
              <el-timeline-item
                v-for="area in employeeView.growth_areas"
                :key="area.dimension"
                type="primary"
              >
                <strong>{{ area.dimension }}</strong> — {{ area.score }} 分
                <div class="evidence">依据：{{ area.evidence.join('；') }}</div>
                <div class="action">建议：{{ area.improvement_actions.join('；') }}</div>
              </el-timeline-item>
            </el-timeline>

            <h4>下周聚焦</h4>
            <el-tag v-for="(focus, idx) in employeeView.next_week_focus" :key="idx" class="focus-tag">
              {{ focus }}
            </el-tag>
          </div>
          <el-empty v-else description="暂无评估数据，请先录入日报" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>
            <span>能力雷达图</span>
          </template>
          <RadarChart
            :dimensions="radarDimensions"
            :scores="radarScores"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useEvaluationStore } from '@/stores/evaluation'
import RadarChart from '@/components/RadarChart.vue'

const evalStore = useEvaluationStore()

const employeeView = computed(() => {
  return evalStore.currentEvaluation?.employee_view || {}
})

const radarDimensions = computed(() => {
  return (employeeView.value.growth_areas || []).map((a) => a.dimension)
})

const radarScores = computed(() => {
  return (employeeView.value.growth_areas || []).map((a) => a.score)
})
</script>

<style scoped>
.employee-dashboard h3 {
  margin-top: 0;
}
.summary {
  color: #374151;
  line-height: 1.6;
}
.evidence {
  color: #6b7280;
  font-size: 13px;
  margin-top: 4px;
}
.action {
  color: #409eff;
  font-size: 13px;
  margin-top: 4px;
}
.focus-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}
</style>
