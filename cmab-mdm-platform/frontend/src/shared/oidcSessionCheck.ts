import type { OidcSession } from './oidcTypes';
import { authResultIsCurrent, type AuthExitReason } from './oidcPolicy';

export interface SessionCheckContext {
  authEpoch: number;
  authExitReason: AuthExitReason;
  userId: number | undefined;
  expiresAt: string | null;
}
export interface SessionCheckActions {
  context: () => SessionCheckContext;
  now: () => number;
  loadSession: () => Promise<OidcSession | null>;
  verified: (session: OidcSession, epoch: number) => void;
  unavailable: () => void;
  expired: () => void;
}

/** Uncertainty suspends operations; only verified expiry/refusal ends authentication. */
export async function checkOidcSession(actions: SessionCheckActions): Promise<void> {
  const context = actions.context();
  if (context.authExitReason) return;
  const current = () => {
    const latest = actions.context();
    return authResultIsCurrent(context.authEpoch, latest.authEpoch, latest.authExitReason);
  };
  const expired = () => {
    const deadline = Date.parse(context.expiresAt ?? '');
    return !Number.isFinite(deadline) || deadline <= actions.now();
  };
  if (expired()) { if (current()) actions.expired(); return; }
  try {
    const session = await actions.loadSession();
    if (!current()) return;
    if (!session || session.user.user_id !== context.userId
      || !Number.isFinite(Date.parse(session.expires_at))
      || Date.parse(session.expires_at) <= actions.now() || expired()) actions.expired();
    else actions.verified(session, context.authEpoch);
  } catch (error) {
    if (!current()) return;
    const status = (error as {response?: {status?: number}} | null)?.response?.status;
    if (expired() || status === 401 || status === 403 || status === 423) actions.expired();
    else actions.unavailable();
  }
}

export function maySendBusinessWrite(mode: 'native' | 'oidc' | null, unavailable: boolean, method?: string): boolean {
  return mode !== 'oidc' || !unavailable || ['get', 'head', 'options'].includes((method ?? 'get').toLowerCase());
}
