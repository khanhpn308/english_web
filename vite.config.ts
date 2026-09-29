/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'frontend/dist',
    emptyOutDir: true,
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['frontend/tests/**/*.test.ts', 'frontend/tests/**/*.test.tsx'],
    passWithNoTests: false,
  },
});
