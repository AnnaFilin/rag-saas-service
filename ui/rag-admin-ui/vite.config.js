import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/ingest': {
        target: 'https://rag-saas-ingest-630957115938.me-west1.run.app',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/ingest/, ''),
      },
      '/api/rag': {
        target: 'https://rag-saas-rag-630957115938.me-west1.run.app',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/rag/, ''),
      },
    },
  },
})