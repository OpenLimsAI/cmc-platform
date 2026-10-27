import { create } from 'zustand';
import { queryClient } from '@/shared/queryClient';
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware';
import type { LoginResponseUser } from '@/api/types';
import { authResultIsCurrent, type AuthExitReason } from '@/shared/oidcPolicy';

// ── 全公司统一令牌 key（cmab-hub 统一门户 2026-08-17 拍板）────────────────────
// localStorage['cmab_access_token'] = MDM access token 原文（JWT）
// localStorage['cmab_user']         = 登录响应里的 user 对象 JSON
// 所有子系统同源挂在 5100 之下、都读这两个 key → 门户登录一次，到处免登。
// 这里给 zustand persist 套一个适配器：对外仍是 {token,user} 状态，落盘时拆成上面两个 key。
const TOKEN_KEY = 'cmab_access_token';
const USER_KEY = 'cmab_user';
const LEGACY_KEY = 'cmab-mdm-auth'; // 旧 key，读到就迁移一次然后删掉

const unifiedStorage: StateStorage = {
  getItem: () => {
    let token = localStorage.getItem(TOKEN_KEY);
    let userRaw = localStorage.getItem(USER_KEY);
    if (!token) {
      // 兼容旧版本：从旧 key 迁移
      const legacy = localStorage.getItem(LEGACY_KEY);
      if (legacy) {
        try {
          const st = JSON.parse(legacy)?.state ?? {};
          if (st.token) {
            token = st.token;
            userRaw = st.user ? JSON.stringify(st.user) : null;
            localStorage.setItem(TOKEN_KEY, token as string);
            if (userRaw) localStorage.setItem(USER_KEY, userRaw);
          }
        } catch {
          /* ignore */
        }
        localStorage.removeItem(LEGACY_KEY);
      }
    }
    if (!token) return null;
    let user: unknown = null;
    try {
      user = userRaw ? JSON.parse(userRaw) : null;
    } catch {
      user = null;
    }
    return JSON.stringify({ state: { token, user }, version: 0 });
  },
  setItem: (_name, value) => {
    try {
      const st = JSON.parse(value)?.state ?? {};
      if (st.token) {
        localStorage.setItem(TOKEN_KEY, st.token);
        if (st.user) localStorage.setItem(USER_KEY, JSON.stringify(st.user));
        else localStorage.removeItem(USER_KEY);
      } else {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      }
    } catch {
      /* ignore */
    }
  },
  removeItem: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

/**
 * 用户管理端点的操作范围（与后端 dept_admin.user_admin_scope 同口径）：
 *  - 'all'        SYS_ADMIN 或持 user:manage → 全公司
 *  - 'department' 仅持 DEPT_ADMIN（部门管理员）→ 本部门
 *  - null         无用户管理能力
 */
export type UserAdminScope = 'all' | 'department' | null;

/** 六个主数据域的读权限；一个都没有 = 只用下游系统的账号，MDM 里只给个人中心 */
export const DOMAIN_READ_PERMISSIONS = [
  'substance:read',
  'project:read',
  'asset:read',
  'material:read',
  'equipment:read',
  'target:read',
] as const;

function computeUserAdminScope(user: LoginResponseUser | null): UserAdminScope {
  if (!user) return null;
  if (user.roles.includes('SYS_ADMIN') || user.permissions.includes('user:manage')) return 'all';
  if (user.roles.includes('DEPT_ADMIN')) return 'department';
  return null;
}

interface AuthState {
  token: string | null;
  authMode: 'native' | 'oidc' | null;
  authEpoch: number;
  authExitReason: AuthExitReason;
  oidcExpiresAt: string | null;
  pmDelegated: boolean;
  oidcEnabled: boolean;
  nativeLoginEnabled: boolean;
  bootstrapPending: boolean;
  bootstrapError: string | null;
  user: LoginResponseUser | null;
  permissions: Set<string>;
  isAdmin: boolean;
  userAdminScope: UserAdminScope;

  setAuth: (token: string, user: LoginResponseUser) => void;
  setOidcSession: (user: LoginResponseUser, expiresAt: string, pmDelegated: boolean, expectedEpoch?: number) => void;
  setOidcConfig: (enabled: boolean, nativeEnabled: boolean) => number;
  finishBootstrap: (error?: string) => void;
  updateToken: (token: string) => void;
  beginLogout: () => number;
  cancelLogout: (expectedEpoch: number) => void;
  logout: (reason?: AuthExitReason) => void;
  hasPermission: (perm: string) => boolean;
  /** 是否有任一主数据域读权限（仪表盘 / 首页落点用） */
  hasAnyReadPermission: () => boolean;
  /** 强制改密完成后清标记：否则 ProtectedRoute 会一直把人弹回改密页 */
  clearMustChangePassword: () => void;
  requirePasswordChange: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      authMode: null,
      authEpoch: 0,
      authExitReason: null,
      oidcExpiresAt: null,
      pmDelegated: false,
      oidcEnabled: false,
      nativeLoginEnabled: true,
      bootstrapPending: true,
      bootstrapError: null,
      user: null,
      permissions: new Set(),
      isAdmin: false,
      userAdminScope: null,

      setAuth: (token, user) => {
        if (!get().nativeLoginEnabled) return;
        if (get().user?.user_id !== user.user_id || get().authMode !== 'native') queryClient.clear();
        set({
          token,
          authMode: 'native',
          authEpoch: get().authEpoch + 1,
          authExitReason: null,
          oidcExpiresAt: null,
          pmDelegated: false,
          user,
          permissions: new Set(user.permissions),
          isAdmin: user.roles.includes('SYS_ADMIN'),
          userAdminScope: computeUserAdminScope(user),
          hasPermission: (perm) => get().isAdmin || get().permissions.has(perm),
        });
      },

      // OIDC credentials remain in the HttpOnly cookie/server session. Persist's
      // native-token adapter removes legacy bearer state instead of storing this user.
      setOidcSession: (user, expiresAt, pmDelegated, expectedEpoch) => {
        if (expectedEpoch !== undefined && !authResultIsCurrent(expectedEpoch, get().authEpoch, get().authExitReason)) return;
        const changed = get().user?.user_id !== user.user_id || get().authMode !== 'oidc';
        if (get().user?.user_id !== user.user_id || get().authMode !== 'oidc') queryClient.clear();
        set({ token: null, authMode: 'oidc', user, oidcExpiresAt: expiresAt, pmDelegated,
          authEpoch: get().authEpoch + (changed ? 1 : 0), authExitReason: null,
          permissions: new Set(user.permissions), isAdmin: user.roles.includes('SYS_ADMIN'),
          userAdminScope: computeUserAdminScope(user),
          // Existing guards select this function. A new reference also notifies
          // those guards when a non-admin's permission set changes in-session.
          hasPermission: (perm) => get().isAdmin || get().permissions.has(perm) });
      },
      setOidcConfig: (enabled, nativeEnabled) => {
        if (!nativeEnabled && (get().authMode === 'native' || get().token)) get().logout();
        set({ oidcEnabled: enabled, nativeLoginEnabled: nativeEnabled });
        return get().authEpoch;
      },
      finishBootstrap: (error) => set({ bootstrapPending: false, bootstrapError: error ?? null }),

      // 换证可能恰好跨越密码到期日；同步服务端声明，权限仍沿用现有用户资料。
      updateToken: (token) => {
        if (!get().nativeLoginEnabled) return;
        let mustChange: boolean | undefined;
        try {
          const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
          const flag = JSON.parse(atob(part.padEnd(Math.ceil(part.length / 4) * 4, '='))).must_change_password;
          if (typeof flag === 'boolean') mustChange = flag;
        } catch { /* 后端鉴权仍是权威；解析失败不清已有改密标记 */ }
        set((state) => ({ token, user: state.user && mustChange !== undefined
          ? { ...state.user, must_change_password: mustChange } : state.user }));
      },

      requirePasswordChange: () => set((state) => ({
        user: state.user ? { ...state.user, must_change_password: true } : null,
      })),

      beginLogout: () => {
        const epoch = get().authEpoch + 1;
        set({ authEpoch: epoch, authExitReason: 'logout' });
        return epoch;
      },
      cancelLogout: (expectedEpoch) => {
        if (get().authEpoch === expectedEpoch && get().user && get().authExitReason === 'logout') {
          set({ authEpoch: expectedEpoch + 1, authExitReason: null });
        }
      },
      logout: (reason) => {
        // 清 React Query 缓存：登出走 SPA 跳转不刷新页面，不清会把上一个人的
        // 列表/仪表盘/角色下拉带给下一个登录的人（2026-09-10 体检发现）
        queryClient.clear();
        set({
          token: null,
          authMode: null,
          authEpoch: get().authEpoch + 1,
          authExitReason: reason ?? get().authExitReason,
          oidcExpiresAt: null,
          pmDelegated: false,
          user: null,
          permissions: new Set(),
          isAdmin: false,
          userAdminScope: null,
        });
      },

      hasPermission: (perm) => {
        const state = get();
        if (state.isAdmin) return true;
        return state.permissions.has(perm);
      },

      hasAnyReadPermission: () => {
        const state = get();
        if (state.isAdmin) return true;
        return DOMAIN_READ_PERMISSIONS.some((p) => state.permissions.has(p));
      },

      clearMustChangePassword: () => {
        const user = get().user;
        if (!user?.must_change_password) return;
        set({ user: { ...user, must_change_password: false } });
      },
    }),
    {
      name: 'cmab-auth', // 仅作 persist 标识；真正落盘的 key 见上方 unifiedStorage
      storage: createJSONStorage(() => unifiedStorage),
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        // 恢复时重建 Set
        if (state?.user) {
          state.authMode = state.token ? 'native' : null;
          state.permissions = new Set(state.user.permissions);
          state.isAdmin = state.user.roles.includes('SYS_ADMIN');
          state.userAdminScope = computeUserAdminScope(state.user);
        }
      },
    }
  )
);
