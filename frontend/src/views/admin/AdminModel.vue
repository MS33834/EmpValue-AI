<template>
  <div class="admin-model">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card v-loading="loading" :aria-busy="loading">
          <template #header>
            <span>当前模型状态</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="当前档位">
              <el-tag type="success">{{ currentTier }}</el-tag>
              <span class="tier-desc">{{ tierInfo(currentTier).description }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模型名称">
              {{ tierInfo(currentTier).model_name }}
            </el-descriptions-item>
            <el-descriptions-item label="提供商类型">
              {{ tierInfo(currentTier).provider_type === 'cloud' ? '云端' : '本地' }}
            </el-descriptions-item>
            <el-descriptions-item label="推荐档位">
              <el-tag type="warning">{{ modelStatus.recommended_tier }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card v-loading="loading" :aria-busy="loading">
          <template #header>
            <span>硬件信息</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="内存 (GB)">
              {{ (modelStatus.ram_gb || 0).toFixed(1) }}
            </el-descriptions-item>
            <el-descriptions-item label="显存 (GB)">
              {{ (modelStatus.vram_gb || 0).toFixed(1) }}
            </el-descriptions-item>
            <el-descriptions-item label="GPU 数量">
              {{ modelStatus.gpu_count || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="GPU 名称">
              {{ (modelStatus.gpu_names || []).join('、') || '无' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>切换模型档位</span>
          </template>
          <el-radio-group v-model="selectedTier" class="tier-radio-group">
            <el-radio-button
              v-for="tier in tiers"
              :key="tier.value"
              :value="tier.value"
            >
              {{ tier.label }}
            </el-radio-button>
          </el-radio-group>
          <div class="tier-detail">
            <strong>{{ tierInfo(selectedTier).description }}</strong>
            <p>模型：{{ tierInfo(selectedTier).model_name }}</p>
            <p v-if="tierInfo(selectedTier).min_ram_gb">
              最低内存 {{ tierInfo(selectedTier).min_ram_gb }}GB
              <span v-if="tierInfo(selectedTier).min_vram_gb">
                · 最低显存 {{ tierInfo(selectedTier).min_vram_gb }}GB
              </span>
            </p>
          </div>
          <el-button
            type="primary"
            :loading="switching"
            :disabled="selectedTier === currentTier"
            class="mt-20"
            @click="switchModel"
          >
            确认切换
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '@/api/client'

const loading = ref(false)
const switching = ref(false)
const modelStatus = ref({})
const currentTier = ref('L0')
const selectedTier = ref('L0')

const tiers = [
  { value: 'auto', label: 'auto 自动选择' },
  { value: 'L0', label: 'L0 云端大模型' },
  { value: 'L1', label: 'L1 边缘小模型' },
  { value: 'L2', label: 'L2 标准模型' },
  { value: 'L3', label: 'L3 旗舰模型' },
]

const tierMap = {
  auto: {
    description: '根据硬件自动选择最佳档位',
    model_name: '动态选择',
    provider_type: 'cloud',
  },
  L0: {
    description: '云端大模型，最强推理能力',
    model_name: '云端模型',
    provider_type: 'cloud',
  },
  L1: {
    description: '本地边缘小模型，纯文本摘要',
    model_name: '本地边缘模型',
    provider_type: 'local',
    min_vram_gb: 0,
    min_ram_gb: 4,
  },
  L2: {
    description: '本地标准模型，文本+表格分析',
    model_name: '本地标准模型',
    provider_type: 'local',
    min_vram_gb: 6,
    min_ram_gb: 12,
  },
  L3: {
    description: '本地旗舰模型，全模态深度推理',
    model_name: '本地旗舰模型',
    provider_type: 'local',
    min_vram_gb: 12,
    min_ram_gb: 24,
  },
}

function tierInfo(tier) {
  return tierMap[tier] || tierMap.L0
}

async function loadStatus() {
  loading.value = true
  try {
    const data = await adminApi.modelStatus()
    modelStatus.value = data
    currentTier.value = data.current_tier || data.recommended_tier || 'L0'
    selectedTier.value = currentTier.value
  } catch (err) {
    console.error('加载模型状态失败:', err)
    ElMessage.error('加载模型状态失败')
  } finally {
    loading.value = false
  }
}

async function switchModel() {
  try {
    await ElMessageBox.confirm(
      `确认将模型档位切换为 ${selectedTier.value}（${tierInfo(selectedTier.value).description}）？`,
      '切换确认',
      { confirmButtonText: '确认切换', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  switching.value = true
  try {
    await adminApi.switchModel(selectedTier.value)
    currentTier.value = selectedTier.value
    ElMessage.success(`已切换至 ${selectedTier.value}`)
    await loadStatus()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    switching.value = false
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.mt-20 {
  margin-top: 20px;
}
.tier-desc {
  margin-left: 8px;
  color: #606266;
  font-size: 13px;
}
.tier-radio-group {
  margin-bottom: 16px;
}
.tier-detail {
  padding: 12px;
  background-color: #f3f4f6;
  border-radius: 4px;
}
.tier-detail p {
  margin: 4px 0;
  color: #606266;
  font-size: 13px;
}
</style>
