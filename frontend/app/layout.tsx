import type { Metadata } from "next"
import { Suspense } from "react"
import "./globals.css"
import { Providers } from "@/lib/providers"
import { Navbar } from "@/components/navbar"

export const metadata: Metadata = {
  title: "TT LIMS Platform",
  description: "CMC 研发检验信息管理平台",
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
