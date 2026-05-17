// dashboard 子布局：左侧边栏（日期+检验组筛选）+ 右侧内容区
// dynamic = force-dynamic：禁止静态预渲染，因为侧边栏和各页面均依赖 useSearchParams
export const dynamic = "force-dynamic"

import { Suspense } from "react"
import { DashboardSidebar } from "@/components/dashboard-sidebar"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex -mx-4 -my-6 min-h-[calc(100vh-3.5rem)]">
      <Suspense>
        <DashboardSidebar />
      </Suspense>
      <main className="flex-1 min-w-0 px-6 py-6 overflow-auto">
        <Suspense>{children}</Suspense>
      </main>
    </div>
  )
}
