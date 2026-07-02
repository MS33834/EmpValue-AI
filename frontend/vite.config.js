import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    // 代码分割：将体积较大的第三方库拆分为独立 chunk，避免主包过大
    rollupOptions: {
      output: {
        manualChunks: {
          // Vue 核心运行时：vue + 路由 + 状态管理，独立成可长期缓存的 vendor chunk
          'vue-core': ['vue', 'vue-router', 'pinia'],
          // Element Plus 全家桶：组件库 + 图标，单独拆分避免污染业务代码
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          // ECharts 图表库 + Vue 封装层，体积较大单独拆分
          echarts: ['echarts', 'vue-echarts'],
        },
      },
    },
    // 拆分后单 chunk 仍超 500KB 时才告警，避免噪音
    chunkSizeWarningLimit: 600,
  },
})
