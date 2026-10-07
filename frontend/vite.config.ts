/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// The API paths the dev server forwards to FastAPI on :8000, so `npm run dev` talks to the real API.
const API_PATHS = ['/sessions', '/progress', '/exercises', '/inputs', '/extractions', '/programs', '/workouts', '/templates', '/config']

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    proxy: Object.fromEntries(API_PATHS.map((p) => [p, 'http://localhost:8000'])),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
