import { create } from "zustand";
import type { User } from "../api/auth";
import { TOKEN_KEY, USER_KEY, stripBase, withBase } from "../shared/base";

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;
  isLoggedIn: () => boolean;
  hasRole: (role: string) => boolean;
  canWrite: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_KEY),
  user: (() => {
    try {
      const s = localStorage.getItem(USER_KEY);
      return s ? JSON.parse(s) : null;
    } catch {
      return null;
    }
  })(),

  setAuth: (token: string, user: User) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, user });
  },

  clearAuth: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, user: null });
  },

  isLoggedIn: () => !!get().token && !!get().user,

  hasRole: (role: string) => get().user?.roles?.includes(role) ?? false,

  canWrite: () => {
    const roles = get().user?.roles ?? [];
    return roles.includes("SYS_ADMIN") || roles.includes("CMC_WAREHOUSE_ADMIN");
  },
}));

// 多标签页同步:其它标签登出/续期改了 localStorage 的 token,本标签 store 跟随。
// token 被清(别处登出)→本标签也清并回登录页;token 变化(别处续期)→同步新值。
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== TOKEN_KEY) return;
    if (!e.newValue) {
      useAuthStore.setState({ token: null, user: null });
      if (stripBase(window.location.pathname) !== "/login") {
        window.location.href = withBase("/login");
      }
    } else {
      useAuthStore.setState({ token: e.newValue });
    }
  });
}
