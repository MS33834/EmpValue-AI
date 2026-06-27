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
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          echarts: ['echarts', 'vue-echarts'],
          vuecore: ['vue', 'vue-router', 'pinia'],
        },
      },
    },
    // 拆分后单 chunk 仍超 500KB 时才告警，避免噪音
    chunkSizeWarningLimit: 600,
  },
})
