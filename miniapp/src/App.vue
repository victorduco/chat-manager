<template>
  <div id="app" :style="themeStyles">
    <SearchBar v-if="activeTab !== 'messages'" @search="handleSearch" />
    <TabBar :activeTab="activeTab" :tabs="tabs" @change="handleTabChange" />

    <div class="content">
      <!-- Messages Tab -->
      <template v-if="activeTab === 'messages'">
        <div class="debug-panel">
          <h3>🐛 Debug Info</h3>
          <div class="debug-item">
            <strong>Raw Chat Instance:</strong> {{ getRawChatInstance() || 'не определён' }}
          </div>
          <div class="debug-item">
            <strong>Thread ID (UUID):</strong> {{ chatId || 'не определён' }}
          </div>
          <div class="debug-item">
            <strong>Telegram WebApp:</strong> {{ isTelegramAvailable() ? 'доступен' : 'недоступен' }}
          </div>
          <div class="debug-item">
            <strong>Init Data (raw):</strong>
            <pre style="font-size: 9px; overflow-x: auto; word-wrap: break-word; white-space: pre-wrap; margin-top: 4px;">{{ getTelegramInitData() || 'пусто' }}</pre>
          </div>
          <div class="debug-item">
            <strong>User ID:</strong> {{ getTelegramUser()?.id || 'не определён' }}
          </div>
          <div class="debug-item">
            <strong>Username:</strong> {{ getTelegramUser()?.username || 'не определён' }}
          </div>
          <div class="debug-item">
            <strong>Messages count:</strong> {{ messages.length }}
          </div>
          <div class="debug-item">
            <strong>API URL:</strong> {{ getApiUrl() }}
          </div>
          <div class="debug-item">
            <strong>Environment:</strong> {{ isDev ? 'dev' : 'prod' }}
          </div>
          <div class="debug-item">
            <strong>Full initDataUnsafe:</strong>
            <pre style="font-size: 9px; overflow-x: auto; margin-top: 4px;">{{ JSON.stringify(getInitDataUnsafe(), null, 2) }}</pre>
          </div>

          <div v-if="debugLogs.length > 0" class="debug-logs">
            <strong>Logs:</strong>
            <div v-for="(log, idx) in debugLogs" :key="idx" class="log-entry">
              {{ log }}
            </div>
          </div>
        </div>

        <!-- Loading state -->
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>Загрузка...</p>
        </div>

        <!-- Error state -->
        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button @click="loadMessages" class="retry-button">Повторить</button>
        </div>

        <!-- Empty state -->
        <div v-else-if="messages.length === 0" class="empty-state">
          <div class="empty-icon">💬</div>
          <p>Нет сообщений</p>
        </div>

        <!-- Messages -->
        <MessageCard
          v-else
          v-for="(message, index) in messages"
          :key="index"
          :message="message"
        />
      </template>

      <!-- Other Tabs -->
      <template v-else>
        <div v-if="filteredItems.length === 0" class="empty-state">
          <div class="empty-icon">🔍</div>
          <p>Ничего не найдено</p>
        </div>

        <!-- Vacancies -->
        <template v-if="activeTab === 'vacancies'">
          <VacancyCard
            v-for="item in filteredItems"
            :key="item.id"
            :vacancy="item"
            @click="handleItemClick"
          />
        </template>

        <!-- Mentors -->
        <template v-if="activeTab === 'mentors'">
          <MentorCard
            v-for="item in filteredItems"
            :key="item.id"
            :mentor="item"
            @click="handleItemClick"
          />
        </template>

        <!-- Services -->
        <template v-if="activeTab === 'services'">
          <ServiceCard
            v-for="item in filteredItems"
            :key="item.id"
            :service="item"
            @click="handleItemClick"
          />
        </template>

        <!-- Courses -->
        <template v-if="activeTab === 'courses'">
          <CourseCard
            v-for="item in filteredItems"
            :key="item.id"
            :course="item"
            @click="handleItemClick"
          />
        </template>

        <!-- Resources -->
        <template v-if="activeTab === 'resources'">
          <ResourceCard
            v-for="item in filteredItems"
            :key="item.id"
            :resource="item"
            @click="handleItemClick"
          />
        </template>

        <!-- Participants -->
        <template v-if="activeTab === 'participants'">
          <div
            v-for="participant in filteredItems"
            :key="participant.id"
            class="participant-card"
          >
            <div class="participant-info">
              <div class="participant-name">{{ participant.name }}</div>
              <div class="participant-username">@{{ participant.username }}</div>
            </div>
            <button
              class="intro-button"
              type="button"
              @click="showIntro(participant)"
            >
              Показать интро
            </button>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script>
