import type { OidcLogout } from './oidcTypes';

/** Only application paths; credentials and callback state never belong in return URLs. */
export function safeAuthReturnTo(raw: string | null): string | null {
  if (!raw || raw.length > 2048) return null;
  let path: string;
  try { path = decodeURIComponent(raw); } catch { return null; }
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return null;
  if (Array.from(path).some((ch) => ch.charCodeAt(0) < 32 || ch.charCodeAt(0) === 127)) return null;
  const url = new URL(path, 'https://mdm.invalid');
  if (url.origin !== 'https://mdm.invalid' || url.hash || path.split(/[?#]/)[0].split('/').some((p) => p === '.' || p === '..')) return null;
  if (['/login', '/auth-complete', '/api/', '/profile/password'].some((p) => url.pathname.startsWith(p))) return null;
  const forbidden = ['access_token', 'id_token', 'refresh_token', 'token', 'code', 'state', 'client_secret', 'cookie'];
  if (Array.from(url.searchParams.keys()).some((key) => forbidden.includes(key.toLowerCase()))) return null;
  return path;
}

/** A server operation wins after an interrupted request; retry never invents another key. */
export function stableCreateRequestId(serverId: string | null, browserId: string | null, generate: () => string): string {
  return serverId || browserId || generate();
}

export function hasUiSession(token: string | null, mode: 'native' | 'oidc' | null, hasUser: boolean): boolean {
  return hasUser && (mode === 'oidc' || (mode === 'native' && !!token));
}

function providerLogoutUrl(raw: string, expectedLoginUrl: string): string | null {
  if (raw.length > 4096 || raw.includes('\\') || Array.from(raw).some((c) => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127)) return null;
  try {
    const url = new URL(raw);
    const loopback = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) return null;
    if (url.username || url.password || url.hash || url.pathname !== '/api/logout') return null;
    const query = url.searchParams;
    if (Array.from(query.keys()).some((key) => !['client_id', 'post_logout_redirect_uri'].includes(key))) return null;
    if (query.getAll('client_id').length !== 1 || !/^[A-Za-z0-9_.-]{1,128}$/.test(query.get('client_id') ?? '')) return null;
    if (query.getAll('post_logout_redirect_uri').length !== 1 || query.get('post_logout_redirect_uri') !== expectedLoginUrl) return null;
    return url.href;
  } catch { return null; }
}

export function oidcLogoutPlan(result: OidcLogout, requestedGlobal: boolean, expectedLoginUrl: string): { providerUrl: string | null; warning: string | null } {
  const candidate = requestedGlobal && result.global_logout ? result.logout_url : undefined;
  const providerUrl = candidate ? providerLogoutUrl(candidate, expectedLoginUrl) : null;
  let warning = result.warning || null;
  if (!warning && requestedGlobal && !result.global_logout) warning = 'MDM 已退出，但统一身份注销尚未确认，其他应用可能仍保持登录。';
  if (!warning && candidate && !providerUrl) warning = 'MDM 已退出，但浏览器注销地址未通过安全检查，未打开外部地址。';
  return { providerUrl, warning };
}

interface LogoutActions {
  clearLocal: () => void;
  navigateLocal: () => void;
  navigateProvider: (url: string) => void;
  warn: (text: string, acknowledge: () => void) => void;
}

/** A warning is acknowledged before clearing state: protected routing must not hide it. */
export function completeOidcLogout(result: OidcLogout, requestedGlobal: boolean, expectedLoginUrl: string, actions: LogoutActions): boolean {
  if (!result.local_logout) return false;
  const plan = oidcLogoutPlan(result, requestedGlobal, expectedLoginUrl);
  const finish = () => {
    actions.clearLocal();
    if (plan.providerUrl) actions.navigateProvider(plan.providerUrl);
    else actions.navigateLocal();
  };
  if (plan.warning) actions.warn(plan.warning, finish);
  else finish();
  return true;
}
