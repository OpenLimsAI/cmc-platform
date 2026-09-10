import { Navigate } from "react-router-dom";
import { Result } from "antd";
import { useAuthStore } from "../stores/authStore";
import { isLabMember } from "../shared/labMember";

/**
 * 登录守卫;可选 roles 做模块级角色拦截(FR-PLT-003:无权限模块不可直达)。
 * 菜单已按角色隐藏入口,这里兜住直接敲 URL 的情况;后端写接口另有守卫。
 */
export default function ProtectedRoute({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: string[];
}) {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn());
  const user = useAuthStore((s) => s.user);

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }

  // 2026-09-10 负责人：LabOps 是实验室系统，只对部门以 TT / CMC 开头的员工开放（SYS_ADMIN 例外）。
  // 与后端 auth.require_lab_member 同口径；这里只是别让不符合的人看到空白/一堆 403，真正拦截在后端。
  if (!isLabMember(user)) {
    return (
      <Result
        status="403"
        title="LabOps 仅对实验室部门开放"
        subTitle={`当前账号部门「${user?.department || "未填写"}」不在开放范围（TT / CMC）。部门信息在 MDM 维护，如有疑问请联系管理员。`}
      />
    );
  }

  if (roles && !roles.some((r) => user?.roles?.includes(r))) {
    return (
      <Result
        status="403"
        title="无权访问"
        subTitle="此模块需要相应角色权限;角色在 MDM Portal 维护,如需开通请联系管理员。"
      />
    );
  }

  return <>{children}</>;
}
