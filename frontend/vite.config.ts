import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: process.env.ELECTRON_RENDERER_URL ? '/' : './',
  // No dev proxy: the frontend always addresses the backend by absolute URL
  // (see src/services/config.ts), so dev, static build, and Electron behave
  // identically.
  optimizeDeps: {
    include: ['pdfjs-dist'],
  },
});
