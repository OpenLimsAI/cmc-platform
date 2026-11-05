import axios from 'axios';
import { BASE } from '@/shared/base';
import { safeAuthReturnTo } from '@/shared/oidcPolicy';
import type { OidcConfig, OidcLogout, OidcSession } from '@/shared/oidcTypes';

// This client never adds the native bearer and never invokes native refresh.
const sessionClient = axios.create({ baseURL: `${BASE}/api/v1/auth/oidc`, withCredentials: true, timeout: 15000 });
export interface SignatureChallenge { challenge_id: string; state: string; authorization_url: string; issuer_origin: string; expires_at: string }
export const oidcApi = {
  config: async (): Promise<OidcConfig> => (await sessionClient.get('/config')).data.data,
  session: async (): Promise<OidcSession | null> => {
    try { return (await sessionClient.get('/session')).data.data; }
    catch (error) { if (axios.isAxiosError(error) && error.response?.status === 401) return null; throw error; }
  },
  logout: async (global: boolean, device = false): Promise<OidcLogout> => (await sessionClient.post('/logout', { global, ...(device ? {device} : {}) })).data.data,
  beginSignature: async (body: {entity_type:string;entity_code:string;action:string;comment:string;reason:string}): Promise<SignatureChallenge> => (await sessionClient.post('/signatures',body)).data.data,
  completeSignature: async (id:string, result:{code:string;state:string}) => (await sessionClient.post(`/signatures/${encodeURIComponent(id)}/complete`,result)).data.data,
  cancelSignature: async (id:string) => (await sessionClient.post(`/signatures/${encodeURIComponent(id)}/cancel`)).data.data,
};

export function oidcLoginPath(returnTo: string | null, delegate = false): string {
  const target = safeAuthReturnTo(returnTo) ?? '/';
  return `${BASE}/api/v1/auth/oidc/${delegate ? 'pm-login' : 'login'}?return_to=${encodeURIComponent(target)}`;
}
