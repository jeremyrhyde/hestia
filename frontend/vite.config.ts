/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Served by FastAPI at / (and by Pantheon under /hestia/). In dev, Vite serves
// the UI and forwards the API, its WebSocket and /health to the Python server.
export default defineConfig({
  base: './',
  plugins: [svelte()],
  define: { __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.0.0') },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8003', ws: true },
      '/health': 'http://localhost:8003',
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
