import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/') || id.includes('node_modules/react-router')) {
            return 'vendor';
          }
          if (id.includes('node_modules/lucide-react') || id.includes('node_modules/@tiptap')) {
            return 'ui';
          }
          if (id.includes('node_modules/zustand')) {
            return 'state';
          }
        },
      },
    },
    chunkSizeWarningLimit: 1000,
    cssMinify: true,
    rolldownOptions: {
      output: {
        codeSplitting: true,
      },
    },
  },
})
