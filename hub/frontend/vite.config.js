import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Builds straight into the FastAPI app's static dir so the hub can
// serve the whole SPA (plus its JS/CSS bundle) without a separate Node
// server in production -- see hub/app/main.py's dashboard route and
// static mount. `base` matches where that mount serves from.
export default defineConfig({
  plugins: [react()],
  base: '/static/dist/',
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
