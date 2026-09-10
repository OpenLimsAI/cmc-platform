import { create } from 'zustand';
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware';
import type { LoginResponseUser } from '@/api/types';

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

function computeUserAdminScope(user: LoginResponseUser | null): UserAdminScope {
  if (!user) return null;
  if (user.roles.includes('SYS_ADMIN') || user.permissions.includes('user:manage')) return 'all';
  if (user.roles.includes('DEPT_ADMIN')) return 'department';
  return null;
}

interface AuthState {
  token: string | null;
  user: LoginResponseUser | null;
  permissions: Set<string>;
  isAdmin: boolean;
  userAdminScope: UserAdminScope;

  setAuth: (token: string, user: LoginResponseUser) => void;
  updateToken: (token: string) => void;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      permissions: new Set(),
      isAdmin: false,
      userAdminScope: null,

      setAuth: (token, user) => {
        set({
          token,
          user,
          permissions: new Set(user.permissions),
          isAdmin: user.roles.includes('SYS_ADMIN'),
          userAdminScope: computeUserAdminScope(user),
        });
      },

      // P4.B：refresh 路径只更新 access token，权限/用户信息保持
      updateToken: (token) => {
        set({ token });
      },

      logout: () => {
        set({
          token: null,
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
          state.permissions = new Set(state.user.permissions);
          state.isAdmin = state.user.roles.includes('SYS_ADMIN');
          state.userAdminScope = computeUserAdminScope(state.user);
        }
      },
    }
  )
);
