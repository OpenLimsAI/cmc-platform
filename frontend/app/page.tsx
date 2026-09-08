"use client";

import { Dashboard } from "@/components/Dashboard";
import { useAuth } from "@/components/AuthGate";

export default function Home() {
  const { user, logout } = useAuth();
  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-3">
        <h1 className="text-lg font-semibold">USP 上游分析看板</h1>
        <span className="text-sm text-slate-400">
          先选批次（项目 → 年份 → 批号 → 罐），再选要看的曲线：生长 / 生化 / 工艺，同屏叠加对比
        </span>
        {/* 后端开放模式（本地开发未配验签密钥）时提示一下 */}
        {user?.is_system && (
          <span className="ml-auto rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
            本地开放模式 · 未登录
          </span>
        )}
        {user && !user.is_system && (
          <span className="ml-auto flex items-center gap-2 text-xs text-slate-500">
            <span>{user.full_name || user.username}</span>
            <button
              onClick={logout}
              className="rounded border border-slate-200 px-2 py-0.5 text-slate-500 transition hover:bg-slate-50"
            >
              退出
            </button>
          </span>
        )}
      </header>
      <Dashboard />
    </div>
  );
}
