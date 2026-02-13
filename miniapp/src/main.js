import { createApp } from 'vue'
import App from './App.vue'

// Initialize Telegram WebApp
if (window.Telegram?.WebApp) {
  window.Telegram.WebApp.ready()
}

createApp(App).mount('#app')
