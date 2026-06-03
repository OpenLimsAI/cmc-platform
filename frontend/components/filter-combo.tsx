"use client"
// 单个可搜索筛选下拉框：受控 value（null=全部），options 由父组件按联动逻辑算好后传入。
// 用于超期未检明细表的 4 个联动筛选框，纯前端、自包含（不依赖 base-ui，避免版本 API 差异）。
import { useEffect, useRef, useState } from "react"
import { ChevronDownIcon, XIcon } from "lucide-react"

interface FilterComboProps {
  label: string
  value: string | null
  options: string[]
  onChange: (v: string | null) => void
}

export function FilterCombo({ label, value, options, onChange }: FilterComboProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const ref = useRef<HTMLDivElement>(null)

  // 点击外部关闭
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener("mousedown", onDown)
    return () => window.removeEventListener("mousedown", onDown)
  }, [open])

  const filtered = query
    ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase()))
    : options

  return (
    <div className="relative min-w-[150px] flex-1" ref={ref}>
      <span className="block text-[11px] text-gray-400 mb-0.5">{label}</span>
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v)
          setQuery("")
        }}
        className="flex h-8 w-full items-center justify-between gap-1 rounded-md border border-gray-300 bg-white px-2.5 text-xs text-gray-700 transition-colors hover:border-blue-400"
      >
        <span className={value ? "truncate" : "truncate text-gray-400"}>{value ?? "全部"}</span>
        {value ? (
          <XIcon
            className="size-3.5 shrink-0 text-gray-400 hover:text-gray-600"
            onClick={(e) => {
              e.stopPropagation()
              onChange(null)
            }}
          />
        ) : (
          <ChevronDownIcon className="size-3.5 shrink-0 text-gray-400" />
        )}
      </button>

      {open && (
        <div className="absolute z-30 mt-1 w-full min-w-[200px] rounded-md border border-gray-200 bg-white shadow-lg">
          <div className="border-b p-1.5">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索…"
              className="w-full rounded border border-gray-200 px-2 py-1 text-xs outline-none focus:border-blue-400"
            />
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            <button
              type="button"
              onClick={() => {
                onChange(null)
                setOpen(false)
              }}
              className="block w-full px-2.5 py-1 text-left text-xs text-gray-500 hover:bg-gray-50"
            >
              全部
            </button>
            {filtered.length === 0 ? (
              <p className="px-2.5 py-2 text-xs text-gray-300">无匹配</p>
            ) : (
              filtered.map((o) => (
                <button
                  key={o}
                  type="button"
                  title={o}
                  onClick={() => {
                    onChange(o)
                    setOpen(false)
                  }}
                  className={`block w-full truncate px-2.5 py-1 text-left text-xs hover:bg-blue-50 ${
                    o === value ? "bg-blue-50 font-medium text-blue-700" : "text-gray-700"
                  }`}
                >
                  {o}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
