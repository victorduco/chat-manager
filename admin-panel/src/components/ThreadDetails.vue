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
          <code>{{ truncateId(threadId) }}</code>
        </div>
        <div class="info-item" v-if="state.created_at">
          <label>Created:</label>
          <span>{{ formatDateTime(state.created_at) }}</span>
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
import { getThreadState, setIntroStatus } from '../services/api'

const props = defineProps({
  threadId: {
    type: String,
    default: null
  }
})

const state = ref(null)
const loading = ref(false)
const error = ref(null)
const activeTab = ref('users')
const savingUserKey = ref(null)

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
  } catch (err) {
    error.value = err.message || 'Failed to load thread state'
    console.error('Load thread state error:', err)
  } finally {
    loading.value = false
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
