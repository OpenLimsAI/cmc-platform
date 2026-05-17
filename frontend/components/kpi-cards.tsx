"use client"
import { StatCard } from "@/components/stat-card"
import type { KPIResponse } from "@/lib/api"

interface Props {
  data: KPIResponse
}

export function KpiCards({ data }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <StatCard label="样品数（到样）"    value={data.sample_n.toLocaleString()}      scheme="blue"   />
      <StatCard label="检项数（到样）"    value={data.test_n.toLocaleString()}        scheme="green"  />
      <StatCard label="已完成检项（完结）" value={data.done_test_n.toLocaleString()}   scheme="lapis"  />
      <StatCard label="未完成检项"        value={data.pending_test_n.toLocaleString()} scheme="orange" />
    </div>
  )
}
