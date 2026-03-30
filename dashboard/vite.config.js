import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: process.env.BUILD_TARGET === 'firebase'
      ? path.resolve(__dirname, 'dist')
      : path.resolve(__dirname, '../agent/static'),
    emptyOutDir: true,
  },
})
