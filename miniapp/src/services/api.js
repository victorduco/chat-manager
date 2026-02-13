import axios from 'axios'
import { getInitData } from './telegram.js'

// Secure API URLs (proxies to LangGraph with authentication)
const API_URLS = {
  prod: 'https://secure-api-miniapp-c0bdba44bbe0.herokuapp.com',
  dev: 'http://localhost:8000' // Secure API runs on port 8000
}

// Determine environment
const isDev = import.meta.env.DEV || window.location.hostname === 'localhost'
const baseURL = isDev ? API_URLS.dev : API_URLS.prod

// Create axios instance
const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add Telegram initData to requests for authentication
api.interceptors.request.use((config) => {
  const initData = getInitData()
  if (initData) {
    config.headers['X-Telegram-Init-Data'] = initData
  }
  return config
})

/**
 * Get thread state (conversation history)
 * @param {string} threadId - Thread ID (chat_id)
 * @returns {Promise<Object>} Thread state with messages
 */
export async function getThreadState(threadId) {
  try {
    console.log(`Fetching thread state for ID: ${threadId}`)
    console.log(`Request URL: ${api.defaults.baseURL}/threads/${threadId}/state`)
    const response = await api.get(`/threads/${threadId}/state`)
    console.log(`Response status: ${response.status}`)
    console.log(`Response data:`, response.data)
    return response.data
  } catch (error) {
    console.error(`Error getting state for thread ${threadId}:`, error)
    console.error(`Error response:`, error.response)
    throw error
  }
}

/**
 * Get thread info
 * @param {string} threadId - Thread ID
 * @returns {Promise<Object>} Thread object
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
 * Search threads with filters
 * @param {Object} params - Search parameters
 * @returns {Promise<Array>} Array of threads
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
 * Send message to thread (create a run)
 * @param {string} threadId - Thread ID
 * @param {string} message - Message content
 * @param {Object} user - User info
 * @returns {Promise<any>}
 */
export async function sendMessage(threadId, message, user) {
  try {
    const payload = {
      assistant_id: 'graph_router',
      input: {
        messages: [
          {
            type: 'human',
            name: user.username || `user_${user.id}`,
            content: message
          }
        ]
      },
      metadata: {
        source: 'miniapp',
        user_id: user.id,
        username: user.username
      }
    }

    const response = await api.post(`/threads/${threadId}/runs/wait`, payload)
    return response.data
  } catch (error) {
    console.error(`Error sending message to thread ${threadId}:`, error)
    throw error
  }
}

export default {
  getThreadState,
  getThread,
  getThreadHistory,
  searchThreads,
  sendMessage
}
