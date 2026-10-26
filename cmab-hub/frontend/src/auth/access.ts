import type { HubApp } from '@/config/apps'
import type { HubUser } from '@/stores/authStore'

// 图标显隐规则（设计方案 §5）：按 MDM 角色码判定；SYS_ADMIN 全可见。
// 这只是"看不看得到"的 UX 层，真正能不能用由各子系统后端自己鉴权。
export function canAccess(app: HubApp, user: HubUser | null): boolean {
  if (!user) return false
  if (app.status === 'hidden') return false
  if (app.requires === 'authenticated') return true
  if (user.roles.includes('SYS_ADMIN')) return true
  if (Array.isArray(app.requires)) return app.requires.some((r) => user.roles.includes(r))
  // 对象形态：各条件为「或」
  const req = app.requires
  if (req.roles?.some((r) => user.roles.includes(r))) return true
  if (req.anyPermission && (user.permissions?.length ?? 0) > 0) return true
  // 按部门前缀（如 LabOps：TT* / CMC*）；部门来自 MDM auth.user.department
  const dept = (user.department ?? '').trim().toUpperCase()
  if (req.departmentPrefixes?.some((p) => dept.startsWith(p.toUpperCase()))) return true
  return false
}
