import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';
import type { ProxyOptions } from 'vite';

const proxy: ProxyOptions = {
  target: 'http://127.0.0.1:8765',
  changeOrigin: true,
  configure(server) {
    server.on('proxyReq', (outgoing, incoming) => {
      // Translate only this loopback UI's browser requests. Foreign origins stay rejected.
      if (
        ['http://127.0.0.1:5173', 'http://localhost:5173'].includes(incoming.headers.origin ?? '')
      ) {
        outgoing.removeHeader('origin');
      }
    });
  },
};
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { input: { dashboard: 'index.html', workbench: 'workbench.html' } },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    cors: false,
    proxy: { '/api': proxy, '/health': proxy },
  },
  preview: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    cors: false,
    proxy: { '/api': proxy, '/health': proxy },
  },
  test: {
    // Keep jsdom workers within this local gate's resource budget. Parallel suites
    // starved user-event timers; retain file isolation and the 5-second timeout.
    maxWorkers: 1,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    restoreMocks: true,
    include: process.env.DASHBOARD_TEST_API
      ? ['tests/backend.integration.ts']
      : ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
  },
});
