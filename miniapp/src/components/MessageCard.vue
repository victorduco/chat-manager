<template>
  <div :class="['message-card', messageClass]">
    <div class="message-header">
      <span class="message-author">{{ message.name || 'Unknown' }}</span>
      <span class="message-time">{{ formatTime(message.timestamp) }}</span>
    </div>
    <div class="message-content">{{ message.content }}</div>
  </div>
</template>

<script>
export default {
  name: 'MessageCard',
  props: {
    message: {
      type: Object,
      required: true
    }
  },
  computed: {
    messageClass() {
      // Check if it's an AI message
      if (this.message.type === 'ai') {
        return 'message-ai'
      }
      // Check if it's from the current user
      if (this.message.name === 'admin_panel' || this.message.type === 'system') {
        return 'message-system'
      }
      return 'message-human'
    }
  },
  methods: {
    formatTime(timestamp) {
      if (!timestamp) return ''

      const date = new Date(timestamp)
      const now = new Date()
      const diffMs = now - date
      const diffMins = Math.floor(diffMs / 60000)

      if (diffMins < 1) return 'только что'
      if (diffMins < 60) return `${diffMins}м назад`

      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}ч назад`

      const diffDays = Math.floor(diffHours / 24)
      if (diffDays < 7) return `${diffDays}д назад`

      return date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short'
      })
    }
  }
}
</script>

<style scoped>
.message-card {
  background: var(--tg-theme-bg-color, #ffffff);
  border-radius: 12px;
  padding: 12px 16px;
  margin: 8px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.message-human {
  background: var(--tg-theme-bg-color, #ffffff);
  border-left: 3px solid var(--tg-theme-button-color, #3390ec);
}

.message-ai {
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-left: 3px solid #34c759;
}

.message-system {
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-left: 3px solid #ff9500;
  opacity: 0.8;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.message-author {
  font-size: 14px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
}

.message-time {
  font-size: 12px;
  color: var(--tg-theme-hint-color, #999999);
}

.message-content {
  font-size: 15px;
  line-height: 1.4;
  color: var(--tg-theme-text-color, #000000);
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
