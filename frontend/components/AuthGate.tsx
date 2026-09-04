"use client";

// 全站登录门：未登录先见登录页，登录后才渲染看板。
// 规范见 ~/code/CLAUDE.md §8：账号/密码/角色统一在 MDM Portal 维护，
// 本项目只代理登录 + 本地验签。登录页视觉与 MDM Portal / LabOps /
// rd-batch-registry 保持一致（渐变背景 #1F4E79→#2E75B6、白标题、400px 卡片）。
// 后端未配验签密钥时为本地开放模式（/api/auth/me 返回 is_system），不弹登录页。
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { clearToken, fetchMe, getToken, login, notifyAuthExpired, setToken, type Me } from "@/lib/api";
import { logoutReasonText, mdmLogout, startSessionGuard } from "@/lib/cmabSession";

const AuthContext = createContext<{ user: Me | null; logout: () => void }>({
  user: null,
  logout: () => {},
});

/** 页面里取当前登录人 / 退出登录（开放模式 user.is_system=true） */
export function useAuth() {
  return useContext(AuthContext);
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  // 探测当前身份：带着本地令牌（若有）问 /api/auth/me。
  // 开放模式无令牌也 200；配了鉴权则 401 → 拦截器清令牌并派发过期事件。
  const meQ = useQuery({
    queryKey: ["auth-me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: Infinity,
  });

  // 任何接口 401（令牌过期/被撤销）→ 回登录页
  useEffect(() => {
    const onExpired = () => {
      qc.setQueryData(["auth-me"], undefined);
      qc.invalidateQueries({ queryKey: ["auth-me"] });
    };
    window.addEventListener("usp-auth-expired", onExpired);
    return () => window.removeEventListener("usp-auth-expired", onExpired);
  }, [qc]);

  const logout = useCallback(() => {
    void mdmLogout(); // 撤销 MDM refresh + 清全公司共用令牌（best-effort）
    clearToken();
    qc.clear(); // 顺带清掉所有数据缓存，防止换账号看到上一个人的数据
    qc.invalidateQueries({ queryKey: ["auth-me"] });
  }, [qc]);

  // 会话守卫（2026-09-04）：空闲超时自动登出 / 通行证快到期静默续期 / 别的标签页或系统登出跟着退。
  // 开放模式（is_system，无令牌）不启动。
  const loggedIn = !!meQ.data && !meQ.data.is_system && !!getToken();
  useEffect(() => {
    if (!loggedIn) return;
    return startSessionGuard({
      onLogout: (reason) => {
        if (reason !== "other-tab") void mdmLogout();
        clearToken();
        qc.clear();
        notifyAuthExpired(reason);
      },
    });
  }, [loggedIn, qc]);

  if (meQ.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-400">
        正在检查登录状态…
      </div>
    );
  }

  if (!meQ.data) {
    return (
      <LoginPage
        onSuccess={() => qc.invalidateQueries({ queryKey: ["auth-me"] })}
      />
    );
  }

  return (
    <AuthContext.Provider value={{ user: meQ.data, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ---- 登录页（视觉规范：与 MDM Portal / LabOps / rd-batch-registry 一致）----

function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 被会话守卫踢回来时的说明（api.ts notifyAuthExpired 写入 sessionStorage）
  const [notice] = useState<string | null>(() => {
    try {
      const r = sessionStorage.getItem("cmab_logout_reason");
      sessionStorage.removeItem("cmab_logout_reason");
      return logoutReasonText(r);
    } catch {
      return null;
    }
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) {
      setError(!username ? "请输入工号" : "请输入密码");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await login(username.trim(), password);
      if (!data.access_token) {
        setError("登录返回里没有令牌");
        return;
      }
      setToken(data.access_token, data.user); // 同时落 cmab_user，供门户/其他子系统共用
      onSuccess();
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "登录失败，请稍后再试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-6"
      style={{ background: "linear-gradient(135deg, #1F4E79 0%, #2E75B6 100%)" }}
    >
      <div className="mb-10 text-center">
        <h1 className="mb-2 text-4xl font-semibold text-white">
          USP 上游分析看板
        </h1>
        <p className="text-base text-white/85">
          工艺曲线 · 细胞生长 · 生化分析 · 多源批次对比
        </p>
      </div>

      <div
        className="w-[400px] rounded-lg bg-white p-6"
        style={{ boxShadow: "0 8px 32px rgba(0,0,0,0.18)" }}
      >
        <h2 className="mb-6 text-center text-xl font-semibold">工号登录</h2>

        {notice && !error && (
          <div className="mb-4 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
            {notice}
          </div>
        )}

        {error && (
          <div className="mb-4 flex items-start justify-between rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-2 text-red-400 hover:text-red-600"
              aria-label="关闭"
            >
              ×
            </button>
          </div>
        )}

        <form onSubmit={onSubmit} autoComplete="off">
          <label className="mb-4 block">
            <span className="mb-1 block text-sm text-slate-600">工号</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="工号"
              autoComplete="username"
              autoFocus
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-base focus:border-blue-500 focus:outline-none"
            />
          </label>
          <label className="mb-6 block">
            <span className="mb-1 block text-sm text-slate-600">密码</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="密码"
              autoComplete="current-password"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-base focus:border-blue-500 focus:outline-none"
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="mb-3 w-full rounded-md bg-blue-600 py-2.5 text-base text-white transition hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "登录中…" : "登 录"}
          </button>
          <div className="text-center text-[13px] text-slate-400">
            工号与密码统一在 MDM Portal 维护，忘记密码请联系系统管理员
          </div>
        </form>
      </div>

      <div className="mt-8 text-xs text-white/70">
        © 2026 CMAB · USP 上游分析看板 · 内部系统
      </div>
    </div>
  );
}
