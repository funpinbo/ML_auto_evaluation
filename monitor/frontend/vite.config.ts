import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// dev 서버는 API 를 로컬 백엔드(8765)로 넘긴다. 빌드 결과(dist)는 백엔드가 같은 출처로 서빙한다.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 1200 },
  test: { environment: 'jsdom', include: ['tests/**/*.spec.ts'] },
})
