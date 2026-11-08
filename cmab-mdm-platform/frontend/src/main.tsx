import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { BASE } from '@/shared/base';
import { ApplicationTheme } from '@/shared/ApplicationTheme';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/shared/queryClient';
import 'dayjs/locale/zh-cn';

import App from './App';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ApplicationTheme>
        <BrowserRouter basename={BASE}>
          <App />
        </BrowserRouter>
      </ApplicationTheme>
    </QueryClientProvider>
  </React.StrictMode>
);
