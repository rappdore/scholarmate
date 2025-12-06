import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ''),
        configure: (proxy, options) => {
          proxy.on('error', (err, req) => {
            // eslint-disable-next-line no-console
            console.error('❌ [VITE PROXY ERROR]', {
              error: err.message,
              url: req.url,
              method: req.method,
              target: options.target,
              timestamp: new Date().toISOString(),
            });
          });
          proxy.on('proxyReq', (proxyReq, req) => {
            // eslint-disable-next-line no-console
            console.log('🔄 [VITE PROXY REQUEST]', {
              originalUrl: req.url,
              targetUrl: `${options.target}${proxyReq.path}`,
              method: req.method,
              headers: proxyReq.getHeaders(),
              timestamp: new Date().toISOString(),
            });
          });
          proxy.on('proxyRes', (proxyRes, req) => {
            // eslint-disable-next-line no-console
            console.log('✅ [VITE PROXY RESPONSE]', {
              originalUrl: req.url,
              status: proxyRes.statusCode,
              statusMessage: proxyRes.statusMessage,
              headers: proxyRes.headers,
              timestamp: new Date().toISOString(),
            });
          });
        },
      },
    },
  },
  optimizeDeps: {
    include: ['pdfjs-dist'],
  },
});
