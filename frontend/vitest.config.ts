import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest config is kept separate from vite.config.ts so the dev-server proxy
// settings don't leak into the test environment.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // E2E lives in ../e2e and is driven by pytest-playwright, not vitest.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
