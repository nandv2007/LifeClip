import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev server: proxies /api to the FastAPI backend so the browser only ever
// talks to one origin. The API secret stays server-side.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true, // sandbox preview hosts
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2020',
    sourcemap: false,
  },
})
