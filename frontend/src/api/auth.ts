/**
 * src/api/auth.ts
 * ===============
 * Auth API calls: login, refresh, logout.
 * Uses a plain axios (not client) for login/refresh to avoid interceptor loops.
 */

import axios from 'axios'
import { BACKEND_URL, saveTokens, clearTokens } from './client'

interface TokenResponse {
  access: string
  refresh: string
}

export async function login(username: string, password: string): Promise<void> {
  const { data } = await axios.post<TokenResponse>(
    `${BACKEND_URL}/api/token/`,
    { username, password },
  )
  saveTokens(data.access, data.refresh)
}

export function logout(): void {
  clearTokens()
  window.location.replace('/login')
}
