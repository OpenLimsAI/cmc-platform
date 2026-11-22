import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

function normalizeBasePath(raw?: string): string {
  const trimmed = (raw ?? '/water/').trim()
  if (!trimmed || trimmed === '/') {
    return '/'
  }
  const withLeading = trimmed.startsWith('/') ? trimmed : `/${trimmed}`
  return withLeading.endsWith('/') ? withLeading : `${withLeading}/`
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  return {
    plugins: [react()],
    base: normalizeBasePath(env.VITE_BASE_PATH),
    server: { host: '127.0.0.1', port: 5115, strictPort: true },
    preview: { host: '127.0.0.1', port: 5115, strictPort: true },
  }
})
