<template>
  <div id="app">
    <header class="app-header">
      <div class="header-content">
        <h1>🤖 LangGraph Admin Panel</h1>
        <div class="header-info">
          <span class="api-url">{{ apiUrl }}</span>
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
        <ThreadDetails :thread-id="selectedThreadId" />
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ThreadsList from './components/ThreadsList.vue'
import ThreadDetails from './components/ThreadDetails.vue'

const apiUrl = import.meta.env.VITE_LANGGRAPH_API_URL || 'https://langgraph-server.herokuapp.com'
const selectedThreadId = ref(null)
const threadsListRef = ref(null)

function handleThreadSelected(threadId) {
  selectedThreadId.value = threadId
}
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

.api-url {
  font-size: 0.875rem;
  opacity: 0.9;
  font-family: monospace;
  background: rgba(255,255,255,0.2);
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
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
}
</style>
