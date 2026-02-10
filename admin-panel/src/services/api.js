import axios from 'axios'

// Use environment variable or default to production URL
const API_BASE_URL = import.meta.env.VITE_LANGGRAPH_API_URL || 'https://langgraph-server.herokuapp.com'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

/**
 * Search for threads with optional filters
 * @param {Object} params - Search parameters
 * @param {number} params.limit - Maximum number of threads to return
 * @param {Object} params.metadata - Metadata filters
 * @param {string} params.status - Thread status (idle, busy, interrupted, error)
 * @returns {Promise<Array>} Array of thread objects
 */
export async function searchThreads({ limit = 100, metadata = {}, status = null } = {}) {
  try {
    const payload = {
      limit,
      metadata,
      values: {}
    }
    if (status) {
      payload.status = status
    }

    const response = await api.post('/threads/search', payload)
    return response.data
  } catch (error) {
    console.error('Error searching threads:', error)
    throw error
  }
}

/**
 * Get detailed state of a specific thread
 * @param {string} threadId - Thread ID
 * @returns {Promise<Object>} Thread state object with users, messages, etc.
 */
export async function getThreadState(threadId) {
  try {
    const response = await api.get(`/threads/${threadId}/state`)
    return response.data
  } catch (error) {
    console.error(`Error getting state for thread ${threadId}:`, error)
    throw error
  }
}

/**
 * Get thread info (includes latest state values)
 * @param {string} threadId - Thread ID
 * @returns {Promise<Object>} Thread object with state
 */
export async function getThread(threadId) {
  try {
    const response = await api.get(`/threads/${threadId}`)
    return response.data
  } catch (error) {
    console.error(`Error getting thread ${threadId}:`, error)
    throw error
  }
}

/**
 * Get thread history (checkpoints)
 * @param {string} threadId - Thread ID
 * @returns {Promise<Array>} Array of checkpoint objects
 */
export async function getThreadHistory(threadId) {
  try {
    const response = await api.get(`/threads/${threadId}/history`)
    return response.data
  } catch (error) {
    console.error(`Error getting history for thread ${threadId}:`, error)
    throw error
  }
}

/**
 * Create a run in a thread and wait for completion.
 * @param {string} threadId
 * @param {Object} payload - RunCreateStateful payload
 * @returns {Promise<any>}
 */
export async function createRunWait(threadId, payload) {
  try {
    const response = await api.post(`/threads/${threadId}/runs/wait`, payload)
    return response.data
  } catch (error) {
    console.error(`Error creating run for thread ${threadId}:`, error)
    throw error
  }
}

/**
 * Admin command: set intro status for a user (persists in checkpoint).
 * Uses graph_router and an admin_panel sender name to bypass chat-side permissions.
 * @param {string} threadId
 * @param {Object} opts
 * @param {string|null} opts.username
 * @param {number|null} opts.telegramId
 * @param {boolean} opts.introCompleted
 */
export async function setIntroStatus(threadId, { username = null, telegramId = null, introCompleted }) {
  const target = username
    ? (username.startsWith('@') ? username : `@${username}`)
    : (telegramId != null ? `telegram:${telegramId}` : null)

  if (!target) {
    throw new Error('Cannot set intro status: missing username/telegramId')
  }

  const content = `/set_intro_status ${target} ${introCompleted ? 'done' : 'pending'}`

  return createRunWait(threadId, {
    assistant_id: 'graph_router',
    input: {
      messages: [
        {
          type: 'human',
          name: 'admin_panel',
          content
        }
      ]
    },
    metadata: {
      source: 'admin-panel',
      command: 'set_intro_status'
    }
  })
}

function base64UrlEncode(str) {
  // Base64url without padding.
  const bytes = new TextEncoder().encode(str)
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  const b64 = btoa(bin)
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

export async function upsertUsers(threadId, users) {
  if (!Array.isArray(users)) throw new Error('upsertUsers: users must be an array')
  const token = base64UrlEncode(JSON.stringify({ users }))
  const content = `/upsert_users ${token}`

  return createRunWait(threadId, {
    assistant_id: 'graph_router',
    input: {
      messages: [
        {
          type: 'human',
          name: 'admin_panel',
          content
        }
      ]
    },
    metadata: {
      source: 'admin-panel',
      command: 'upsert_users'
    }
  })
}

export async function deleteThread(threadId) {
  if (!threadId) throw new Error('deleteThread: missing threadId')
  const response = await api.delete(`/threads/${threadId}`)
  // LangGraph API typically returns 204 No Content.
  return response.data
}

export async function patchThread(threadId, patch) {
  if (!threadId) throw new Error('patchThread: missing threadId')
  if (!patch || typeof patch !== 'object') throw new Error('patchThread: patch must be an object')
  const response = await api.patch(`/threads/${threadId}`, patch)
  return response.data
}

export async function setThreadMetadata(threadId, metadata) {
  if (!metadata || typeof metadata !== 'object') throw new Error('setThreadMetadata: metadata must be an object')
  return patchThread(threadId, { metadata })
}

export async function mergeThreadMetadata(threadId, partial) {
  if (!partial || typeof partial !== 'object') throw new Error('mergeThreadMetadata: partial must be an object')
  const t = await getThread(threadId)
  const current = (t && t.metadata && typeof t.metadata === 'object') ? t.metadata : {}
  return setThreadMetadata(threadId, { ...current, ...partial })
}

export default {
  searchThreads,
  getThreadState,
  getThread,
  getThreadHistory,
  createRunWait,
  setIntroStatus,
  upsertUsers,
  deleteThread,
  patchThread,
  setThreadMetadata,
  mergeThreadMetadata
}
