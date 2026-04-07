import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    host: '0.0.0.0',
    proxy: {
      '/research': 'http://localhost:8000',
      '/stream': 'http://localhost:8000',
      '/report': 'http://localhost:8000',
      '/memory': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
