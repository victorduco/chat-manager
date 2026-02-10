<template>
  <div class="threads-list">
    <div class="filters">
      <h3>Filters</h3>
      <div class="filter-group">
        <label>Status:</label>
        <select v-model="filters.status" @change="loadThreads">
          <option value="">All</option>
          <option value="idle">Idle</option>
          <option value="busy">Busy</option>
          <option value="interrupted">Interrupted</option>
          <option value="error">Error</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Limit:</label>
        <input
          type="number"
          v-model.number="filters.limit"
          @change="loadThreads"
          min="1"
          max="500"
        />
      </div>
      <button @click="loadThreads" class="refresh-btn">🔄 Refresh</button>
    </div>

    <div class="stats">
      <span>Total threads: {{ threads.length }}</span>
      <span v-if="loading">Loading...</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>

    <div class="threads-container">
      <div
        v-for="thread in threads"
        :key="thread.thread_id"
        class="thread-card"
        :class="{ active: selectedThreadId === thread.thread_id }"
        @click="selectThread(thread.thread_id)"
      >
        <div class="thread-header">
          <span class="thread-id">{{ truncateId(thread.thread_id) }}</span>
          <span class="thread-status" :class="thread.status">
            {{ thread.status || 'unknown' }}
          </span>
        </div>
        <div class="thread-meta">
          <div v-if="thread.created_at" class="meta-item">
            📅 {{ formatDate(thread.created_at) }}
          </div>
          <div v-if="thread.updated_at" class="meta-item">
            🕒 {{ formatDate(thread.updated_at) }}
          </div>
        </div>
        <div v-if="thread.metadata && Object.keys(thread.metadata).length" class="thread-metadata">
          <small>{{ JSON.stringify(thread.metadata) }}</small>
        </div>
      </div>

      <div v-if="!loading && threads.length === 0" class="empty-state">
        No threads found
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { searchThreads } from '../services/api'

const emit = defineEmits(['thread-selected'])

const threads = ref([])
const selectedThreadId = ref(null)
const loading = ref(false)
const error = ref(null)

const filters = ref({
  status: '',
  limit: 100
})

async function loadThreads() {
  loading.value = true
  error.value = null

  try {
    const params = {
      limit: filters.value.limit
    }
    if (filters.value.status) {
      params.status = filters.value.status
    }

    threads.value = await searchThreads(params)
  } catch (err) {
    error.value = err.message || 'Failed to load threads'
    console.error('Load threads error:', err)
  } finally {
    loading.value = false
  }
}

function selectThread(threadId) {
  selectedThreadId.value = threadId
  emit('thread-selected', threadId)
}

function truncateId(id) {
  if (!id) return ''
  return id.length > 12 ? `${id.slice(0, 8)}...${id.slice(-4)}` : id
}

function formatDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  loadThreads()
})

defineExpose({ loadThreads })
</script>

<style scoped>
.threads-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f8f9fa;
  border-right: 1px solid #dee2e6;
}

.filters {
  padding: 1rem;
  background: white;
  border-bottom: 1px solid #dee2e6;
}

.filters h3 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #495057;
}

.filter-group {
  margin-bottom: 0.75rem;
}

.filter-group label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.875rem;
  color: #6c757d;
}

.filter-group select,
.filter-group input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.875rem;
}

.refresh-btn {
  width: 100%;
  padding: 0.5rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.refresh-btn:hover {
  background: #0056b3;
}

.stats {
  padding: 0.75rem 1rem;
  background: #e9ecef;
  font-size: 0.875rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats .error {
  color: #dc3545;
}

.threads-container {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.thread-card {
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.thread-card:hover {
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  border-color: #007bff;
}

.thread-card.active {
  border-color: #007bff;
  background: #e7f3ff;
}

.thread-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.thread-id {
  font-family: monospace;
  font-size: 0.875rem;
  color: #495057;
  font-weight: 600;
}

.thread-status {
  padding: 0.125rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  text-transform: uppercase;
  font-weight: 600;
}

.thread-status.idle {
  background: #d4edda;
  color: #155724;
}

.thread-status.busy {
  background: #fff3cd;
  color: #856404;
}

.thread-status.interrupted {
  background: #f8d7da;
  color: #721c24;
}

.thread-status.error {
  background: #f8d7da;
  color: #721c24;
}

.thread-meta {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.meta-item {
  font-size: 0.75rem;
  color: #6c757d;
}

.thread-metadata {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #e9ecef;
}

.thread-metadata small {
  color: #6c757d;
  font-family: monospace;
  font-size: 0.75rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #6c757d;
}
</style>
