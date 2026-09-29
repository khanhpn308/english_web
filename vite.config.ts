/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'frontend',
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
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
