import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // antd / echarts 体量天生就大，已各自拆为独立 vendor chunk 单独缓存；
    // 阈值抬到 1300KB，避免它们反复触发告警，又能让真正的应用代码膨胀露头
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'antd-vendor': ['antd', '@ant-design/icons'],
          // echarts(~1MB) 拆出独立 chunk：仅访问仪表盘时才下载（配合路由懒加载）
          'echarts-vendor': ['echarts', 'echarts-for-react'],
        },
      },
    },
  },
});
