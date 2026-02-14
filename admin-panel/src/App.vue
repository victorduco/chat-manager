<template>
  <div id="app">
    <header class="app-header">
      <div class="header-content">
        <h1>Admin Panel</h1>
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
      </div>
    </header>

    <main class="app-main">
      <aside class="sidebar">
        <ThreadsList
          ref="threadsListRef"
          :selected-thread-id="selectedThreadId"
          @thread-selected="handleThreadSelected"
        />
      </aside>

      <section class="content">
        <ThreadDetails
          :thread-id="selectedThreadId"
          :initial-tab="selectedTab"
          @thread-deleted="handleThreadDeleted"
          @tab-changed="handleTabChanged"
        />
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import ThreadsList from './components/ThreadsList.vue'
import ThreadDetails from './components/ThreadDetails.vue'
import { getCurrentEnvironment, setEnvironment } from './services/api'

const VALID_ENVS = new Set(['dev', 'prod'])
const VALID_TABS = new Set(['users', 'messages', 'records', 'highlights', 'improvements', 'thread_info'])

const currentEnv = ref(getCurrentEnvironment())
const selectedThreadId = ref(null)
const selectedTab = ref('users')
const threadsListRef = ref(null)

function handleThreadSelected(threadId) {
  selectedThreadId.value = threadId
}

function handleTabChanged(tab) {
  if (VALID_TABS.has(tab)) {
    selectedTab.value = tab
  }
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
  if (!VALID_ENVS.has(env)) return
  setEnvironment(env)
  currentEnv.value = env

  // Reload threads for selected environment.
  try {
    threadsListRef.value?.loadThreads?.()
  } catch (_) {}
}

function getUrlState() {
  const params = new URLSearchParams(window.location.search)
  const env = params.get('env')
  const thread = params.get('thread')
  const tab = params.get('tab')
  return {
    env: VALID_ENVS.has(String(env || '')) ? String(env) : null,
    thread: thread ? String(thread) : null,
    tab: VALID_TABS.has(String(tab || '')) ? String(tab) : null,
  }
}

function syncStateToUrl() {
  const params = new URLSearchParams(window.location.search)
  params.set('env', currentEnv.value)

  if (selectedThreadId.value) params.set('thread', selectedThreadId.value)
  else params.delete('thread')

  if (selectedTab.value) params.set('tab', selectedTab.value)
  else params.delete('tab')

  const next = `${window.location.pathname}?${params.toString()}`
  window.history.replaceState({}, '', next)
}

// Listen for environment changes from other tabs/windows
function handleEnvChange(event) {
  currentEnv.value = event.detail
}

onMounted(() => {
  window.addEventListener('api-environment-changed', handleEnvChange)
  const urlState = getUrlState()
  if (urlState.env && urlState.env !== currentEnv.value) {
    setEnvironment(urlState.env)
    currentEnv.value = urlState.env
  }
  if (urlState.thread) {
    selectedThreadId.value = urlState.thread
  }
  if (urlState.tab) {
    selectedTab.value = urlState.tab
  }
  syncStateToUrl()
})

onUnmounted(() => {
  window.removeEventListener('api-environment-changed', handleEnvChange)
})

watch([currentEnv, selectedThreadId, selectedTab], () => {
  syncStateToUrl()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: Manrope, "IBM Plex Sans", "SF Pro Text", "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #0f172a;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.app-header {
  background: #0f172a;
  color: #ffffff;
  padding: 0.9rem 1.25rem;
  border-bottom: 1px solid #1e293b;
  box-shadow: 0 2px 8px rgba(2, 6, 23, 0.35);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app-header h1 {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  color: #ffffff;
}

.env-toggle {
  display: flex;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.12);
  padding: 0.25rem;
  border-radius: 10px;
}

.env-btn {
  background: transparent;
  border: 1px solid transparent;
  color: #e2e8f0;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.42rem 0.82rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.9;
}

.env-btn:hover {
  background: rgba(255, 255, 255, 0.18);
}

.env-btn.active {
  background: #ffffff;
  color: #0f172a;
  border-color: #ffffff;
  opacity: 1;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.app-main {
  flex: 1;
  display: grid;
  grid-template-columns: 350px 1fr;
  overflow: hidden;
}

.sidebar {
  background: #f8fafc;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e2e8f0;
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

  .env-btn {
    font-size: 0.75rem;
    padding: 0.4rem 0.8rem;
  }
}
</style>
