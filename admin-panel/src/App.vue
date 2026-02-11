<template>
  <div id="app">
    <header class="app-header">
      <div class="header-content">
        <h1>🤖 LangGraph Admin Panel</h1>
        <div class="header-info">
          <div class="env-toggle">
            <button
              :class="['env-btn', { active: currentEnv === 'dev' }]"
              @click="switchEnvironment('dev')"
              title="Local development server"
            >
              🔧 DEV
            </button>
            <button
              :class="['env-btn', { active: currentEnv === 'prod' }]"
              @click="switchEnvironment('prod')"
              title="Production Heroku server"
            >
              🚀 PROD
            </button>
          </div>
          <span class="api-url" :title="apiUrl">{{ apiUrl }}</span>
        </div>
      </div>
    </header>

    <main class="app-main">
      <aside class="sidebar">
        <ThreadsList
          ref="threadsListRef"
          @thread-selected="handleThreadSelected"
        />
      </aside>

      <section class="content">
        <ThreadDetails :thread-id="selectedThreadId" @thread-deleted="handleThreadDeleted" />
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import ThreadsList from './components/ThreadsList.vue'
import ThreadDetails from './components/ThreadDetails.vue'
import { getCurrentEnvironment, setEnvironment, getCurrentApiUrl } from './services/api'

const currentEnv = ref(getCurrentEnvironment())
const apiUrl = ref(getCurrentApiUrl())
const selectedThreadId = ref(null)
const threadsListRef = ref(null)

function handleThreadSelected(threadId) {
  selectedThreadId.value = threadId
}

function handleThreadDeleted(threadId) {
  // Clear selection and refresh the list.
  if (selectedThreadId.value === threadId) {
    selectedThreadId.value = null
  }
  try {
    threadsListRef.value?.loadThreads?.()
  } catch (_) {}
}

function switchEnvironment(env) {
  setEnvironment(env)
  currentEnv.value = env
  apiUrl.value = getCurrentApiUrl()

  // Clear selection and reload threads
  selectedThreadId.value = null
  try {
    threadsListRef.value?.loadThreads?.()
  } catch (_) {}
}

// Listen for environment changes from other tabs/windows
function handleEnvChange(event) {
  currentEnv.value = event.detail
  apiUrl.value = getCurrentApiUrl()
}

onMounted(() => {
  window.addEventListener('api-environment-changed', handleEnvChange)
})

onUnmounted(() => {
  window.removeEventListener('api-environment-changed', handleEnvChange)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8f9fa;
}

.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.env-toggle {
  display: flex;
  gap: 0.5rem;
  background: rgba(255,255,255,0.15);
  padding: 0.25rem;
  border-radius: 6px;
}

.env-btn {
  background: transparent;
  border: none;
  color: white;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.7;
}

.env-btn:hover {
  opacity: 0.9;
  background: rgba(255,255,255,0.1);
}

.env-btn.active {
  background: rgba(255,255,255,0.3);
  opacity: 1;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.api-url {
  font-size: 0.875rem;
  opacity: 0.9;
  font-family: monospace;
  background: rgba(255,255,255,0.2);
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  flex: 1;
  display: grid;
  grid-template-columns: 350px 1fr;
  overflow: hidden;
}

.sidebar {
  background: #f8f9fa;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.content {
  background: white;
  overflow: hidden;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Responsive */
@media (max-width: 1024px) {
  .app-main {
    grid-template-columns: 300px 1fr;
  }
}

@media (max-width: 768px) {
  .app-main {
    grid-template-columns: 1fr;
  }

  .sidebar {
    display: none;
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .header-info {
    width: 100%;
    flex-wrap: wrap;
  }

  .api-url {
    max-width: 100%;
    font-size: 0.75rem;
  }

  .env-btn {
    font-size: 0.75rem;
    padding: 0.4rem 0.8rem;
  }
}
</style>
