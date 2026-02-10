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

export default {
  searchThreads,
  getThreadState,
  getThread,
  getThreadHistory,
  createRunWait,
  setIntroStatus
}
