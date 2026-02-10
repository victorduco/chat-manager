<template>
  <div class="thread-details">
    <div v-if="!threadId" class="empty-state">
      <h2>👈 Select a thread to view details</h2>
      <p>Choose a thread from the list to see users and messages</p>
    </div>

    <div v-else-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading thread data...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <h3>❌ Error loading thread</h3>
      <p>{{ error }}</p>
      <button @click="loadThreadState" class="retry-btn">🔄 Retry</button>
    </div>

    <div v-else-if="state" class="details-content">
      <!-- Thread Info Header -->
      <div class="thread-header">
        <div class="info-item">
          <label>Thread ID:</label>
          <code class="thread-id-full">{{ threadId }}</code>
        </div>
        <div class="info-item" v-if="state.created_at">
          <label>Created:</label>
          <span>{{ formatDateTime(state.created_at) }}</span>
        </div>
        <div class="info-item" v-if="state.updated_at">
          <label>Updated:</label>
          <span>{{ formatDateTime(state.updated_at) }}</span>
        </div>
      </div>

      <div class="header-actions">
        <div class="graph-config">
          <label class="graph-label">Graph:</label>
          <select
            class="graph-select"
            :disabled="graphBusy || !threadId"
            :value="dispatchGraphValue"
            @change="(e) => onChangeGraph(e.target.value)"
          >
            <option value="">Default (auto)</option>
            <option value="graph_supervisor">graph_supervisor</option>
            <option value="graph_router">graph_router</option>
            <option value="graph_chat_manager">graph_chat_manager</option>
          </select>
          <span v-if="graphBusy" class="graph-status">Saving...</span>
          <span v-else-if="graphError" class="graph-error">{{ graphError }}</span>
        </div>

        <button class="import-btn" @click="importOpen = !importOpen">
          {{ importOpen ? 'Hide' : 'Paste' }} YAML
        </button>
        <button class="delete-btn" :disabled="deleteBusy" @click="onDeleteThread">
          {{ deleteBusy ? 'Deleting...' : 'Delete Thread' }}
        </button>
        <span v-if="importStatus" class="import-status">{{ importStatus }}</span>
      </div>

      <div v-if="importOpen" class="import-panel">
        <div class="import-help">
          <div class="import-title">Import users from YAML</div>
          <div class="import-subtitle">
            Supported formats:
            <code>- username: ducov</code>
            <code>  first_name: Viktor</code>
            <code>  last_name: Dyukov</code>
            <code>  intro: true</code>
            or simple blocks:
            <code>Viktor Dyukov</code>
            <code>@ducov</code>
            <code>intro:true</code>
          </div>
        </div>

        <textarea
          v-model="importText"
          class="import-textarea"
          placeholder="Paste YAML here..."
          rows="8"
        />

        <div class="import-actions">
          <button class="import-apply" :disabled="importBusy || !threadId" @click="onImportYaml">
            {{ importBusy ? 'Importing...' : 'Add Users' }}
          </button>
          <button class="import-clear" :disabled="importBusy" @click="importText = ''">Clear</button>
          <span v-if="importError" class="import-error">{{ importError }}</span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          class="tab"
          :class="{ active: activeTab === 'users' }"
          @click="activeTab = 'users'"
        >
          👥 Users ({{ users.length }})
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'messages' }"
          @click="activeTab = 'messages'"
        >
          💬 Messages ({{ messages.length }})
        </button>
      </div>

      <!-- Users Tab -->
      <div v-show="activeTab === 'users'" class="tab-content">
        <div v-if="users.length === 0" class="no-data">
          No users found in this thread
        </div>

        <div v-else class="users-table-container">
          <table class="users-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Edit Intro</th>
                <th>Name</th>
                <th>Username</th>
                <th>Telegram ID</th>
                <th>Preferred Name</th>
                <th>Information</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(user, index) in users"
                :key="index"
                :class="{ 'intro-completed': user.intro_completed }"
              >
                <td class="status-cell">
                  <span class="status-badge" :class="{ completed: user.intro_completed }">
                    {{ user.intro_completed ? '✅ Done' : '❌ Pending' }}
                  </span>
                </td>
                <td class="edit-cell">
                  <select
                    class="intro-select"
                    :disabled="savingUserKey === userKey(user, index) || (!user.username && !user.telegram_id)"
                    :value="user.intro_completed ? 'done' : 'pending'"
                    @change="(e) => onChangeIntro(user, index, e.target.value)"
                  >
                    <option value="pending">Pending</option>
                    <option value="done">Done</option>
                  </select>
                  <span v-if="savingUserKey === userKey(user, index)" class="saving">Saving...</span>
                </td>
                <td class="name-cell">
                  {{ user.first_name }} {{ user.last_name || '' }}
                </td>
                <td class="username-cell">
                  @{{ user.username || 'N/A' }}
                </td>
                <td class="telegram-cell">
                  <code v-if="user.telegram_id">{{ user.telegram_id }}</code>
                  <span v-else class="na">N/A</span>
                </td>
                <td class="preferred-cell">
                  {{ user.preferred_name || '—' }}
                </td>
                <td class="info-cell">
                  <span v-if="!user.information || Object.keys(user.information).length === 0" class="na">—</span>
                  <pre v-else class="info-json">{{ JSON.stringify(user.information, null, 2) }}</pre>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Messages Tab -->
      <div v-show="activeTab === 'messages'" class="tab-content">
        <div v-if="messages.length === 0" class="no-data">
          No messages found in this thread
        </div>

        <div v-else class="messages-container">
          <div
            v-for="(message, index) in messages"
            :key="index"
            class="message"
            :class="message.type"
          >
            <div class="message-header">
              <span class="message-type">{{ message.type }}</span>
              <span class="message-name" v-if="message.name">{{ message.name }}</span>
            </div>
            <div class="message-content">
              {{ message.content }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { getThreadState, getThread, setThreadMetadata, setIntroStatus, upsertUsers, deleteThread, mergeThreadMetadata } from '../services/api'
import YAML from 'js-yaml'

const props = defineProps({
  threadId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['thread-deleted'])

const state = ref(null)
const loading = ref(false)
const error = ref(null)
const activeTab = ref('users')
const savingUserKey = ref(null)
const importOpen = ref(false)
const importText = ref('')
const importError = ref('')
const importStatus = ref('')
const importBusy = ref(false)
const deleteBusy = ref(false)
const threadInfo = ref(null)
const graphBusy = ref(false)
const graphError = ref('')

const dispatchGraphValue = computed(() => {
  const meta = threadInfo.value?.metadata
  const v = meta && typeof meta === 'object' ? meta.dispatch_graph_id : null
  return (typeof v === 'string') ? v : (v == null ? '' : String(v))
})

const users = computed(() => {
  if (!state.value?.values?.users) return []
  return state.value.values.users
})

const messages = computed(() => {
  if (!state.value?.values?.messages) return []
  return state.value.values.messages
})

async function loadThreadState() {
  if (!props.threadId) return

  loading.value = true
  error.value = null
  state.value = null

  try {
    state.value = await getThreadState(props.threadId)
    // Best-effort: metadata for graph routing lives on /threads/:id, not /state.
    try {
      threadInfo.value = await getThread(props.threadId)
    } catch (_) {
      threadInfo.value = null
    }
  } catch (err) {
    error.value = err.message || 'Failed to load thread state'
    console.error('Load thread state error:', err)
  } finally {
    loading.value = false
  }
}

async function onChangeGraph(value) {
  if (!props.threadId) return
  graphError.value = ''

  // Empty string means "unset" -> clear key to fall back to default behavior.
  const next = String(value || '').trim()

  graphBusy.value = true
  try {
    if (next) {
      await mergeThreadMetadata(props.threadId, { dispatch_graph_id: next })
    } else {
      // Clear the key entirely (avoid leaving nulls around).
      const t = await getThread(props.threadId)
      const current = (t && t.metadata && typeof t.metadata === 'object') ? { ...t.metadata } : {}
      delete current.dispatch_graph_id
      await setThreadMetadata(props.threadId, current)
    }
    threadInfo.value = await getThread(props.threadId)
  } catch (e) {
    graphError.value = e?.message || 'Failed to save graph'
  } finally {
    graphBusy.value = false
  }
}

function splitName(fullName) {
  const s = (fullName || '').trim().replace(/\s+/g, ' ')
  if (!s) return { first_name: '', last_name: null }
  const parts = s.split(' ')
  if (parts.length === 1) return { first_name: parts[0], last_name: null }
  return { first_name: parts[0], last_name: parts.slice(1).join(' ') }
}

function normalizeIntro(v) {
  if (typeof v === 'boolean') return v
  const t = String(v ?? '').trim().toLowerCase()
  if (['true', 'yes', 'y', '1', 'done', 'completed', 'complete', 'on'].includes(t)) return true
  if (['false', 'no', 'n', '0', 'pending', 'off', 'not_done', 'notdone'].includes(t)) return false
  return null
}

function parseSimpleBlocks(text) {
  const blocks = String(text || '')
    .trim()
    .split(/\n\s*\n+/g)
    .map((b) => b.trim())
    .filter(Boolean)

  const out = []
  for (const b of blocks) {
    const lines = b.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lines.length < 2) continue
    const fullName = lines[0]
    const usernameLine = lines[1]
    const username = usernameLine.startsWith('@') ? usernameLine.slice(1).trim() : usernameLine.trim()
    const introLine = lines.find((l) => l.toLowerCase().startsWith('intro'))
    let introVal = null
    if (introLine) {
      const m = introLine.split(':', 2)
      introVal = normalizeIntro(m.length === 2 ? m[1] : '')
    }
    const { first_name, last_name } = splitName(fullName)
    out.push({
      username,
      first_name: first_name || username,
      last_name,
      intro_completed: introVal === true
    })
  }
  return out
}

function parseUsersYaml(text) {
  const raw = String(text || '').trim()
  if (!raw) return []

  try {
    const doc = YAML.load(raw)
    let arr = null
    if (Array.isArray(doc)) arr = doc
    else if (doc && typeof doc === 'object' && Array.isArray(doc.users)) arr = doc.users

    if (arr) {
      return arr
        .filter((u) => u && typeof u === 'object')
        .map((u) => {
          const username = String(u.username || u.user || u.handle || '').trim().replace(/^@/, '')
          const intro = normalizeIntro(u.intro ?? u.intro_completed ?? u.introCompleted)
          let first_name = String(u.first_name || u.firstName || '').trim()
          let last_name = u.last_name ?? u.lastName ?? null

          if (!first_name && (u.name || u.full_name || u.fullName)) {
            const split = splitName(String(u.name || u.full_name || u.fullName))
            first_name = split.first_name
            last_name = last_name ?? split.last_name
          }

          return {
            username,
            first_name: first_name || username,
            last_name: last_name != null ? String(last_name) : null,
            telegram_id: u.telegram_id ?? u.telegramId ?? null,
            preferred_name: u.preferred_name ?? u.preferredName ?? null,
            information: (u.information && typeof u.information === 'object') ? u.information : {},
            intro_completed: intro === true
          }
        })
    }
  } catch (_) {
    // fall through
  }

  return parseSimpleBlocks(raw)
}

async function onImportYaml() {
  if (!props.threadId) {
    importError.value = 'Select a thread first.'
    return
  }

  importError.value = ''
  importStatus.value = ''

  let usersToUpsert = parseUsersYaml(importText.value)
  usersToUpsert = usersToUpsert.filter((u) => u && u.username)

  if (usersToUpsert.length === 0) {
    importError.value = 'No users found. Provide at least one username.'
    return
  }

  importBusy.value = true
  try {
    await upsertUsers(props.threadId, usersToUpsert)
    importStatus.value = `Imported ${usersToUpsert.length} user(s)`
    await loadThreadState()
  } catch (e) {
    importError.value = e?.message || 'Import failed'
    try { await loadThreadState() } catch (_) {}
  } finally {
    importBusy.value = false
  }
}

async function onDeleteThread() {
  if (!props.threadId) return
  if (deleteBusy.value) return

  const ok = window.confirm(`Delete thread ${props.threadId}?\n\nThis cannot be undone.`)
  if (!ok) return

  deleteBusy.value = true
  error.value = null
  importStatus.value = ''
  importError.value = ''

  try {
    await deleteThread(props.threadId)
    emit('thread-deleted', props.threadId)
  } catch (e) {
    error.value = e?.message || 'Failed to delete thread'
  } finally {
    deleteBusy.value = false
  }
}

function userKey(user, index) {
  if (user?.username) return `u:${user.username}`
  if (user?.telegram_id != null) return `t:${user.telegram_id}`
  return `i:${index}`
}

async function onChangeIntro(user, index, value) {
  if (!props.threadId) return
  const introCompleted = value === 'done'
  const key = userKey(user, index)

  savingUserKey.value = key
  error.value = null

  try {
    await setIntroStatus(props.threadId, {
      username: user.username || null,
      telegramId: user.telegram_id ?? null,
      introCompleted
    })
    await loadThreadState()
  } catch (err) {
    error.value = err.message || 'Failed to update intro status'
    console.error('Set intro status error:', err)
    try { await loadThreadState() } catch (_) {}
  } finally {
    savingUserKey.value = null
  }
}

function formatDateTime(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function truncateId(id) {
  if (!id) return ''
  return id.length > 12 ? `${id.slice(0, 8)}...${id.slice(-4)}` : id
}

watch(() => props.threadId, (newId) => {
  if (newId) {
    loadThreadState()
  }
}, { immediate: true })
</script>

<style scoped>
.thread-details {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;
}

.thread-id-full {
  word-break: break-all;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem 0.75rem 1rem;
  flex-wrap: wrap;
}

.graph-config {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.graph-label {
  font-weight: 700;
  color: #212529;
}

.graph-select {
  border: 1px solid #ced4da;
  background: white;
  color: #212529;
  padding: 0.35rem 0.55rem;
  border-radius: 6px;
  font-weight: 600;
}

.graph-status {
  color: #495057;
  font-size: 0.9rem;
}

.graph-error {
  color: #c92a2a;
  font-size: 0.9rem;
}

.import-btn {
  border: 1px solid #ced4da;
  background: white;
  color: #212529;
  padding: 0.4rem 0.7rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.import-btn:hover {
  background: #f1f3f5;
}

.delete-btn {
  border: 1px solid #fa5252;
  background: #fff5f5;
  color: #c92a2a;
  padding: 0.4rem 0.7rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
}

.delete-btn:hover {
  background: #ffe3e3;
}

.delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.import-status {
  color: #2b8a3e;
  font-size: 0.9rem;
}

.import-panel {
  padding: 0 1rem 1rem 1rem;
  border-bottom: 1px solid #e9ecef;
  background: #ffffff;
}

.import-help {
  margin-bottom: 0.75rem;
}

.import-title {
  font-weight: 700;
  color: #212529;
  margin-bottom: 0.25rem;
}

.import-subtitle {
  color: #6c757d;
  font-size: 0.9rem;
  line-height: 1.3;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.import-subtitle code {
  background: #f1f3f5;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.import-textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid #ced4da;
  border-radius: 8px;
  padding: 0.75rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.9rem;
  line-height: 1.35;
  outline: none;
}

.import-textarea:focus {
  border-color: #748ffc;
  box-shadow: 0 0 0 3px rgba(116, 143, 252, 0.18);
}

.import-actions {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.import-apply {
  border: 1px solid #4263eb;
  background: #4263eb;
  color: white;
  padding: 0.45rem 0.8rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.import-apply:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.import-clear {
  border: 1px solid #ced4da;
  background: white;
  color: #212529;
  padding: 0.45rem 0.8rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}

.import-error {
  color: #c92a2a;
  font-size: 0.9rem;
}

.empty-state,
.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
  color: #6c757d;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-state {
  color: #dc3545;
}

.retry-btn {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.details-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Thread Header */
.thread-header {
  padding: 1rem 1.5rem;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
  display: flex;
  gap: 2rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-item label {
  font-size: 0.75rem;
  color: #6c757d;
  font-weight: 600;
  text-transform: uppercase;
}

.info-item code {
  padding: 0.25rem 0.5rem;
  background: white;
  border-radius: 4px;
  font-size: 0.875rem;
  font-family: monospace;
}

.info-item span {
  font-size: 0.875rem;
  color: #212529;
}

/* Tabs */
.tabs {
  display: flex;
  border-bottom: 2px solid #dee2e6;
  background: white;
}

.tab {
  padding: 1rem 1.5rem;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #6c757d;
  transition: all 0.2s;
}

.tab:hover {
  color: #007bff;
  background: #f8f9fa;
}

.tab.active {
  color: #007bff;
  border-bottom-color: #007bff;
}

/* Tab Content */
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.no-data {
  padding: 3rem;
  text-align: center;
  color: #6c757d;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 1rem;
}

/* Users Table */
.users-table-container {
  overflow-x: auto;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.users-table thead {
  background: #f8f9fa;
  position: sticky;
  top: 0;
  z-index: 1;
}

.users-table th {
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #495057;
  border-bottom: 2px solid #dee2e6;
  font-size: 0.8125rem;
  text-transform: uppercase;
}

.users-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e9ecef;
  vertical-align: top;
}

.users-table tbody tr {
  transition: background-color 0.2s;
}

.users-table tbody tr:hover {
  background: #f8f9fa;
}

.users-table tbody tr.intro-completed {
  background: #f0fff4;
}

.users-table tbody tr:not(.intro-completed) {
  background: #fff5f5;
}

.status-cell {
  width: 120px;
}

.edit-cell {
  width: 180px;
  white-space: nowrap;
}

.intro-select {
  padding: 0.35rem 0.5rem;
  border: 1px solid #ced4da;
  border-radius: 4px;
  background: white;
  font-size: 0.875rem;
}

.saving {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}

.status-badge.completed {
  background: #d4edda;
  color: #155724;
}

.status-badge:not(.completed) {
  background: #f8d7da;
  color: #721c24;
}

.name-cell {
  font-weight: 600;
  color: #212529;
  min-width: 150px;
}

.username-cell {
  color: #6c757d;
  font-family: monospace;
  min-width: 120px;
}

.telegram-cell code {
  padding: 0.125rem 0.375rem;
  background: #f8f9fa;
  border-radius: 3px;
  font-size: 0.8125rem;
}

.telegram-cell .na,
.preferred-cell .na,
.info-cell .na {
  color: #adb5bd;
  font-style: italic;
}

.info-json {
  padding: 0.5rem;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 0.75rem;
  margin: 0;
  max-width: 300px;
  overflow-x: auto;
}

/* Messages */
.messages-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  padding: 0.75rem;
  border-radius: 6px;
  border-left: 4px solid;
}

.message.human {
  background: #e7f3ff;
  border-left-color: #007bff;
}

.message.ai {
  background: #f0f9ff;
  border-left-color: #0dcaf0;
}

.message.system {
  background: #f8f9fa;
  border-left-color: #6c757d;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.message-type {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: #6c757d;
}

.message-name {
  font-size: 0.75rem;
  color: #6c757d;
  font-family: monospace;
}

.message-content {
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
