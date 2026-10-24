// 通用彩色 KPI 卡片，配色与原版 Streamlit 看板保持一致
const SCHEMES = {
  blue:   { bg: "#EAF2F8", label: "#154360", value: "#2E86C1" },
  green:  { bg: "#E9F7EF", label: "#145A32", value: "#28B463" },
  lapis:  { bg: "#EEF7FF", label: "#0B5CAD", value: "#1B6EC2" },
  orange: { bg: "#FFF6E6", label: "#9A5B00", value: "#D67D00" },
  red:    { bg: "#FDEDEC", label: "#922B21", value: "#C0392B" },
  purple: { bg: "#F5EEF8", label: "#6C3483", value: "#8E44AD" },
  gray:   { bg: "#F8F9F9", label: "#7F8C8D", value: "#95A5A6" },
} as const

export type CardScheme = keyof typeof SCHEMES

interface StatCardProps {
  label: string
  value: string | number
  unit?: string   // 附在数值后的小号单位文字，如 "工作日" "小时" "%"
  sub?: string    // 卡片底部辅助说明，如趋势箭头文字
  scheme?: CardScheme
}

export function StatCard({ label, value, unit, sub, scheme = "blue" }: StatCardProps) {
  const c = SCHEMES[scheme]
  return (
    <div
      style={{ backgroundColor: c.bg }}
      className="rounded-xl px-5 py-5 flex flex-col gap-1.5 items-center text-center"
    >
      <p className="text-sm font-semibold leading-snug" style={{ color: c.label }}>
        {label}
      </p>
      <p className="text-[2.6rem] font-extrabold tabular-nums leading-none" style={{ color: c.value }}>
        {value}
        {unit && (
          <span className="text-base font-semibold ml-1" style={{ color: c.value }}>
            {unit}
          </span>
        )}
      </p>
      {sub && (
        <p className="text-xs font-medium mt-0.5" style={{ color: c.label }}>
          {sub}
        </p>
      )}
    </div>
  )
}
