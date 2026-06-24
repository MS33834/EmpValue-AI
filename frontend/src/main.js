import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import {
  TrendCharts,
  Document,
  UserFilled,
  SwitchButton,
  Timer,
  ChatDotRound,
  View,
  DataAnalysis,
  Setting,
  Tickets,
} from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.component('TrendCharts', TrendCharts)
app.component('Document', Document)
app.component('UserFilled', UserFilled)
app.component('SwitchButton', SwitchButton)
app.component('Timer', Timer)
app.component('ChatDotRound', ChatDotRound)
app.component('View', View)
app.component('DataAnalysis', DataAnalysis)
app.component('Setting', Setting)
app.component('Tickets', Tickets)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
