import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Set base to './' so assets use relative paths — works on any host.
// For GitHub Pages with a sub-path, run: npm run deploy:gh-pages
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 3000,
    open: true
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  }
})
