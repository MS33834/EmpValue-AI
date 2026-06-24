<template>
  <v-chart v-if="hasData" class="radar-chart" :option="option" autoresize />
  <el-empty v-else description="暂无维度数据" />
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([RadarChart, TitleComponent, TooltipComponent, RadarComponent, CanvasRenderer])

const props = defineProps({
  dimensions: {
    type: Array,
    default: () => [],
  },
  scores: {
    type: Array,
    default: () => [],
  },
})

const hasData = computed(() => {
  return props.dimensions.length > 0 && props.dimensions.length === props.scores.length
})

const option = computed(() => ({
  tooltip: {},
  radar: {
    indicator: props.dimensions.map((name) => ({ name, max: 100 })),
    radius: '65%',
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: props.scores,
          name: '能力雷达',
          areaStyle: { color: 'rgba(103, 194, 58, 0.3)' },
          lineStyle: { color: '#67c23a' },
          itemStyle: { color: '#67c23a' },
        },
      ],
    },
  ],
}))
</script>

<style scoped>
.radar-chart {
  width: 100%;
  height: 360px;
}
</style>
