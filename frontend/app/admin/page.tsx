"use client"

import { useEffect, useRef, useState } from "react"
import api, { logout } from "@/lib/api"
import { getToken, getUser, isAdmin, type AuthUser } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Pencil, Check, X, Upload, Plus } from "lucide-react"

// ---------- types ----------
interface MethodItem { method_code: string; method_name: string | null; std_minutes: number | null; target_days: number | null }
interface EmployeeItem { employee_id: string; employee_name: string | null; department: string | null }

// --- inline-editable cell ---
function EditableCell({
  value,
  type = "text",
  onSave,
}: {
  value: string | number | null
  type?: "text" | "number"
  onSave: (v: string) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(String(value ?? ""))
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    await onSave(val)
    setSaving(false)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          autoFocus
          type={type}
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false) }}
          className="border rounded px-1 py-0.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400"
        />
        <button onClick={save} disabled={saving} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
        <button onClick={() => setEditing(false)} className="text-gray-400 hover:text-gray-600"><X size={14} /></button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1 group">
      <span className="text-sm">{value ?? <span className="text-gray-300">—</span>}</span>
      <button
        onClick={() => { setVal(String(value ?? "")); setEditing(true) }}
        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-indigo-500 transition-opacity"
      >
        <Pencil size={12} />
      </button>
    </div>
  )
}

// --- upload button ---
function UploadButton({ url, onDone }: { url: string; onDone: () => void }) {
  const ref = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState<string | null>(null)

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setStatus("上传中…")
    const form = new FormData()
    form.append("file", file)
    try {
      const { data } = await api.post<{ upserted: number }>(url, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setStatus(`已更新 ${data.upserted} 条`)
      onDone()
    } catch {
      setStatus("上传失败")
    }
    e.target.value = ""
  }

  return (
    <div className="flex items-center gap-2">
      <input ref={ref} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFile} />
      <Button variant="outline" size="sm" onClick={() => ref.current?.click()}>
        <Upload size={14} className="mr-1" /> 导入 Excel
      </Button>
      {status && <span className="text-xs text-gray-500">{status}</span>}
    </div>
  )
}

