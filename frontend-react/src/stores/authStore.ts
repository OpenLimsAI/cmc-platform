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
