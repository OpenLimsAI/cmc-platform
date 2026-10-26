import { QueryClient } from '@tanstack/react-query';

/**
 * 全局唯一 QueryClient。单独成模块（不放 main.tsx）是为了让 authStore 能在登出时
 * queryClient.clear()，避免同一标签页换人登录后看到上一个人的缓存数据。
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});
