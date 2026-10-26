import axios from 'axios';
import { BASE } from '@/shared/base';
import { safeAuthReturnTo } from '@/shared/oidcPolicy';
import type { OidcConfig, OidcLogout, OidcSession } from '@/shared/oidcTypes';

// This client never adds the native bearer and never invokes native refresh.
const sessionClient = axios.create({ baseURL: `${BASE}/api/v1/auth/oidc`, withCredentials: true, timeout: 15000 });
export const oidcApi = {
  config: async (): Promise<OidcConfig> => (await sessionClient.get('/config')).data.data,
  session: async (): Promise<OidcSession | null> => {
    try { return (await sessionClient.get('/session')).data.data; }
    catch (error) { if (axios.isAxiosError(error) && error.response?.status === 401) return null; throw error; }
  },
  logout: async (global: boolean): Promise<OidcLogout> => (await sessionClient.post('/logout', { global })).data.data,
};

export function oidcLoginPath(returnTo: string | null, delegate = false): string {
  const target = safeAuthReturnTo(returnTo) ?? '/';
  return `${BASE}/api/v1/auth/oidc/${delegate ? 'pm-login' : 'login'}?return_to=${encodeURIComponent(target)}`;
}
