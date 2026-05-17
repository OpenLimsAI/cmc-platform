import { redirect } from "next/navigation"

// 根路径重定向到检验概况
export default function Home() {
  redirect("/dashboard/overview")
}
