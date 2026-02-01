import { defineConfig } from 'vite';

// Vite config for Electron preload script
export default defineConfig({
  build: {
    rollupOptions: {
      external: ['electron'],
      output: {
        format: 'cjs',
        entryFileNames: '[name].cjs',
      },
    },
  },
});
