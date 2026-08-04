"use client"
// 近N月趋势折线图：对应 Streamlit View 1 的月度趋势图
import ReactECharts from "echarts-for-react"
import dayjs from "dayjs"
import type { MonthlyTrendItem } from "@/lib/api"

interface Props {
  data: MonthlyTrendItem[]
}

export function MonthlyTrendChart({ data }: Props) {
  // 数据未覆盖到月底的月份，标签加"(截至MM-DD)"（与该月自身的月末比，
  // 而不是与"当前月"比：否则月初 ETL 未跑时，完整的上月也会被错标"截至"）
  const xLabels = data.map((d) => {
    if (d.month_end) {
      const end = dayjs(d.month_end)
      if (end.isBefore(dayjs(`${d.ym}-01`).endOf("month"), "day")) {
        return `${d.ym} (截至${end.format("MM-DD")})`
      }
    }
    return d.ym
  })

  const option = {
    tooltip: { trigger: "axis" },
    legend: { data: ["样品数", "检项数", "未完成检项"], bottom: 0 },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: "category",
      data: xLabels,
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: "value", axisLabel: { fontSize: 11 } },
    series: [
      {
        name: "样品数",
        type: "line",
        smooth: true,
        data: data.map((d) => d.sample_n),
        itemStyle: { color: "#3b82f6" },
      },
      {
        name: "检项数",
        type: "line",
        smooth: true,
        data: data.map((d) => d.test_n),
        itemStyle: { color: "#6366f1" },
      },
      {
        name: "未完成检项",
        type: "line",
        smooth: true,
        data: data.map((d) => d.pending_test_n),
        itemStyle: { color: "#f59e0b" },
        lineStyle: { type: "dashed" },
      },
    ],
  }
  return <ReactECharts option={option} style={{ height: 300 }} />
}
