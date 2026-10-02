/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'path';

export default defineConfig({
  root: 'frontend',
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': resolve(process.cwd(), 'frontend/src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(process.cwd(), 'frontend/index.html'),
        bootstrap: resolve(process.cwd(), 'frontend/bootstrap.html'),
      },
    },
  },
  test: {
    root: '.',
    globals: true,
    environment: 'node',
    include: [
      'frontend/tests/**/*.test.ts',
      'frontend/tests/**/*.test.tsx',
      'frontend/src/**/*.test.ts',
      'frontend/src/**/*.test.tsx',
    ],
    passWithNoTests: false,
  },
});
