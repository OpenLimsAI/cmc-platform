import type { Metadata } from "next"
import { Suspense } from "react"
import "./globals.css"
import { Providers } from "@/lib/providers"
import { Navbar } from "@/components/navbar"

export const metadata: Metadata = {
  title: "CMC R&D LIMS Dashboard",
  description: "CMC 研发 LIMS 检验进度与考核看板（cmc_analytics.mart）",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="min-h-full flex flex-col bg-gray-50 antialiased">
        <Providers>
          <Suspense><Navbar /></Suspense>
          <main className="flex-1 container mx-auto px-4 py-6 max-w-screen-2xl">{children}</main>
        </Providers>
      </body>
    </html>
  )
}
