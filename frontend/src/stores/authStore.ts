import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LoginResponseUser } from '@/api/types';

interface AuthState {
  token: string | null;
  user: LoginResponseUser | null;
  permissions: Set<string>;
  isAdmin: boolean;

  setAuth: (token: string, user: LoginResponseUser) => void;
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

      setAuth: (token, user) => {
        set({
          token,
          user,
          permissions: new Set(user.permissions),
          isAdmin: user.roles.includes('SYS_ADMIN'),
        });
      },

      logout: () => {
        set({ token: null, user: null, permissions: new Set(), isAdmin: false });
      },

      hasPermission: (perm) => {
        const state = get();
        if (state.isAdmin) return true;
        return state.permissions.has(perm);
      },
    }),
    {
      name: 'cmab-mdm-auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        // 恢复时重建 Set
        if (state?.user) {
          state.permissions = new Set(state.user.permissions);
          state.isAdmin = state.user.roles.includes('SYS_ADMIN');
        }
      },
    }
  )
);
