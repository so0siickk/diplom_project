import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In Docker the backend is reached via the service name; locally via 127.0.0.1.
const backendUrl = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    // 0.0.0.0 binds to all interfaces — required inside Docker
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/analytics': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
})
