import { createPinia } from 'pinia'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import { permission } from './directives/permission'
import router from './router'
import './styles/index.scss'
import { useAppStore } from './stores/app'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// 全局指令
app.directive('permission', permission)

// 应用初始主题
useAppStore().applyTheme()

app.mount('#app')
