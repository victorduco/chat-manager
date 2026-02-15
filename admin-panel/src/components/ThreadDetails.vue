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
        <div class="thread-header-top">
          <h2 class="thread-title">
            {{ chatTitle || 'Thread Details' }}
          </h2>
          <div class="header-popovers">
            <div class="popover-anchor">
              <button class="header-btn" @click="toggleInfoPopover">
                ℹ️ Info
              </button>
              <div v-if="infoPopoverOpen" class="popover-card">
                <div class="popover-title">Thread Info</div>
                <div class="popover-row">
                  <span class="popover-label">Thread ID</span>
                  <code class="popover-value code">{{ threadId }}</code>
                </div>
                <div class="popover-row">
                  <span class="popover-label">Telegram Chat ID</span>
                  <code class="popover-value code">{{ chatId || '—' }}</code>
                </div>
                <div class="popover-row">
                  <span class="popover-label">Created</span>
                  <span class="popover-value">{{ infoCreatedAt ? formatDateTime(infoCreatedAt) : '—' }}</span>
                </div>
                <div class="popover-row">
                  <span class="popover-label">Updated</span>
                  <span class="popover-value">{{ infoUpdatedAt ? formatDateTime(infoUpdatedAt) : '—' }}</span>
                </div>
              </div>
            </div>

            <div class="popover-anchor">
              <button class="header-btn" @click="toggleSettingsPopover">
                ⚙️ Settings
              </button>
              <div v-if="settingsPopoverOpen" class="popover-card settings-card">
                <div class="settings-grid">
                  <div class="settings-group settings-group-full">
                    <label class="graph-label">Graph</label>
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

                  <div class="settings-group">
                    <label class="daily-label">
                      <input
                        type="checkbox"
                        :disabled="dailyBusy || !threadId"
                        :checked="dailyRunnerEnabled"
                        @change="(e) => onToggleDailyRunner(e.target.checked)"
                      />
                      Daily runner
                    </label>
                    <span v-if="dailyBusy" class="daily-status">Saving...</span>
                    <span v-else-if="dailyError" class="daily-error">{{ dailyError }}</span>
                  </div>

                  <div class="settings-group">
                    <label class="daily-label">
                      <input
                        type="checkbox"
                        :disabled="introSettingBusy || !threadId"
                        :checked="requireIntroEnabled"
                        @change="(e) => onToggleRequireIntro(e.target.checked)"
                      />
                      Require intro
                    </label>
                    <span v-if="introSettingBusy" class="daily-status">Saving...</span>
                    <span v-else-if="introSettingError" class="daily-error">{{ introSettingError }}</span>
                  </div>
                </div>

                <div class="settings-buttons">
                  <button class="import-btn" @click="importOpen = !importOpen">
                    {{ importOpen ? 'Hide' : 'Paste' }} YAML
                  </button>
                  <button
                    class="delete-btn"
                    :disabled="deleteBusy || deleteBlockedByUsers"
                    :title="deleteBlockedByUsers ? 'Deletion is disabled for threads with more than 5 users.' : ''"
                    @click="onDeleteThread"
                  >
                    {{ deleteBusy ? 'Deleting...' : 'Delete Thread' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="importStatus" class="import-status-line">{{ importStatus }}</div>

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
        <button
          class="tab"
          :class="{ active: activeTab === 'records' }"
          @click="activeTab = 'records'"
        >
          🧠 Records ({{ memoryRecords.length }})
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'highlights' }"
          @click="activeTab = 'highlights'"
        >
          ⭐ Highlights ({{ highlights.length }})
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'improvements' }"
          @click="activeTab = 'improvements'"
        >
          🛠 Improvements ({{ improvements.length }})
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'thread_info' }"
          @click="activeTab = 'thread_info'"
        >
          📌 Thread Info ({{ threadInfoItems.length }})
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
                <th>Name</th>
                <th>Username</th>
                <th>Telegram ID</th>
                <th>Information</th>
                <th>Records</th>
                <th class="intro-header">Intro</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(user, index) in users"
                :key="index"
              >
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
                <td class="records-user-cell">
                  <div class="records-user-row">
                    <span class="records-count">{{ getUserInformationEntries(user).length }}</span>
                    <button
                      class="records-popover-btn"
                      type="button"
                      title="Show information"
                      @click.stop="toggleUserInfoPopover(user, index)"
                    >
                      🧾
                    </button>
                  </div>
                  <div v-if="userInfoPopoverKey === userKey(user, index)" class="user-records-popover">
                    <div class="user-records-title">Information</div>
                    <div v-if="getUserInformationEntries(user).length === 0" class="user-records-empty">No information</div>
                    <div v-else class="user-records-list">
                      <div v-for="(entry, entryIdx) in getUserInformationEntries(user)" :key="`${entry[0]}-${entryIdx}`" class="user-record-item">
                        <div class="user-record-meta">
                          <code>{{ entry[0] }}</code>
                        </div>
                        <div class="user-record-text">{{ entry[1] }}</div>
                      </div>
                    </div>
                  </div>
                </td>
                <td class="records-user-cell">
                  <div class="records-user-row">
                    <span class="records-count">{{ getUserRecords(user).length }}</span>
                    <button
                      class="records-popover-btn"
                      type="button"
                      title="Show records"
                      @click.stop="toggleUserRecordsPopover(user, index)"
                    >
                      🗂
                    </button>
                  </div>
                  <div v-if="userRecordsPopoverKey === userKey(user, index)" class="user-records-popover">
                    <div class="user-records-title">Records</div>
                    <div v-if="getUserRecords(user).length === 0" class="user-records-empty">No records</div>
                    <div v-else class="user-records-list">
                      <div v-for="(rec, recIdx) in getUserRecords(user)" :key="rec.id || recIdx" class="user-record-item">
                        <div class="user-record-meta">
                          <code>{{ rec.category || '—' }}</code>
                          <span>{{ formatDateTime(rec.created_at) || '—' }}</span>
                        </div>
                        <div class="user-record-text">{{ rec.text || '' }}</div>
                      </div>
                    </div>
                  </div>
                </td>
                <td class="intro-status-cell">
                  <div class="intro-status-row">
                    <span class="status-badge" :class="{ completed: user.intro_completed }">
                      {{ user.intro_completed ? '✅ Done' : `${pendingIcon} Pending (${user.messages_without_intro ?? 0})` }}
                    </span>
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
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Messages Tab -->
      <div v-show="activeTab === 'messages'" ref="messagesTabRef" class="tab-content">
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

      <!-- Records Tab -->
      <div v-show="activeTab === 'records'" class="tab-content">
        <div v-if="memoryRecords.length === 0" class="no-data">
          No records found in this thread
        </div>

        <div v-else class="records-container">
          <table class="records-table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Category</th>
                <th>Text</th>
                <th>From</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, index) in memoryRecords" :key="r.id || index">
                <td class="records-created">
                  {{ formatDateTime(r.created_at) }}
                </td>
                <td class="records-category">
                  <code>{{ r.category || '—' }}</code>
                </td>
                <td class="records-text">
                  {{ r.text || '' }}
                </td>
                <td class="records-from">
                  <span v-if="r.from_user?.username">@{{ r.from_user.username }}</span>
                  <span v-else class="na">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Highlights Tab -->
      <div v-show="activeTab === 'highlights'" class="tab-content">
        <div v-if="highlights.length === 0" class="no-data">
          No highlights found in this thread
        </div>

        <div v-else class="highlights-container">
          <table class="highlights-table">
            <thead>
              <tr>
                <th>Published</th>
                <th>Category</th>
                <th>Tags</th>
                <th>Highlight Description</th>
                <th>Message Text</th>
                <th>Highlight Link</th>
                <th>Author</th>
                <th>Expires</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, index) in highlights" :key="h.id || index">
                <td class="highlights-date">
                  {{ formatDateTime(h.published_at) }}
                </td>
                <td class="highlights-category">
                  <code>{{ h.category || '—' }}</code>
                </td>
                <td class="highlights-tags">
                  <span v-if="!h.tags || h.tags.length === 0" class="na">—</span>
                  <span v-else>{{ h.tags.join(', ') }}</span>
                </td>
                <td class="highlights-description">
                  {{ h.highlight_description || h.description || '' }}
                </td>
                <td class="highlights-text">
                  {{ h.message_text || '' }}
                </td>
                <td class="highlights-link">
                  <a v-if="isExternalLink(h.highlight_link || h.message_link)" :href="h.highlight_link || h.message_link" target="_blank" rel="noopener noreferrer">
                    Open highlight
                  </a>
                  <code v-else-if="h.highlight_link || h.message_link">{{ h.highlight_link || h.message_link }}</code>
                  <span v-else class="na">—</span>
                </td>
                <td class="highlights-author">
                  <span v-if="h.author_username">@{{ h.author_username }}</span>
                  <span v-else class="na">—</span>
                </td>
                <td class="highlights-expires">
                  <span v-if="h.expires_at">{{ formatDateTime(h.expires_at) }}</span>
                  <span v-else class="na">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Improvements Tab -->
      <div v-show="activeTab === 'improvements'" class="tab-content">
        <div v-if="improvements.length === 0" class="no-data">
          No improvements found in this thread
        </div>

        <div v-else class="improvements-container">
          <table class="improvements-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Created</th>
                <th>Category</th>
                <th>Status</th>
                <th>Reporter</th>
                <th>Resolution</th>
                <th>Closed At</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in improvements" :key="item.id || index">
                <td class="improvements-task">
                  <code>{{ item.task_number || '—' }}</code>
                </td>
                <td class="improvements-date">
                  {{ formatDateTime(item.created_at) }}
                </td>
                <td class="improvements-category">
                  <code>{{ item.category || '—' }}</code>
                </td>
                <td class="improvements-status">
                  <code>{{ item.status || '—' }}</code>
                </td>
                <td class="improvements-reporter">
                  <span v-if="item.reporter">{{ String(item.reporter) }}</span>
                  <span v-else class="na">—</span>
                </td>
                <td class="improvements-resolution">
                  <span v-if="item.resolution">{{ item.resolution }}</span>
                  <span v-else class="na">—</span>
                </td>
                <td class="improvements-date">
                  <span v-if="item.closed_at">{{ formatDateTime(item.closed_at) }}</span>
                  <span v-else class="na">—</span>
                </td>
                <td class="improvements-description">
                  {{ item.description || '' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Thread Info Tab -->
      <div v-show="activeTab === 'thread_info'" class="tab-content">
        <div class="thread-info-container">
          <table class="thread-info-table">
            <tbody>
              <tr>
                <th>Title</th>
                <td>{{ threadMetaTitle || '—' }}</td>
              </tr>
              <tr>
                <th>Username</th>
                <td>
                  <span v-if="threadMetaUsername">@{{ threadMetaUsername }}</span>
                  <span v-else class="na">—</span>
                </td>
              </tr>
              <tr>
                <th>Description</th>
                <td class="thread-info-multiline">{{ threadMetaDescription || '—' }}</td>
              </tr>
              <tr>
                <th>Pinned</th>
                <td class="thread-info-multiline">{{ threadMetaPinnedText || '—' }}</td>
              </tr>
            </tbody>
          </table>

          <div class="thread-info-list-block">
            <div class="thread-info-list-title">Thread Info Entries</div>
            <div v-if="threadInfoItems.length === 0" class="no-data">
              No thread info entries
            </div>
            <ol v-else class="thread-info-list">
              <li v-for="(item, index) in threadInfoItems" :key="`${index}-${item}`">
                {{ item }}
              </li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { getThreadState, getThread, setThreadMetadata, setIntroStatus, upsertUsers, deleteThread, mergeThreadMetadata } from '../services/api'
import YAML from 'js-yaml'

const props = defineProps({
  threadId: {
    type: String,
    default: null
  },
  initialTab: {
    type: String,
    default: 'users'
  }
})

const emit = defineEmits(['thread-deleted', 'tab-changed'])

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
const dailyBusy = ref(false)
const dailyError = ref('')
const introSettingBusy = ref(false)
const introSettingError = ref('')
const infoPopoverOpen = ref(false)
const settingsPopoverOpen = ref(false)
const userRecordsPopoverKey = ref(null)
const userInfoPopoverKey = ref(null)
const messagesTabRef = ref(null)
const VALID_TABS = new Set(['users', 'messages', 'records', 'highlights', 'improvements', 'thread_info'])
const AUTO_REFRESH_MS = 5000
let detailRefreshTimer = null

const dispatchGraphValue = computed(() => {
  const meta = threadInfo.value?.metadata
  const v = meta && typeof meta === 'object' ? meta.dispatch_graph_id : null
  return (typeof v === 'string') ? v : (v == null ? '' : String(v))
})

const dailyRunnerEnabled = computed(() => {
  const meta = threadInfo.value?.metadata
  const v = meta && typeof meta === 'object' ? meta.daily_runner_enabled : false
  return v === true
})

const requireIntroEnabled = computed(() => {
  const meta = threadInfo.value?.metadata
  const raw = meta && typeof meta === 'object' ? meta.require_intro : true
  if (raw === false) return false
  if (raw === true || raw == null) return true
  const v = String(raw).trim().toLowerCase()
  if (['false', '0', 'no', 'off'].includes(v)) return false
  if (['true', '1', 'yes', 'on'].includes(v)) return true
  return true
})

const users = computed(() => {
  if (!state.value?.values?.users) return []
  return state.value.values.users
})

const messages = computed(() => {
  if (!state.value?.values?.messages) return []
  return state.value.values.messages
})

const memoryRecords = computed(() => {
  const raw = state.value?.values?.memory_records
  const arr = Array.isArray(raw) ? raw.slice() : []
  // Most recent first (best-effort).
  arr.sort((a, b) => {
    const ta = Date.parse(a?.created_at || '') || 0
    const tb = Date.parse(b?.created_at || '') || 0
    return tb - ta
  })
  return arr
})

const highlights = computed(() => {
  const raw = state.value?.values?.highlights
  const arr = Array.isArray(raw) ? raw.slice() : []
  arr.sort((a, b) => {
    const ta = Date.parse(a?.published_at || '') || 0
    const tb = Date.parse(b?.published_at || '') || 0
    return tb - ta
  })
  return arr
})

const improvements = computed(() => {
  const raw = state.value?.values?.improvements
  const arr = Array.isArray(raw) ? raw.slice() : []
  arr.sort((a, b) => {
    const ta = Date.parse(a?.created_at || '') || 0
    const tb = Date.parse(b?.created_at || '') || 0
    return tb - ta
  })
  return arr
})

const threadMeta = computed(() => {
  const raw = threadInfo.value?.metadata
  return raw && typeof raw === 'object' ? raw : {}
})

const threadInfoItems = computed(() => {
  const raw = threadMeta.value?.thread_info
  if (!Array.isArray(raw)) return []
  return raw
    .map((x) => String(x ?? '').trim())
    .filter(Boolean)
})

const threadMetaTitle = computed(() => String(threadMeta.value?.chat_title || '').trim())
const threadMetaUsername = computed(() => String(threadMeta.value?.chat_username || '').trim().replace(/^@+/, ''))
const threadMetaDescription = computed(() => String(threadMeta.value?.chat_description || '').trim())
const threadMetaPinnedText = computed(() => {
  const pinned = threadMeta.value?.pinned_message
  if (!pinned || typeof pinned !== 'object') return ''
  const text = String(pinned.text || '').trim()
  if (text) return text
  const messageId = String(pinned.message_id || '').trim()
  return messageId ? `message_id=${messageId}` : ''
})

const deleteBlockedByUsers = computed(() => {
  return users.value.length > 5
})

const chatId = computed(() => {
  const meta = threadInfo.value?.metadata
  return meta && typeof meta === 'object' ? meta.chat_id : null
})

const chatTitle = computed(() => {
  const meta = threadInfo.value?.metadata
  return meta && typeof meta === 'object' ? meta.chat_title : null
})

const infoCreatedAt = computed(() => {
  return threadInfo.value?.created_at || state.value?.created_at || null
})

const infoUpdatedAt = computed(() => {
  return threadInfo.value?.updated_at || state.value?.updated_at || null
})

const pendingIcon = computed(() => {
  const icons = ['⏳', '🔄', '⏸️']
  const index = (props.threadId?.charCodeAt(0) || 0) % icons.length
  return icons[index]
})

async function loadThreadState({ silent = false } = {}) {
  if (!props.threadId) return

  if (!silent) {
    loading.value = true
    error.value = null
    state.value = null
  }

  try {
    state.value = await getThreadState(props.threadId)
    // Best-effort: metadata for graph routing lives on /threads/:id, not /state.
    try {
      threadInfo.value = await getThread(props.threadId)
    } catch (_) {
      if (!silent) {
        threadInfo.value = null
      }
    }
  } catch (err) {
    if (!silent) {
      error.value = err.message || 'Failed to load thread state'
    }
    console.error('Load thread state error:', err)
  } finally {
    if (!silent) {
      loading.value = false
    }
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

async function onToggleDailyRunner(enabled) {
  if (!props.threadId) return
  dailyError.value = ''

  dailyBusy.value = true
  try {
    await mergeThreadMetadata(props.threadId, { daily_runner_enabled: !!enabled })
    threadInfo.value = await getThread(props.threadId)
  } catch (e) {
    dailyError.value = e?.message || 'Failed to save daily runner setting'
  } finally {
    dailyBusy.value = false
  }
}

function toggleInfoPopover() {
  infoPopoverOpen.value = !infoPopoverOpen.value
  if (infoPopoverOpen.value) settingsPopoverOpen.value = false
}

function toggleSettingsPopover() {
  settingsPopoverOpen.value = !settingsPopoverOpen.value
  if (settingsPopoverOpen.value) infoPopoverOpen.value = false
}

async function onToggleRequireIntro(enabled) {
  if (!props.threadId) return
  introSettingError.value = ''

  introSettingBusy.value = true
  try {
    await mergeThreadMetadata(props.threadId, { require_intro: !!enabled })
    threadInfo.value = await getThread(props.threadId)
  } catch (e) {
    introSettingError.value = e?.message || 'Failed to save intro setting'
  } finally {
    introSettingBusy.value = false
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
  if (deleteBlockedByUsers.value) {
    error.value = 'Delete is disabled for threads with more than 5 users.'
    return
  }

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

function _norm(v) {
  return String(v ?? '').trim().toLowerCase()
}

function getUserRecords(user) {
  const items = memoryRecords.value || []
  const username = _norm(user?.username)
  const tgid = user?.telegram_id != null ? String(user.telegram_id) : null

  return items.filter((r) => {
    const from = r?.from_user || {}
    const rUsername = _norm(from?.username)
    const rTgid = from?.telegram_id != null ? String(from.telegram_id) : null

    if (username && rUsername && rUsername === username) return true
    if (tgid && rTgid && rTgid === tgid) return true
    return false
  })
}

function toggleUserRecordsPopover(user, index) {
  const key = userKey(user, index)
  userInfoPopoverKey.value = null
  userRecordsPopoverKey.value = (userRecordsPopoverKey.value === key) ? null : key
}

function getUserInformationEntries(user) {
  const info = user?.information
  if (!info || typeof info !== 'object') return []
  return Object.entries(info).filter(([k, v]) => String(k || '').trim() !== '' && String(v ?? '').trim() !== '')
}

function toggleUserInfoPopover(user, index) {
  const key = userKey(user, index)
  userRecordsPopoverKey.value = null
  userInfoPopoverKey.value = (userInfoPopoverKey.value === key) ? null : key
}

function handleGlobalPointerDown(event) {
  const target = event.target
  if (!(target instanceof Element)) return

  if (!target.closest('.popover-anchor')) {
    infoPopoverOpen.value = false
    settingsPopoverOpen.value = false
  }

  if (!target.closest('.records-user-cell')) {
    userRecordsPopoverKey.value = null
    userInfoPopoverKey.value = null
  }
}

async function scrollMessagesToBottom() {
  await nextTick()
  const el = messagesTabRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
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

function isExternalLink(link) {
  const v = String(link || '').trim().toLowerCase()
  return v.startsWith('http://') || v.startsWith('https://')
}

watch(() => props.threadId, (newId) => {
  if (newId) {
    infoPopoverOpen.value = false
    settingsPopoverOpen.value = false
    userRecordsPopoverKey.value = null
    userInfoPopoverKey.value = null
    loadThreadState()
  }
}, { immediate: true })

watch(() => props.initialTab, (tab) => {
  const next = String(tab || '').trim()
  if (VALID_TABS.has(next) && activeTab.value !== next) {
    activeTab.value = next
  }
}, { immediate: true })

watch(activeTab, (tab) => {
  if (VALID_TABS.has(tab)) {
    emit('tab-changed', tab)
  }
  if (tab === 'messages') {
    scrollMessagesToBottom()
  }
})

watch(() => messages.value.length, () => {
  if (activeTab.value === 'messages') {
    scrollMessagesToBottom()
  }
})

onMounted(() => {
  document.addEventListener('pointerdown', handleGlobalPointerDown)
  detailRefreshTimer = window.setInterval(() => {
    if (!props.threadId || document.hidden) return
    loadThreadState({ silent: true })
  }, AUTO_REFRESH_MS)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', handleGlobalPointerDown)
  if (detailRefreshTimer) {
    clearInterval(detailRefreshTimer)
    detailRefreshTimer = null
  }
})
</script>

<style scoped>
.thread-details {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  color: #0f172a;
  font-family: Manrope, "IBM Plex Sans", "SF Pro Text", "Segoe UI", sans-serif;
}

.records-container {
  padding: 0.75rem 1rem 1rem 1rem;
}

.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.records-table th,
.records-table td {
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  padding: 0.5rem 0.6rem;
  vertical-align: top;
}

.records-created {
  white-space: nowrap;
  color: #555;
  font-variant-numeric: tabular-nums;
}

.records-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.highlights-container {
  padding: 0.75rem 1rem 1rem 1rem;
}

.highlights-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.highlights-table th,
.highlights-table td {
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  padding: 0.5rem 0.6rem;
  vertical-align: top;
}

.highlights-date {
  white-space: nowrap;
  color: #555;
  font-variant-numeric: tabular-nums;
}

.highlights-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.improvements-container {
  padding: 0.75rem 1rem 1rem 1rem;
}

.improvements-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.improvements-table th,
.improvements-table td {
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  padding: 0.5rem 0.6rem;
  vertical-align: top;
}

.improvements-date {
  white-space: nowrap;
  color: #555;
  font-variant-numeric: tabular-nums;
}

.improvements-description {
  white-space: pre-wrap;
  word-break: break-word;
}

.thread-info-container {
  padding: 0.75rem 1rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.thread-info-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.thread-info-table th,
.thread-info-table td {
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  padding: 0.5rem 0.6rem;
  vertical-align: top;
}

.thread-info-table th {
  width: 170px;
  color: #475569;
  font-weight: 600;
}

.thread-info-multiline {
  white-space: pre-wrap;
  word-break: break-word;
}

.thread-info-list-block {
  border: 1px solid #edf2f7;
  border-radius: 10px;
  padding: 0.75rem;
  background: #fbfdff;
}

.thread-info-list-title {
  font-size: 0.85rem;
  color: #334155;
  margin-bottom: 0.5rem;
  font-weight: 700;
}

.thread-info-list {
  margin: 0;
  padding-left: 1.2rem;
}

.graph-label {
  font-size: 0.72rem;
  font-weight: 400;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.graph-select {
  border: 1px solid #d0d7e2;
  background: #fff;
  color: #212529;
  padding: 0.45rem 0.6rem;
  border-radius: 10px;
  font-weight: 600;
}

.graph-status {
  color: #64748b;
  font-size: 0.75rem;
}

.graph-error {
  color: #dc2626;
  font-size: 0.75rem;
}

.daily-label {
  font-size: 0.8rem;
  font-weight: 400;
  color: #0f172a;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  user-select: none;
}

.daily-label input {
  accent-color: #0284c7;
}

.daily-status {
  color: #64748b;
  font-size: 0.75rem;
}

.daily-error {
  color: #dc2626;
  font-size: 0.75rem;
}

.import-btn {
  border: 1px solid #d0d7e2;
  background: #fff;
  color: #212529;
  padding: 0.45rem 0.72rem;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
}

.import-btn:hover {
  background: #f1f3f5;
}

.delete-btn {
  border: 1px solid #fecaca;
  background: #fff7f7;
  color: #b91c1c;
  padding: 0.45rem 0.72rem;
  border-radius: 10px;
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

.import-status-line {
  color: #2b8a3e;
  font-size: 0.9rem;
  padding: 0.4rem 1.5rem 0.8rem 1.5rem;
}

.import-status {
  color: #2b8a3e;
  font-size: 0.9rem;
}

.import-panel {
  padding: 0 1rem 1rem 1rem;
  border-bottom: 1px solid #edf2f7;
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
  border: 1px solid #d0d7e2;
  border-radius: 12px;
  padding: 0.75rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.9rem;
  line-height: 1.35;
  outline: none;
}

.import-textarea:focus {
  border-color: #38bdf8;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
}

.import-actions {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.import-apply {
  border: 1px solid #0284c7;
  background: #0284c7;
  color: white;
  padding: 0.48rem 0.84rem;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 700;
}

.import-apply:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.import-clear {
  border: 1px solid #d0d7e2;
  background: #fff;
  color: #212529;
  padding: 0.48rem 0.84rem;
  border-radius: 10px;
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
  overflow: visible;
}

/* Thread Header */
.thread-header {
  padding: 1rem 1.5rem;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  position: relative;
  z-index: 40;
}

.thread-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0;
}

.thread-title {
  font-size: 1.2rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.header-popovers {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.popover-anchor {
  position: relative;
  z-index: 45;
}

.header-btn {
  border: 1px solid #d0d7e2;
  background: #fff;
  color: #0f172a;
  padding: 0.42rem 0.74rem;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
}

.header-btn:hover {
  background: #f1f3f5;
}

.popover-card {
  position: absolute;
  top: calc(100% + 0.45rem);
  right: 0;
  min-width: 320px;
  max-width: 420px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.12);
  padding: 0.8rem;
  z-index: 60;
}

.settings-card {
  min-width: 360px;
}

.popover-title {
  font-size: 0.82rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.popover-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
  border-bottom: 1px dashed #edf0f2;
  padding: 0.42rem 0;
}

.popover-row:last-child {
  border-bottom: none;
}

.popover-label {
  font-size: 0.8rem;
  color: #6c757d;
  font-weight: 600;
  white-space: nowrap;
}

.popover-value {
  font-size: 0.84rem;
  color: #212529;
  text-align: right;
  word-break: break-word;
}

.popover-value.code {
  font-family: monospace;
  background: #f8f9fa;
  border-radius: 4px;
  padding: 0.12rem 0.38rem;
}

.settings-group {
  margin-bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
  margin-bottom: 0.75rem;
}

.settings-group-full {
  grid-column: 1 / -1;
}

.settings-buttons {
  margin-top: 0;
  padding-top: 0.7rem;
  border-top: 1px solid #edf2f7;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.settings-buttons .import-btn,
.settings-buttons .delete-btn {
  flex: 1 1 0;
  font-weight: 500;
}

/* Tabs */
.tabs {
  display: flex;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
  padding: 0 1.25rem;
  position: relative;
  z-index: 2;
}

.tab {
  padding: 0.9rem 1.2rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  color: #6c757d;
  transition: all 0.2s;
}

.tab:hover {
  color: #0284c7;
  background: #f8fafc;
}

.tab.active {
  color: #0284c7;
  border-bottom-color: #0284c7;
}

/* Tab Content */
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  position: relative;
  z-index: 1;
}

.no-data {
  padding: 2.5rem;
  text-align: center;
  color: #6c757d;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  font-size: 0.95rem;
}

/* Users Table */
.users-table-container {
  overflow-x: auto;
  overflow-y: visible;
  position: relative;
}

.users-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.86rem;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: visible;
}

.users-table thead {
  background: #f8fafc;
  position: sticky;
  top: 0;
  z-index: 1;
}

.users-table th {
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.users-table th.intro-header {
  text-align: right;
  padding-right: 0.92rem;
}

.users-table td {
  padding: 0.72rem 0.92rem;
  border-bottom: 1px solid #edf2f7;
  vertical-align: top;
}

.users-table tbody tr {
  transition: background-color 0.2s;
}

.users-table tbody tr:hover {
  background: #f8fafc;
}

.users-table tbody tr:nth-child(odd) {
  background: #fff;
}

.users-table tbody tr:nth-child(even) {
  background: #f8fafc;
}

.intro-status-cell {
  min-width: 180px;
  white-space: nowrap;
  text-align: right;
  position: relative;
}

.intro-status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: nowrap;
  justify-content: flex-end;
}

.intro-select {
  padding: 0.28rem 0.42rem;
  border: 1px solid #d0d7e2;
  border-radius: 8px;
  background: #fff;
  font-size: 0.74rem;
  width: auto;
  min-width: 92px;
  margin-left: 0.25rem;
}

.saving {
  margin-left: 0.45rem;
  font-size: 0.7rem;
  color: #6c757d;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.2rem 0.62rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}

.status-badge.completed {
  background: #dcfce7;
  color: #166534;
}

.status-badge:not(.completed) {
  background: #fee2e2;
  color: #991b1b;
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

.telegram-cell .na {
  color: #adb5bd;
  font-style: italic;
}

.records-user-cell {
  min-width: 130px;
  position: relative;
}

.records-user-row {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.records-count {
  font-size: 0.78rem;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  padding: 0.1rem 0.42rem;
  min-width: 1.6rem;
  text-align: center;
}

.records-popover-btn {
  border: 1px solid #d0d7e2;
  background: #fff;
  border-radius: 8px;
  padding: 0.16rem 0.34rem;
  font-size: 0.74rem;
  cursor: pointer;
}

.records-popover-btn:hover {
  background: #f1f5f9;
}

.user-records-popover {
  position: absolute;
  top: calc(100% + 0.35rem);
  left: 0;
  width: 320px;
  max-height: 280px;
  overflow: auto;
  z-index: 12;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.15);
  padding: 0.55rem;
}

.records-user-cell {
  z-index: 2;
}

.user-records-title {
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.4rem;
}

.user-records-empty {
  font-size: 0.8rem;
  color: #64748b;
}

.user-records-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.user-record-item {
  border: 1px solid #edf2f7;
  border-radius: 8px;
  background: #f8fafc;
  padding: 0.42rem 0.5rem;
}

.user-record-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.72rem;
  color: #64748b;
  margin-bottom: 0.22rem;
}

.user-record-meta code {
  font-size: 0.7rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.06rem 0.3rem;
}

.user-record-text {
  font-size: 0.8rem;
  color: #1e293b;
  line-height: 1.35;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Messages */
.messages-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  padding: 0.8rem;
  border-radius: 10px;
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
