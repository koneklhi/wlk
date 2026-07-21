import tailwindcss from '@tailwindcss/vite';
import { tanstackRouterGenerator } from '@tanstack/router-plugin/vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vite';

const server = {
  host: process.env.VITE_SERVER_HOST ?? '127.0.0.1',
  port: process.env.VITE_SERVER_PORT ?? '8900',
};

export default defineConfig(() => {
  return {
    base: '/wlkies',
    plugins: [react(), tailwindcss(), tanstackRouterGenerator()],
    resolve: {
      alias: {
        '@': path.join(process.cwd(), 'src'),
      },
    },
    // build: {
    //   outDir: '../backend/src/main/resources/static',
    // },
    server: {
      proxy: {
        '/asr': {
          target: `ws://${server.host}:${server.port}`,
          ws: true,
          changeOrigin: true,
        },
        '/api': {
          target: `http://${server.host}:${server.port}`,
          changeOrigin: true,
        },
        '/health': {
          target: `http://${server.host}:${server.port}`,
          changeOrigin: true,
        },
      },
    },
  };
});
