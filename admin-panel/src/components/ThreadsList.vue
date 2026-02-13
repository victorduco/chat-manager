<template>
  <div class="threads-list">
    <div class="stats">
      <span>Total threads: {{ threads.length }}</span>
      <button @click="loadThreads" class="refresh-btn">🔄 Refresh</button>
      <span v-if="loading">Loading...</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>

    <div class="threads-container">
      <div
        v-for="thread in threads"
        :key="thread.thread_id"
        class="thread-card"
        :class="{ active: selectedThreadIdLocal === thread.thread_id }"
        @click="selectThread(thread.thread_id)"
      >
        <div class="thread-header">
          <span class="thread-title">{{ displayName(thread.thread_id) }}</span>
          <span class="thread-status" :class="thread.status">
            {{ thread.status || 'unknown' }}
          </span>
        </div>
        <div class="thread-meta">
          <div v-if="thread.updated_at" class="meta-item">
            Updated: {{ formatDate(thread.updated_at) }}
          </div>
        </div>
        <div class="thread-counts">
          <span class="count-chip">
            👥 Users: {{ countValue(thread.thread_id, 'users') }}
          </span>
          <span class="count-chip">
            💬 Messages: {{ countValue(thread.thread_id, 'messages') }}
          </span>
          <span class="count-chip">
            🧠 Records: {{ countValue(thread.thread_id, 'records') }}
          </span>
          <span class="count-chip">
            ⭐ Highlights: {{ countValue(thread.thread_id, 'highlights') }}
          </span>
        </div>
      </div>

      <div v-if="!loading && threads.length === 0" class="empty-state">
        No threads found
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { searchThreads, getThread } from '../services/api'

const props = defineProps({
  selectedThreadId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['thread-selected'])

const threads = ref([])
const selectedThreadIdLocal = ref(null)
const loading = ref(false)
const error = ref(null)
const extrasById = ref({})
const LIMIT = 100
const AUTO_REFRESH_MS = 5000
let refreshTimer = null

function extra(threadId) {
  return extrasById.value[threadId] || null
}

function displayName(threadId) {
  const x = extra(threadId)
  if (x?.chat_title) return String(x.chat_title)
  if (x?.chat_id) return `Chat ${x.chat_id}`
  return truncateId(threadId)
}

function countValue(threadId, key) {
  const x = extra(threadId)
  if (!x || x[key] == null) return '—'
  return x[key]
}

async function loadThreads({ silent = false } = {}) {
  if (!silent) {
    loading.value = true
    error.value = null
  }

  try {
    const base = await searchThreads({ limit: LIMIT })
    const sorted = (Array.isArray(base) ? base.slice() : []).sort((a, b) => {
      const ta = Date.parse(a?.updated_at || a?.created_at || '') || 0
      const tb = Date.parse(b?.updated_at || b?.created_at || '') || 0
      return tb - ta
    })
    threads.value = sorted
    // Best-effort enrichment: show message/user counts without blocking the list.
    enrichThreads(sorted)
  } catch (err) {
    if (!silent) {
      error.value = err.message || 'Failed to load threads'
    }
    console.error('Load threads error:', err)
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function pLimit(concurrency) {
  let active = 0
  const queue = []
  const next = () => {
    if (active >= concurrency) return
    const item = queue.shift()
    if (!item) return
    active++
    Promise.resolve()
      .then(item.fn)
      .then(item.resolve, item.reject)
      .finally(() => {
        active--
        next()
      })
  }
  return (fn) =>
    new Promise((resolve, reject) => {
      queue.push({ fn, resolve, reject })
      next()
    })
}

async function enrichThreads(list) {
  const limit = pLimit(8)
  const ids = (list || []).map((t) => t.thread_id).filter(Boolean)

  await Promise.all(ids.map((id) => limit(async () => {
    try {
      const t = await getThread(id)
      const values = (t && t.values) || {}
      const metadata = (t && t.metadata && typeof t.metadata === 'object') ? t.metadata : {}
      const messages = Array.isArray(values.messages) ? values.messages.length : null
      const users = Array.isArray(values.users) ? values.users.length : null
      const records = Array.isArray(values.memory_records) ? values.memory_records.length : null
      const highlights = Array.isArray(values.highlights) ? values.highlights.length : null

      extrasById.value = {
        ...extrasById.value,
        [id]: {
          messages,
          users,
          records,
          highlights,
          chat_title: metadata.chat_title || null,
          chat_id: metadata.chat_id || null,
        }
      }
    } catch (_) {
      // Ignore enrichment errors.
    }
  })))
}

function selectThread(threadId) {
  selectedThreadIdLocal.value = threadId
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
  selectedThreadIdLocal.value = props.selectedThreadId || null
  loadThreads()
  refreshTimer = window.setInterval(() => {
    if (document.hidden) return
    loadThreads({ silent: true })
  }, AUTO_REFRESH_MS)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})

watch(() => props.selectedThreadId, (v) => {
  selectedThreadIdLocal.value = v || null
})

defineExpose({ loadThreads })
</script>

<style scoped>
.threads-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  font-family: Manrope, "IBM Plex Sans", "SF Pro Text", "Segoe UI", sans-serif;
}

.refresh-btn {
  padding: 0.4rem 0.66rem;
  background: #0284c7;
  color: #fff;
  border: 1px solid #0284c7;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.76rem;
  font-weight: 600;
}

.refresh-btn:hover {
  background: #0369a1;
}

.stats {
  padding: 0.75rem 1rem;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.82rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.stats .error {
  color: #dc3545;
}

.threads-container {
  flex: 1;
  overflow-y: auto;
  padding: 0.6rem;
}

.thread-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0.72rem;
  margin-bottom: 0.55rem;
  cursor: pointer;
  transition: all 0.18s;
}

.thread-card:hover {
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  border-color: #7dd3fc;
}

.thread-card.active {
  border-color: #38bdf8;
  background: #f0f9ff;
}

.thread-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.thread-title {
  max-width: 230px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.86rem;
  color: #0f172a;
  font-weight: 600;
}

.thread-status {
  padding: 0.14rem 0.52rem;
  border-radius: 999px;
  font-size: 0.68rem;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.04em;
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
  font-size: 0.72rem;
  color: #64748b;
}

.thread-counts {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}

.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  color: #334155;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 0.18rem 0.52rem;
  border-radius: 999px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: #64748b;
}
</style>
