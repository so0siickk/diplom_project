/**
 * src/api/client.ts
 * =================
 * Axios instance configured for the LMS Adaptive backend.
 *
 * Interceptor pipeline:
 *   REQUEST  → attach "Authorization: Bearer <access_token>" from localStorage
 *   RESPONSE → on 401: attempt silent token refresh, retry original request;
 *              on second 401 (refresh expired): clear tokens, redirect to /login
 *
 * Token rotation (ROTATE_REFRESH_TOKENS=True on the backend):
 *   Each successful refresh returns a new refresh token that replaces the old one.
 *
 * Concurrent-request safety:
 *   If multiple requests fail with 401 simultaneously, only one refresh call
 *   is made. All other requests are queued and retried after the refresh resolves.
 */

import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from 'axios'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const BACKEND_URL = 'http://127.0.0.1:8000'

/** localStorage keys — centralised so they're easy to rename or namespace. */
export const TOKEN_KEYS = {
  access: 'lms_access_token',
  refresh: 'lms_refresh_token',
} as const

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEYS.access)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(TOKEN_KEYS.refresh)
}

export function saveTokens(access: string, refresh?: string): void {
  localStorage.setItem(TOKEN_KEYS.access, access)
  if (refresh) {
    localStorage.setItem(TOKEN_KEYS.refresh, refresh)
  }
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEYS.access)
  localStorage.removeItem(TOKEN_KEYS.refresh)
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const client: AxiosInstance = axios.create({
  baseURL: BACKEND_URL,
  headers: { 'Content-Type': 'application/json' },
  // Django requires a trailing slash
  // (APPEND_SLASH=True by default)
})

// ---------------------------------------------------------------------------
// REQUEST interceptor — attach Bearer token
// ---------------------------------------------------------------------------

client.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error),
)

// ---------------------------------------------------------------------------
// RESPONSE interceptor — silent token refresh on 401
// ---------------------------------------------------------------------------

/**
 * Flag that prevents multiple simultaneous refresh calls.
 * While true, new 401-triggered requests are pushed to failedQueue.
 */
let isRefreshing = false

interface QueueEntry {
  resolve: (newAccessToken: string) => void
  reject: (err: unknown) => void
}

let failedQueue: QueueEntry[] = []

/** Drain the queue after a refresh attempt completes (success or failure). */
function flushQueue(error: unknown, newAccessToken: string | null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error)
    } else {
      resolve(newAccessToken!)
    }
  })
  failedQueue = []
}

/**
 * Performs a token refresh using a raw axios call (NOT through `client`)
 * to avoid triggering this interceptor recursively.
 */
async function refreshAccessToken(): Promise<string> {
  const refresh = getRefreshToken()

  if (!refresh) {
    throw new Error('No refresh token available')
  }

  const { data } = await axios.post<{ access: string; refresh?: string }>(
    `${BACKEND_URL}/api/token/refresh/`,
    { refresh },
  )

  // Persist new tokens (refresh may rotate per ROTATE_REFRESH_TOKENS=True)
  saveTokens(data.access, data.refresh)

  return data.access
}

/** Extends InternalAxiosRequestConfig with a retry flag to prevent loops. */
type RetryableConfig = InternalAxiosRequestConfig & { _retry?: boolean }

client.interceptors.response.use(
  // Pass successful responses through unchanged
  (response) => response,

  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableConfig | undefined

    // Only intercept 401 errors on requests we haven't already retried
    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry
    ) {
      return Promise.reject(error)
    }

    // --- Case 1: a refresh is already in progress ---
    // Queue this request; it will be retried once the refresh resolves.
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      })
        .then((newAccessToken) => {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
          return client(originalRequest)
        })
        .catch((err) => Promise.reject(err))
    }

    // --- Case 2: first 401 — attempt a refresh ---
    originalRequest._retry = true
    isRefreshing = true

    try {
      const newAccessToken = await refreshAccessToken()

      // Update the default header so subsequent requests use the new token
      client.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`

      // Retry all queued requests with the new token
      flushQueue(null, newAccessToken)

      // Retry the original request
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
      return client(originalRequest)
    } catch (refreshError) {
      // Refresh failed (token expired / revoked) — log the user out
      flushQueue(refreshError, null)
      clearTokens()

      // Redirect to login without full page reload (SPA-friendly)
      window.location.replace('/login')

      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

export default client