import SearchBar from './components/SearchBar.vue'
import TabBar from './components/TabBar.vue'
import VacancyCard from './components/VacancyCard.vue'
import MentorCard from './components/MentorCard.vue'
import ServiceCard from './components/ServiceCard.vue'
import CourseCard from './components/CourseCard.vue'
import ResourceCard from './components/ResourceCard.vue'
import MessageCard from './components/MessageCard.vue'
import { vacancies, mentors, services, courses, resources } from './data/mockData.js'
import { getThreadState } from './services/api.js'
import { getChatId, hapticFeedback, openLink } from './services/telegram.js'

export default {
  name: 'App',
  components: {
    SearchBar,
    TabBar,
    VacancyCard,
    MentorCard,
    ServiceCard,
    CourseCard,
    ResourceCard,
    MessageCard
  },
  data() {
    return {
      activeTab: 'participants',
      searchQuery: '',
      tabs: [
        // { id: 'messages', label: 'Сообщения', icon: '💬' },
        { id: 'vacancies', label: 'Вакансии', icon: '💼' },
        { id: 'mentors', label: 'Менторы', icon: '👨‍🏫' },
        { id: 'services', label: 'Услуги', icon: '🎨' },
        { id: 'courses', label: 'Курсы', icon: '📚' },
        { id: 'resources', label: 'Ресурсы', icon: '🔗' },
        { id: 'participants', label: 'Участники', icon: '👥' }
      ],
      data: {
        vacancies,
        mentors,
        services,
        courses,
        resources,
        participants: []
      },
      messages: [],
      chatId: null,
      loading: false,
      error: null,
      themeStyles: {},
      debugLogs: [],
      isDev: import.meta.env.DEV || window.location.hostname === 'localhost'
    }
  },
  computed: {
    currentItems() {
      return this.data[this.activeTab] || []
    },
    filteredItems() {
      if (!this.searchQuery) {
        return this.currentItems
      }

      const query = this.searchQuery.toLowerCase()
      return this.currentItems.filter(item => {
        const searchFields = [
          item.title,
          item.name,
          item.company,
          item.provider,
          item.school,
          ...(item.tags || [])
        ]
        return searchFields.some(field =>
          field && field.toLowerCase().includes(query)
        )
      })
    }
  },
  methods: {
    addDebugLog(message) {
      const timestamp = new Date().toLocaleTimeString()
      this.debugLogs.push(`[${timestamp}] ${message}`)
      console.log(message)
    },
    isTelegramAvailable() {
      return typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp
    },
    getTelegramInitData() {
      if (!this.isTelegramAvailable()) return null
      return window.Telegram.WebApp.initData || null
    },
    getTelegramUser() {
      if (!this.isTelegramAvailable()) return null
      return window.Telegram.WebApp.initDataUnsafe?.user || null
    },
    getApiUrl() {
      return this.isDev ? 'http://localhost:2024' : 'https://langgraph-server-611bd1822796.herokuapp.com'
    },
    getInitDataUnsafe() {
      if (!this.isTelegramAvailable()) return {}
      return window.Telegram.WebApp.initDataUnsafe || {}
    },
    getRawChatInstance() {
      const initDataUnsafe = this.getInitDataUnsafe()
      return initDataUnsafe.start_param || initDataUnsafe.chat?.id || initDataUnsafe.chat_instance || null
    },
    handleSearch(query) {
      this.searchQuery = query
    },
    async handleTabChange(tabId) {
      this.activeTab = tabId
      this.searchQuery = ''
      hapticFeedback('selection')

      // Load thread state when switching to messages/participants tab
      if ((tabId === 'messages' || tabId === 'participants') && this.messages.length === 0) {
        await this.loadMessages()
      }
    },
    handleItemClick(item) {
      hapticFeedback('light')
      console.log('Clicked item:', item)
    },
    showIntro(participant) {
      if (!participant?.introMessage) {
        return
      }
      hapticFeedback('light')
      openLink(participant.introMessage)
    },
    async loadMessages() {
      if (!this.chatId) {
        this.error = 'Не удалось получить ID чата'
        this.addDebugLog('❌ No chat ID available')
        return
      }

      this.addDebugLog(`🔄 Loading messages for chat ID: ${this.chatId}`)
      this.loading = true
      this.error = null

      try {
        this.addDebugLog(`📡 Requesting /threads/${this.chatId}/state`)
        const threadState = await getThreadState(this.chatId)
        this.addDebugLog(`✅ Thread state received`)
        this.addDebugLog(`📊 Thread state: ${JSON.stringify(threadState, null, 2).substring(0, 200)}...`)

        // Extract messages from thread state
        if (threadState && threadState.values && threadState.values.messages) {
          this.messages = threadState.values.messages.map(msg => ({
            type: msg.type || 'human',
            name: msg.name || msg.sender || 'Unknown',
            content: msg.content || msg.text || '',
            timestamp: msg.timestamp || msg.additional_kwargs?.timestamp || null
          }))
          this.addDebugLog(`✅ Extracted ${this.messages.length} messages`)
        } else {
          this.messages = []
          this.addDebugLog('⚠️ No messages in thread state')
        }

        // Extract participants with intro messages
        const rawUsers = threadState?.values?.users || []
        const participants = rawUsers
          .filter(user => typeof user?.intro_message === 'string' && user.intro_message.trim())
          .map((user, index) => ({
            id: user.telegram_id || user.username || `participant_${index}`,
            name: user.preferred_name || user.first_name || user.username || 'Unknown',
            username: user.username || 'unknown',
            introMessage: user.intro_message.trim()
          }))

        this.data.participants = participants
        this.addDebugLog(`✅ Extracted ${participants.length} participants with intro`)
      } catch (err) {
        this.addDebugLog(`❌ Error: ${err.message}`)
        this.addDebugLog(`📍 Status: ${err.response?.status || 'unknown'}`)
        this.addDebugLog(`📍 Response: ${JSON.stringify(err.response?.data || {})}`)

        // More detailed error message
        if (err.response?.status === 404) {
          this.error = `Тред не найден (ID: ${this.chatId})`
        } else if (err.response?.status === 403) {
          this.error = 'Доступ запрещён'
        } else if (err.message?.includes('Network Error')) {
          this.error = 'Ошибка сети. Проверьте подключение к LangGraph API'
        } else {
          this.error = `Ошибка загрузки: ${err.message}`
        }
      } finally {
        this.loading = false
      }
    },
    initTelegramWebApp() {
      const tg = window.Telegram?.WebApp
      if (!tg) return

      // Expand to full height
      tg.expand()

      // Apply Telegram theme colors
      this.themeStyles = {
        '--tg-theme-bg-color': tg.themeParams.bg_color || '#ffffff',
        '--tg-theme-text-color': tg.themeParams.text_color || '#000000',
        '--tg-theme-hint-color': tg.themeParams.hint_color || '#999999',
        '--tg-theme-link-color': tg.themeParams.link_color || '#3390ec',
        '--tg-theme-button-color': tg.themeParams.button_color || '#3390ec',
        '--tg-theme-button-text-color': tg.themeParams.button_text_color || '#ffffff',
        '--tg-theme-secondary-bg-color': tg.themeParams.secondary_bg_color || '#f0f0f0'
      }

      // Signal that app is ready
      tg.ready()
    }
  },
  async mounted() {
    this.addDebugLog('🚀 App mounted')

    this.initTelegramWebApp()

    // Get chat ID from Telegram
    this.chatId = getChatId()
    this.addDebugLog(`📱 Chat ID from Telegram: ${this.chatId}`)

    const user = this.getTelegramUser()
    if (user) {
      this.addDebugLog(`👤 User: ${user.username || user.first_name} (ID: ${user.id})`)
    }

    // Auto-load messages if starting on messages tab
    if (this.activeTab === 'messages' && this.chatId) {
      await this.loadMessages()
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow-x: hidden;
}

#app {
  min-height: 100vh;
  background: var(--tg-theme-bg-color, #ffffff);
  color: var(--tg-theme-text-color, #000000);
  padding-bottom: 16px;
}

.content {
  padding-top: 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.3;
}

.empty-state p {
  font-size: 16px;
  color: var(--tg-theme-hint-color, #999999);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-top-color: var(--tg-theme-button-color, #3390ec);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-state p {
  font-size: 16px;
  color: var(--tg-theme-hint-color, #999999);
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.error-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.error-state p {
  font-size: 16px;
  color: #ff3b30;
}

.debug-panel {
  background: #1a1a1a;
  color: #00ff00;
  padding: 16px;
  margin: 8px 16px;
  border-radius: 8px;
  font-size: 11px;
  font-family: 'Courier New', monospace;
  max-height: 500px;
  overflow-y: auto;
}

.debug-panel h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #ffff00;
}

.debug-item {
  margin: 6px 0;
  padding: 4px 0;
  border-bottom: 1px solid #333;
}

.debug-item strong {
  color: #00ffff;
}

.debug-logs {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 2px solid #333;
}

.log-entry {
  margin: 4px 0;
  padding: 4px 8px;
  background: #2a2a2a;
  border-radius: 4px;
  word-wrap: break-word;
  font-size: 10px;
}

.retry-button {
  margin-top: 16px;
  padding: 12px 24px;
  background: var(--tg-theme-button-color, #3390ec);
  color: var(--tg-theme-button-text-color, #ffffff);
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.retry-button:active {
  opacity: 0.7;
}

.participant-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 8px 16px;
  padding: 14px;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-radius: 10px;
}

.participant-info {
  min-width: 0;
}

.participant-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
}

.participant-username {
  margin-top: 4px;
  font-size: 13px;
  color: var(--tg-theme-hint-color, #999999);
}

.intro-button {
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--tg-theme-button-color, #3390ec);
  color: var(--tg-theme-button-text-color, #ffffff);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.intro-button:active {
  opacity: 0.75;
}
</style>