// --- methods tab ---
function MethodsTab() {
  const [rows, setRows] = useState<MethodItem[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newRow, setNewRow] = useState({ method_code: "", method_name: "", std_minutes: "", target_days: "" })
  const [saveError, setSaveError] = useState("")

  const load = async () => {
    setLoading(true)
    const { data } = await api.get<MethodItem[]>("/api/v1/admin/methods")
    setRows(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const updateField = async (code: string, field: "method_name" | "std_minutes" | "target_days", val: string) => {
    const payload = field === "std_minutes" ? { std_minutes: parseFloat(val) }
      : field === "target_days" ? { target_days: val ? parseInt(val) : null }
      : { method_name: val }
    const { data } = await api.put<MethodItem>(`/api/v1/admin/methods/${encodeURIComponent(code)}`, payload)
    setRows((prev) => prev.map((r) => (r.method_code === code ? data : r)))
  }

  const saveNew = async () => {
    if (!newRow.method_code.trim()) { setSaveError("方法编码不能为空"); return }
    setSaveError("")
    try {
      const { data } = await api.post<MethodItem>("/api/v1/admin/methods", {
        method_code: newRow.method_code.trim(),
        method_name: newRow.method_name.trim() || null,
        std_minutes: newRow.std_minutes ? parseFloat(newRow.std_minutes) : null,
        target_days: newRow.target_days ? parseInt(newRow.target_days) : null,
      })
      setRows((prev) => [data, ...prev])
      setAdding(false)
      setNewRow({ method_code: "", method_name: "", std_minutes: "", target_days: "" })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSaveError(msg ?? "保存失败")
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">共 {rows.length} 条方法</p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => { setAdding(true); setSaveError("") }}>
            <Plus size={14} className="mr-1" /> 新增
          </Button>
          <UploadButton url="/api/v1/admin/methods/upload" onDone={load} />
        </div>
      </div>
      {loading ? (
        <p className="text-sm text-gray-400">加载中…</p>
      ) : (
        <div className="overflow-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-3 py-2 text-left w-36">方法编码</th>
                <th className="px-3 py-2 text-left">方法名称</th>
                <th className="px-3 py-2 text-right w-32">标准工时 (min)</th>
                <th className="px-3 py-2 text-right w-28">检验期限 (天)</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {adding && (
                <tr className="bg-indigo-50">
                  <td className="px-3 py-1.5">
                    <input
                      autoFocus
                      placeholder="方法编码 *"
                      value={newRow.method_code}
                      onChange={(e) => setNewRow((p) => ({ ...p, method_code: e.target.value }))}
                      className="border rounded px-1 py-0.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    <input
                      placeholder="方法名称"
                      value={newRow.method_name}
                      onChange={(e) => setNewRow((p) => ({ ...p, method_name: e.target.value }))}
                      className="border rounded px-1 py-0.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <input
                      type="number"
                      step="0.1"
                      placeholder="分钟"
                      value={newRow.std_minutes}
                      onChange={(e) => setNewRow((p) => ({ ...p, std_minutes: e.target.value }))}
                      className="border rounded px-1 py-0.5 text-sm w-20 text-right focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    <div className="flex items-center gap-1 justify-end">
                      <input
                        type="number"
                        placeholder="天"
                        value={newRow.target_days}
                        onChange={(e) => setNewRow((p) => ({ ...p, target_days: e.target.value }))}
                        className="border rounded px-1 py-0.5 text-sm w-16 text-right focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      />
                      <button onClick={saveNew} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
                      <button onClick={() => { setAdding(false); setSaveError("") }} className="text-gray-400 hover:text-gray-600"><X size={14} /></button>
                    </div>
                    {saveError && <p className="text-xs text-red-500 text-right mt-0.5">{saveError}</p>}
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.method_code} className="hover:bg-gray-50">
                  <td className="px-3 py-1.5 text-gray-400 font-mono text-xs">{r.method_code}</td>
                  <td className="px-3 py-1.5">
                    <EditableCell value={r.method_name} onSave={(v) => updateField(r.method_code, "method_name", v)} />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <EditableCell value={r.std_minutes} type="number" onSave={(v) => updateField(r.method_code, "std_minutes", v)} />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <EditableCell value={r.target_days} type="number" onSave={(v) => updateField(r.method_code, "target_days", v)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// --- employees tab ---
function EmployeesTab() {
  const [rows, setRows] = useState<EmployeeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newRow, setNewRow] = useState({ employee_id: "", employee_name: "", department: "" })
  const [saveError, setSaveError] = useState("")

  const load = async () => {
    setLoading(true)
    const { data } = await api.get<EmployeeItem[]>("/api/v1/admin/employees")
    setRows(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const updateField = async (id: string, field: "employee_name" | "department", val: string) => {
    const { data } = await api.put<EmployeeItem>(
      `/api/v1/admin/employees/${encodeURIComponent(id)}`,
      { [field]: val },
    )
    setRows((prev) => prev.map((r) => (r.employee_id === id ? data : r)))
  }

  const saveNew = async () => {
    if (!newRow.employee_id.trim()) { setSaveError("员工 ID 不能为空"); return }
    setSaveError("")
    try {
      const { data } = await api.post<EmployeeItem>("/api/v1/admin/employees", {
        employee_id: newRow.employee_id.trim(),
        employee_name: newRow.employee_name.trim() || null,
        department: newRow.department.trim() || null,
      })
      setRows((prev) => [data, ...prev])
      setAdding(false)
      setNewRow({ employee_id: "", employee_name: "", department: "" })
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSaveError(msg ?? "保存失败")
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">共 {rows.length} 名员工</p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => { setAdding(true); setSaveError("") }}>
            <Plus size={14} className="mr-1" /> 新增
          </Button>
          <UploadButton url="/api/v1/admin/employees/upload" onDone={load} />
        </div>
      </div>
      {loading ? (
        <p className="text-sm text-gray-400">加载中…</p>
      ) : (
        <div className="overflow-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-3 py-2 text-left w-28">员工 ID</th>
                <th className="px-3 py-2 text-left">姓名</th>
                <th className="px-3 py-2 text-left">部门</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {adding && (
                <tr className="bg-indigo-50">
                  <td className="px-3 py-1.5">
                    <input
                      autoFocus
                      placeholder="员工 ID *"
                      value={newRow.employee_id}
                      onChange={(e) => setNewRow((p) => ({ ...p, employee_id: e.target.value }))}
                      className="border rounded px-1 py-0.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    <input
                      placeholder="姓名"
                      value={newRow.employee_name}
                      onChange={(e) => setNewRow((p) => ({ ...p, employee_name: e.target.value }))}
                      className="border rounded px-1 py-0.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    <div className="flex items-center gap-1">
                      <input
                        placeholder="部门"
                        value={newRow.department}
                        onChange={(e) => setNewRow((p) => ({ ...p, department: e.target.value }))}
                        className="border rounded px-1 py-0.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      />
                      <button onClick={saveNew} className="text-green-600 hover:text-green-700 shrink-0"><Check size={14} /></button>
                      <button onClick={() => { setAdding(false); setSaveError("") }} className="text-gray-400 hover:text-gray-600 shrink-0"><X size={14} /></button>
                    </div>
                    {saveError && <p className="text-xs text-red-500 mt-0.5">{saveError}</p>}
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.employee_id} className="hover:bg-gray-50">
                  <td className="px-3 py-1.5 text-gray-400 font-mono text-xs">{r.employee_id}</td>
                  <td className="px-3 py-1.5">
                    <EditableCell value={r.employee_name} onSave={(v) => updateField(r.employee_id, "employee_name", v)} />
                  </td>
                  <td className="px-3 py-1.5">
                    <EditableCell value={r.department} onSave={(v) => updateField(r.employee_id, "department", v)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------- main page ----------
// 鉴权：复用 MDM 统一登录。管理员角色（CMC_LIMS_ADMIN / SYS_ADMIN）直接进入，无需再输密码；
// 已登录但无管理员角色 → 提示无权限；未登录 → AuthGuard 已跳 /login。
export default function AdminPage() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checked, setChecked] = useState(false)
  const [tab, setTab] = useState<"methods" | "employees">("methods")

  useEffect(() => {
    if (getToken()) setUser(getUser())
    setChecked(true)
  }, [])

  if (!checked) return null

  if (!isAdmin(user)) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <div className="bg-white rounded-xl shadow p-8 w-96 space-y-2 text-center">
          <h1 className="text-lg font-semibold text-gray-800">无管理权限</h1>
          <p className="text-sm text-gray-500">
            管理员后台需要「LIMS 管理员」角色，请联系管理员在 MDM Portal 中分配。
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">管理员后台</h1>
          <p className="text-xs text-gray-400 mt-0.5">{user!.full_name || user!.username} · 管理员</p>
        </div>
        <button
          className="text-sm text-gray-400 hover:text-gray-600"
          onClick={async () => { await logout(); window.location.href = "/login" }}
        >
          退出登录
        </button>
      </div>

      <div className="flex gap-1 border-b">
        {(["methods", "employees"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-indigo-500 text-indigo-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "methods" ? "检验方法" : "检验人员"}
          </button>
        ))}
      </div>

      {tab === "methods" ? <MethodsTab /> : <EmployeesTab />}
    </div>
  )
}
