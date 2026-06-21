<template>
  <div class="manager-dashboard">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>团队价值排行榜</span>
          </template>
          <el-table :data="teamRankings" style="width: 100%">
            <el-table-column prop="rank" label="排名" width="80" />
            <el-table-column prop="name" label="姓名" />
            <el-table-column prop="score" label="综合得分" sortable />
            <el-table-column prop="tier" label="档位" />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="viewDetail(row)">
                  查看诊断
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>待审批评估</span>
          </template>
          <el-empty description="暂无待审批评估" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>团队风险分布</span>
          </template>
          <div class="risk-summary">
            <el-statistic title="高风险" :value="2" value-style="color: #f56c6c" />
            <el-statistic title="中风险" :value="3" value-style="color: #e6a23c" />
            <el-statistic title="低风险" :value="8" value-style="color: #67c23a" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const teamRankings = ref([
  { rank: 1, name: '张三', score: 92, tier: 'L3' },
  { rank: 2, name: '李四', score: 85, tier: 'L2' },
  { rank: 3, name: '王五', score: 78, tier: 'L2' },
  { rank: 4, name: '赵六', score: 65, tier: 'L1' },
  { rank: 5, name: '孙七', score: 55, tier: 'L1' },
])

function viewDetail(row) {
  router.push(`/manager/approval/${row.rank}`)
}
</script>

<style scoped>
.mt-20 {
  margin-top: 20px;
}
.risk-summary {
  display: flex;
  justify-content: space-around;
  padding: 20px 0;
}
</style>
