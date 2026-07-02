<template>
  <!--
    全屏水印覆盖层：安全合规防截图溯源。
    - pointer-events: none 不阻挡页面交互
    - aria-hidden="true" 对辅助技术隐藏，不影响 WCAG 可访问性
    - 水印内容含用户标识 + 当前时间，防止简单截图去标识
  -->
  <div
    class="watermark-overlay"
    :style="{ backgroundImage: `url(${watermarkUrl})` }"
    aria-hidden="true"
  ></div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  // 水印文字，默认取当前用户 ID（无 ID 时取姓名）
  text: {
    type: String,
    default: '',
  },
  // 水印不透明度（0-1）
  opacity: {
    type: Number,
    default: 0.08,
  },
  // 水印旋转角度（度）
  rotate: {
    type: Number,
    default: -22,
  },
  // 水印平铺间距（像素）
  gap: {
    type: Number,
    default: 200,
  },
})

const auth = useAuthStore()

// 水印文字：优先使用传入 text，否则回退到当前用户 ID / 姓名
const watermarkText = computed(
  () => props.text || auth.userId || auth.name || 'EmpValue-AI'
)

const watermarkUrl = ref('')
let timer = null

// 数字补零，用于格式化时间
function pad(n) {
  return String(n).padStart(2, '0')
}

// 用 canvas 生成平铺水印纹理：用户标识 + 当前时间
function generate() {
  if (typeof document === 'undefined') return
  const now = new Date()
  const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
  const lines = [watermarkText.value, timeStr]
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  // 单块画布尺寸：留出旋转与多行文本空间
  const size = Math.max(props.gap, 180)
  canvas.width = size
  canvas.height = size
  ctx.clearRect(0, 0, size, size)
  ctx.font = '14px Arial, "PingFang SC", "Microsoft YaHei", sans-serif'
  ctx.fillStyle = `rgba(20, 20, 20, ${props.opacity})`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.translate(size / 2, size / 2)
  ctx.rotate((props.rotate * Math.PI) / 180)
  // 多行文本垂直居中绘制
  const lineHeight = 20
  const startY = -((lines.length - 1) * lineHeight) / 2
  lines.forEach((line, i) => {
    ctx.fillText(line, 0, startY + i * lineHeight)
  })
  watermarkUrl.value = canvas.toDataURL()
}

onMounted(() => {
  generate()
  // 每 60 秒刷新一次时间，保证水印时间贴近截图时刻
  timer = setInterval(generate, 60 * 1000)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})

// 文字或视觉参数变化时重新生成水印纹理
watch(
  [watermarkText, () => props.opacity, () => props.rotate, () => props.gap],
  generate
)
</script>

<style scoped>
.watermark-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 9999;
  pointer-events: none;
  background-repeat: repeat;
}
</style>
