import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
// 主题色覆盖：须在 Element Plus 样式之后引入，通过 CSS 变量统一主色调
import './styles/theme.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.config.errorHandler = (err, instance, info) => {
  console.error('全局错误:', err, info)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
