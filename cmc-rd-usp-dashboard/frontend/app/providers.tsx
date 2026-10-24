"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthGate } from "@/components/AuthGate";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60_000, refetchOnWindowFocus: false },
        },
      })
  );
  return (
    <QueryClientProvider client={client}>
      {/* 全站登录门：未登录只能见登录页（后端开放模式除外） */}
      <AuthGate>{children}</AuthGate>
    </QueryClientProvider>
  );
}
