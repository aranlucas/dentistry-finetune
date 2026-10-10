import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// The Python server (src/server.py) owns /api and serves the built app from dist/.
// In `npm run dev`, Vite proxies /api to it. The server only accepts its own origin, so
// requests from this dev page are re-addressed to it; other origins pass through and are refused.
const api = process.env.LAB_API ?? 'http://127.0.0.1:8765';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: api,
        changeOrigin: true,
        configure: proxy => proxy.on('proxyReq', (req, incoming) => {
          const origin = incoming.headers.origin, host = incoming.headers.host;
          if (origin && host && origin === `http://${host}`) req.setHeader('origin', api);
        }),
      },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
});
