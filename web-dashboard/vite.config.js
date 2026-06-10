import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    extensions: ['.mjs', '.js', '.jsx', '.json'],
  },
  server: {
    port: 3000,
    open: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          apexcharts: ['apexcharts', 'react-apexcharts'],
          jspdf: ['jspdf', 'jspdf-autotable'],
          supabase: ['@supabase/supabase-js'],
          vendor: ['react', 'react-dom'],
        },
      },
    },
  },
});
