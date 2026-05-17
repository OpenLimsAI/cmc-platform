"use client"
// 近N月趋势折线图：对应 Streamlit View 1 的月度趋势图
import ReactECharts from "echarts-for-react"
import dayjs from "dayjs"
import type { MonthlyTrendItem } from "@/lib/api"

interface Props {
  data: MonthlyTrendItem[]
}

export function MonthlyTrendChart({ data }: Props) {
  // 最后一个月若未结束，标签加"(截至MM-DD)"，与 Streamlit 原版保持一致
  const xLabels = data.map((d, i) => {
    if (i === data.length - 1 && d.month_end) {
      const end = dayjs(d.month_end)
      if (end.isBefore(dayjs().endOf("month"))) {
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
