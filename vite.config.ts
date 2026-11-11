import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Firefox 115 ESR is the Windows 7 client. Keep it in the production build targets.
    target: ['chrome111', 'edge111', 'firefox115', 'safari16.4', 'ios16.4'],
  },
  server: { host: true, allowedHosts: true, proxy: { '/api': 'http://localhost:8000' } },
  preview: { host: true, allowedHosts: true },
})
