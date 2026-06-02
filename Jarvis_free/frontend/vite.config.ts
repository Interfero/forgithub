import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const devPanelStub = path.resolve(
  __dirname,
  'src/components/dev-panel/DevPanelShell.stub.tsx',
)

export default defineConfig(() => {
  // Локальное приложение: панель разработчика (бессознательное) всегда в UI.
  const includeDevPanel = true

  return {
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@jarvis-base': path.resolve(__dirname, '../../jarvis/jarvis.png'),
      ...(includeDevPanel
        ? {}
        : {
            '@/components/dev-panel/DevPanelShell': devPanelStub,
          }),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    headers: {
      'Cache-Control': 'no-store',
    },
    hmr: {
      host: '127.0.0.1',
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  }
})
