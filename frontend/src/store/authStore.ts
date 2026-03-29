/**
 * src/store/authStore.ts
 * ======================
 * Zustand store for authentication state.
 * Source of truth: localStorage tokens (persisted across reloads).
 * username and role are fetched from /analytics/api/profile/ after login.
 */

import { create } from 'zustand'
import { getAccessToken, clearTokens } from '../api/client'
import { login as apiLogin } from '../api/auth'
import client from '../api/client'

interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  username: string
  role: string
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => void
  fetchProfile: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: Boolean(getAccessToken()),
  isLoading: false,
  error: null,
  username: '',
  role: 'student',

  login: async (username, password) => {
    set({ isLoading: true, error: null })
    try {
      await apiLogin(username, password)
      set({ isAuthenticated: true, isLoading: false })
      // Fetch role/username right after login
      const { data } = await client.get<{ username: string; role: string }>(
        '/analytics/api/profile/'
      )
      set({ username: data.username, role: data.role })
    } catch {
      set({ isAuthenticated: false, isLoading: false, error: 'Invalid credentials' })
    }
  },

  logout: () => {
    clearTokens()
    set({ isAuthenticated: false, username: '', role: 'student' })
    window.location.replace('/login')
  },

  checkAuth: () => {
    set({ isAuthenticated: Boolean(getAccessToken()) })
  },

  fetchProfile: async () => {
    try {
      const { data } = await client.get<{ username: string; role: string }>(
        '/analytics/api/profile/'
      )
      set({ username: data.username, role: data.role })
    } catch {
      // token may be expired; checkAuth + interceptor handle redirect
    }
  },
}))
