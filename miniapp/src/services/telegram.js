/**
 * Telegram WebApp utilities
 */

import { v5 as uuidv5 } from 'uuid'

export function getTelegramWebApp() {
  return window.Telegram?.WebApp
}

export function getInitData() {
  const tg = getTelegramWebApp()
  return tg?.initData || ''
}

export function getInitDataUnsafe() {
  const tg = getTelegramWebApp()
  return tg?.initDataUnsafe || {}
}

/**
 * Generate thread ID from chat ID using UUID5 (same as bot does)
 * Must match the logic in chatbot/event_handlers/utils/stream/context_extractor.py
 *
 * Note: uuid v13+ validates UUID format strictly. The namespace UUID
 * '12345678-1234-5678-1234-567812345678' works in Python but not in JS.
 * We need to use a properly formatted UUID or downgrade uuid library.
 */
function chatIdToThreadId(chatId) {
  // Create a buffer representation of the namespace to bypass validation
  // This matches the Python uuid.UUID('12345678-1234-5678-1234-567812345678')
  const NAMESPACE_STR = '12345678-1234-5678-1234-567812345678'

  // Convert to buffer manually (bypassing strict validation)
  const parts = NAMESPACE_STR.split('-')
  const hex = parts.join('')
  const buffer = new Uint8Array(16)
  for (let i = 0; i < 16; i++) {
    buffer[i] = parseInt(hex.substr(i * 2, 2), 16)
  }

  // Generate UUID5 from chat_id using the namespace buffer
  return uuidv5(String(chatId), buffer)
}

export function getChatId() {
  const initDataUnsafe = getInitDataUnsafe()

  let chatId = null

  console.log('[getChatId] initDataUnsafe:', initDataUnsafe)

  // Priority 1: start_param (for groups, bot should pass chat ID)
  if (initDataUnsafe.start_param) {
    // Try format: "chat_-1001234567890" or "chat_1234567890"
    const matchWithPrefix = initDataUnsafe.start_param.match(/^chat_(-?\d+)$/)
    if (matchWithPrefix) {
      chatId = matchWithPrefix[1]
      console.log('[getChatId] Found chatId from start_param (with prefix):', chatId)
    } else if (/^-?\d+$/.test(initDataUnsafe.start_param)) {
      // Direct chat_id: "-1001234567890" or "1234567890"
      chatId = initDataUnsafe.start_param
      console.log('[getChatId] Found chatId from start_param (direct):', chatId)
    }
  }

  // Priority 2: Direct chat.id (if available)
  if (!chatId && initDataUnsafe.chat?.id) {
    chatId = String(initDataUnsafe.chat.id)
    console.log('[getChatId] Found chatId from chat.id:', chatId)
  }

  // Priority 3: For private chats, use user.id
  if (!chatId && (initDataUnsafe.chat_type === 'sender' || !initDataUnsafe.chat_type)) {
    chatId = String(initDataUnsafe.user?.id || null)
    console.log('[getChatId] Found chatId from user.id:', chatId)
  }

  // Priority 4: Fallback to chat_instance
  if (!chatId) {
    chatId = initDataUnsafe.chat_instance
    console.log('[getChatId] Found chatId from chat_instance:', chatId)
  }

  console.log('[getChatId] Final chatId before UUID conversion:', chatId)

  // Convert chat ID to thread ID using UUID5 (same as bot)
  if (chatId) {
    try {
      const threadId = chatIdToThreadId(chatId)
      console.log('[getChatId] Generated thread ID:', threadId)
      return threadId
    } catch (err) {
      console.error('[getChatId] Error generating UUID:', err)
      return null
    }
  }

  console.log('[getChatId] No chatId found, returning null')
  return null
}

export function getUserId() {
  const initDataUnsafe = getInitDataUnsafe()
  return initDataUnsafe.user?.id || null
}

export function getUser() {
  const initDataUnsafe = getInitDataUnsafe()
  return initDataUnsafe.user || null
}

export function getStartParam() {
  const initDataUnsafe = getInitDataUnsafe()
  return initDataUnsafe.start_param || null
}

export function showAlert(message) {
  const tg = getTelegramWebApp()
  if (tg?.showAlert) {
    tg.showAlert(message)
  } else {
    alert(message)
  }
}

export function showConfirm(message) {
  const tg = getTelegramWebApp()
  if (tg?.showConfirm) {
    return new Promise((resolve) => {
      tg.showConfirm(message, resolve)
    })
  } else {
    return Promise.resolve(confirm(message))
  }
}

export function hapticFeedback(type = 'light') {
  const tg = getTelegramWebApp()
  if (tg?.HapticFeedback) {
    if (type === 'impact') {
      tg.HapticFeedback.impactOccurred('light')
    } else if (type === 'notification') {
      tg.HapticFeedback.notificationOccurred('success')
    } else if (type === 'selection') {
      tg.HapticFeedback.selectionChanged()
    }
  }
}

export function openLink(url, options = {}) {
  const tg = getTelegramWebApp()
  if (tg?.openLink) {
    tg.openLink(url, options)
  } else {
    window.open(url, '_blank')
  }
}

export function close() {
  const tg = getTelegramWebApp()
  if (tg?.close) {
    tg.close()
  }
}

export function expand() {
  const tg = getTelegramWebApp()
  if (tg?.expand) {
    tg.expand()
  }
}

export function ready() {
  const tg = getTelegramWebApp()
  if (tg?.ready) {
    tg.ready()
  }
}
