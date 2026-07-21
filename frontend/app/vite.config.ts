import tailwindcss from '@tailwindcss/vite';
import { tanstackRouterGenerator } from '@tanstack/router-plugin/vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

// dev 프록시 대상 = 로컬에서 띄운 wlk 백엔드(uvicorn). 배포 빌드에는 영향 없다.
const server = {
  host: process.env.VITE_SERVER_HOST ?? '127.0.0.1',
  port: process.env.VITE_SERVER_PORT ?? '8900',
};

export default defineConfig(() => {
  return {
    // 백엔드(basic_server.py `_detect_frontend_base`)가 index.html 의 자산 참조에서
    // 이 base 를 자동 추출해 /wlkies/assets 로 마운트한다. 바꾸면 백엔드 서빙 경로도 같이 바뀐다.
    base: '/wlkies',
    plugins: [react(), tailwindcss(), tanstackRouterGenerator()],
    resolve: {
      alias: {
        // process.cwd() 기준이면 다른 디렉터리에서 vite 를 호출할 때 깨진다 — 설정 파일 위치 기준으로 고정.
        '@': path.join(projectRoot, 'src'),
      },
    },
    build: {
      // 백엔드 `--frontend-dir` 기본값이 저장소 루트 기준 `frontend/static` 이다.
      // 여기(frontend/app)에서 한 단계 위 → frontend/static. `pnpm build` 만으로 서빙 위치에 떨어진다.
      outDir: '../static',
      // outDir 이 vite root 바깥이라 기본적으로 비우지 않는다(경고만). 명시적으로 켜서 stale 자산을 남기지 않는다.
      emptyOutDir: true,
    },
    server: {
      // ⚠️ '/wlkies' 는 프록시하지 않는다 — dev 서버가 이 base 로 앱 자체를 서빙하므로 프록시하면 앱이 안 뜬다.
      // 프론트는 백엔드 API 를 base 없는 절대 경로(/health, /api/...)로 호출해야 한다.
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
