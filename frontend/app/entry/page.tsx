"use client";

// 数据录入页（独立页面，不和曲线展示混在一起）。路径 /usp/entry。
// 目前录两个指标：渗透压、葡萄糖（试剂盒法，摇瓶摇管不做生化分析时用）。
import Link from "next/link";
import { DataEntry } from "@/components/DataEntry";
import { useAuth } from "@/components/AuthGate";

export default function EntryPage() {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      {/* 顶栏固定在页面顶部，表再长也能随时点「返回看板」 */}
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-3">
        <h1 className="text-lg font-semibold">数据录入</h1>
        <span className="text-sm text-slate-400">
          每天把仪器采不到的结果填进来：渗透压、葡萄糖（试剂盒法，当天没做生化分析时才填），曲线和数据表里就有了
        </span>
        <Link
          href="/"
          className="ml-auto rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-600 transition hover:bg-slate-50"
        >
          ← 返回看板
        </Link>
        {user?.is_system && (
          <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">本地开放模式 · 未登录</span>
        )}
        {user && !user.is_system && (
          <span className="flex items-center gap-2 text-xs text-slate-500">
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
      <main className="mx-auto w-full max-w-6xl px-5 py-4">
        <DataEntry />
      </main>
    </div>
  );
}
