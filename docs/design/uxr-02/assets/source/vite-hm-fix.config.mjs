import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
export default defineConfig({root:path.resolve('docs/design/uxr-02/assets/source'),plugins:[react(),tailwindcss()],resolve:{alias:{'@':path.resolve('frontend/src')}},server:{port:4183,host:'127.0.0.1'}});
