/**
 * src/store/authStore.ts
 * ======================
 * Zustand store for authentication state.
 * Source of truth: localStorage tokens (persisted across reloads).
 */

import { create } from 'zustand'
import { getAccessToken, clearTokens } from '../api/client'
import { login as apiLogin } from '../api/auth'

interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: Boolean(getAccessToken()),
  isLoading: false,
  error: null,

  login: async (username, password) => {
    set({ isLoading: true, error: null })
    try {
      await apiLogin(username, password)
      set({ isAuthenticated: true, isLoading: false })
    } catch {
      set({ isAuthenticated: false, isLoading: false, error: 'Invalid credentials' })
    }
  },

  logout: () => {
    clearTokens()
    set({ isAuthenticated: false })
    window.location.replace('/login')
  },

  checkAuth: () => {
    set({ isAuthenticated: Boolean(getAccessToken()) })
  },
}))
