import { create } from "zustand";
import type { User } from "../api/auth";

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
  token: localStorage.getItem("token"),
  user: (() => {
    try {
      const s = localStorage.getItem("user");
      return s ? JSON.parse(s) : null;
    } catch {
      return null;
    }
  })(),

  setAuth: (token: string, user: User) => {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    set({ token, user });
  },

  clearAuth: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
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
    if (e.key !== "token") return;
    if (!e.newValue) {
      useAuthStore.setState({ token: null, user: null });
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    } else {
      useAuthStore.setState({ token: e.newValue });
    }
  });
}
