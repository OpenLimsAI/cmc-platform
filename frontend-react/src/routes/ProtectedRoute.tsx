import { Navigate } from "react-router-dom";
import { Result } from "antd";
import { useAuthStore } from "../stores/authStore";

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
