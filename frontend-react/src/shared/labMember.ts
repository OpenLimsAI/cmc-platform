import type { User } from "../api/auth";

/**
 * LabOps 准入（2026-09-10 负责人）：实验室系统，只对部门以 TT / CMC 开头的员工开放，SYS_ADMIN 例外。
 * 与后端 auth.require_lab_member / LAB_DEPARTMENT_PREFIXES 同口径；前端只负责别让人看到空白页，真正拦截在后端。
 */
export const LAB_DEPARTMENT_PREFIXES = ["TT", "CMC"];

export function isLabMember(user: User | null | undefined): boolean {
  if (!user) return false;
  if (user.roles?.includes("SYS_ADMIN")) return true;
  const dept = (user.department ?? "").trim().toUpperCase();
  return LAB_DEPARTMENT_PREFIXES.some((p) => dept.startsWith(p));
}
