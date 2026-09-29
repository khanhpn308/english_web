import React from 'react';
import { createRoot } from 'react-dom/client';
import { AppShell } from './app/AppShell';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Không tìm thấy phần tử root trong tài liệu');
}

const root = createRoot(rootElement);
root.render(
  <React.StrictMode>
    <AppShell />
  </React.StrictMode>
);
