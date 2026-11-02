import assert from 'node:assert/strict';
import { test, beforeEach } from 'node:test';
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';

const require = createRequire(import.meta.url);
const { buildSync } = require(createRequire(require.resolve('vite')).resolve('esbuild'));
const target = '/tmp/mdm-phase2-ui-tests';
mkdirSync(target, { recursive: true });
function bundle(source, name) {
  const outfile = `${target}/${name}.mjs`;
  buildSync({ entryPoints: [`/app/src/${source}`], outfile, bundle: true, platform: 'node', format: 'esm',
    alias: { '@': '/app/src' }, define: { 'import.meta.env.BASE_URL': '"/mdm/"' }, logLevel: 'silent' });
  return import(outfile);
}
const items = new Map();
globalThis.localStorage = { getItem: (key) => items.get(key) ?? null, setItem: (key, value) => items.set(key, value), removeItem: (key) => items.delete(key) };
const { useAuthStore } = await bundle('stores/authStore.ts', 'auth-store');
const user = { user_id: 29, username: 'isolated-reader', full_name: '隔离只读用户', roles: [], permissions: ['project:read'] };
beforeEach(() => { useAuthStore.getState().logout(); useAuthStore.getState().setOidcConfig(false, true); items.clear(); });

test('SSO-only password change clearly separates signing credential from Casdoor login', async () => {
  const { passwordChangeText } = await bundle('shared/passwordChangeText.ts', 'password-change-sso');
  const text = passwordChangeText('oidc', false);
  assert.match(text.heading, /签名/);
  assert.match(text.description, /不能用于登录/);
  assert.match(text.description, /Casdoor/);
  assert.match(text.success, /Casdoor/);
  assert.doesNotMatch(text.success, /用新密码重新登录/);
  assert.match(text.loginNotice, /Casdoor/);
});

test('native and opt-in compatible deployments retain truthful password wording', async () => {
  const { passwordChangeText } = await bundle('shared/passwordChangeText.ts', 'password-change-compatible');
  const native = passwordChangeText('native', true);
  assert.equal(native.heading, '修改密码');
  assert.match(native.success, /用新密码重新登录/);
  const compatible = passwordChangeText('oidc', true);
  assert.doesNotMatch(compatible.description, /不能用于登录/);
  assert.match(compatible.success, /Casdoor/);
});

test('SSO-only configuration discards legacy native identity and persisted credentials', () => {
  useAuthStore.getState().setAuth('synthetic-native-token', { ...user, roles: ['SYS_ADMIN'] });
  useAuthStore.getState().setOidcConfig(true, false);
  const state = useAuthStore.getState();
  assert.equal(state.token, null);
  assert.equal(state.authMode, null);
  assert.equal(state.user, null);
  assert.equal(state.hasPermission('project:read'), false);
  assert.equal(state.isAdmin, false);
  assert.equal(items.has('cmab_access_token'), false);
  assert.equal(items.has('cmab_user'), false);
});

test('SSO-only cannot be bypassed by a late native login or refresh result', () => {
  useAuthStore.getState().setOidcConfig(true, false);
  useAuthStore.getState().setAuth('synthetic-late-native', user);
  useAuthStore.getState().updateToken('synthetic-late-refresh');
  assert.equal(useAuthStore.getState().authMode, null);
  assert.equal(useAuthStore.getState().token, null);
  assert.equal(items.has('cmab_access_token'), false);
});

test('SSO-only ignores the native query override and restores the real cookie identity', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-only-bootstrap');
  let reads = 0;
  await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: false }), async () => {
    reads += 1;
    return { mode: 'oidc', user, expires_at: '2030-01-01T00:00:00Z', pm_delegated: true };
  }, useAuthStore.getState(), true);
  assert.equal(reads, 1);
  assert.equal(useAuthStore.getState().authMode, 'oidc');
});

test('SSO-only bootstraps a verified cookie after clearing an old native account', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-only-restore');
  useAuthStore.getState().setAuth('synthetic-native-token', { ...user, user_id: 99 });
  await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: false }), async () => (
    { mode: 'oidc', user, expires_at: '2030-01-01T00:00:00Z', pm_delegated: false }
  ), useAuthStore.getState());
  assert.equal(useAuthStore.getState().authMode, 'oidc');
  assert.equal(useAuthStore.getState().user.user_id, 29);
  assert.equal(useAuthStore.getState().token, null);
});

test('unavailable SSO never falls back to a cached local account', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-only-unavailable');
  useAuthStore.getState().setAuth('synthetic-native-token', user);
  await restoreOidcAuth(async () => ({ enabled: false, native_login_enabled: false }), async () => null, useAuthStore.getState());
  assert.equal(useAuthStore.getState().authMode, null);
  assert.equal(useAuthStore.getState().token, null);
});

test('native login presentation requires explicit deployment permission', async () => {
  const { nativeLoginSelected } = await bundle('shared/oidcPolicy.ts', 'native-presentation-policy');
  assert.equal(nativeLoginSelected(true, false, true), false);
  assert.equal(nativeLoginSelected(false, false, false), false);
  assert.equal(nativeLoginSelected(false, true, false), true);
  assert.equal(nativeLoginSelected(true, true, true), true);
  assert.equal(nativeLoginSelected(true, true, false), false);
});

test('OIDC establishes cookie mode without a fake token or persisted identity', () => {
  useAuthStore.getState().setAuth('synthetic-native-token', user);
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', false);
  const state = useAuthStore.getState();
  assert.equal(state.authMode, 'oidc');
  assert.equal(state.token, null);
  assert.equal(state.user.user_id, 29);
  assert.equal(state.hasPermission('project:read'), true);
  assert.equal(state.hasPermission('project:update'), false);
  assert.equal(items.has('cmab_access_token'), false);
  assert.equal(items.has('cmab_user'), false);
});

test('server permission updates replace the OIDC UI authority immediately', () => {
  useAuthStore.getState().setOidcSession({ ...user, roles: ['SYS_ADMIN'] }, '2030-01-01T00:00:00Z', true);
  assert.equal(useAuthStore.getState().isAdmin, true);
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', false);
  assert.equal(useAuthStore.getState().isAdmin, false);
  assert.equal(useAuthStore.getState().pmDelegated, false);
  assert.equal(useAuthStore.getState().hasPermission('project:update'), false);
});

test('explicit native login retains legacy storage compatibility and clears cookie-mode metadata', () => {
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', true);
  useAuthStore.getState().setAuth('synthetic-native-token', user);
  assert.equal(useAuthStore.getState().authMode, 'native');
  assert.equal(useAuthStore.getState().oidcExpiresAt, null);
  assert.equal(items.get('cmab_access_token'), 'synthetic-native-token');
  assert.equal(JSON.parse(items.get('cmab_user')).user_id, 29);
});

test('logout clears both auth modes and role-derived UI state', () => {
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', true);
  useAuthStore.getState().logout();
  assert.equal(useAuthStore.getState().authMode, null);
  assert.equal(useAuthStore.getState().user, null);
  assert.equal(useAuthStore.getState().hasPermission('project:read'), false);
});

test('return paths preserve a project context but reject credentials and external navigation', async () => {
  const { safeAuthReturnTo } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  assert.equal(safeAuthReturnTo('/projects/CMAB-PRJ-2026-0001?tab=pm'), '/projects/CMAB-PRJ-2026-0001?tab=pm');
  for (const input of ['//evil.invalid', 'https://evil.invalid', '/\\evil.invalid', '/%2f%2fevil.invalid', '/projects?access_token=secret', '/projects?code=credential', '/projects#access_token=secret', '/auth-complete', '/login', '/profile/password', '/a/../projects', '/api/v1/auth/logout', '/projects%0d%0aLocation:evil']) {
    assert.equal(safeAuthReturnTo(input), null, input);
  }
});

test('creation retry identity reuses an existing request instead of making a new project', async () => {
  const { stableCreateRequestId } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  let generated = 0;
  const next = () => { generated += 1; return 'new-operation'; };
  assert.equal(stableCreateRequestId('server-operation', 'browser-operation', next), 'server-operation');
  assert.equal(stableCreateRequestId(null, 'browser-operation', next), 'browser-operation');
  assert.equal(generated, 0);
  assert.equal(stableCreateRequestId(null, null, next), 'new-operation');
  assert.equal(generated, 1);
});

test('feature-off bootstrap preserves native mode without querying an OIDC session', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-bootstrap');
  useAuthStore.getState().setAuth('synthetic-native-token', user);
  let reads = 0;
  await restoreOidcAuth(async () => ({ enabled: false, native_login_enabled: true }), async () => { reads += 1; return null; }, useAuthStore.getState());
  assert.equal(reads, 0);
  assert.equal(useAuthStore.getState().authMode, 'native');
  assert.equal(useAuthStore.getState().bootstrapPending, false);
});

test('bootstrap restores only server-verified cookie identity and delegation status', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-bootstrap');
  await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: true }), async () => ({ mode: 'oidc', user, expires_at: '2030-01-01T00:00:00Z', pm_delegated: true }), useAuthStore.getState());
  assert.equal(useAuthStore.getState().authMode, 'oidc');
  assert.equal(useAuthStore.getState().pmDelegated, true);
  assert.equal(items.has('cmab_access_token'), false);
});

test('bootstrap network failure stays explicit instead of guessing native recovery is enabled', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-bootstrap');
  await restoreOidcAuth(async () => { throw new Error('provider failure'); }, async () => null, useAuthStore.getState());
  assert.equal(useAuthStore.getState().bootstrapPending, false);
  assert.equal(typeof useAuthStore.getState().bootstrapError, 'string');
  assert.equal(useAuthStore.getState().authMode, null);
});

test('expired SSO signing bootstrap explains the real 40308 refusal without granting a session', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'expired-signing-bootstrap');
  useAuthStore.getState().setAuth('synthetic-old-native', { ...user, roles: ['SYS_ADMIN'] });
  await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: false }), async () => {
    throw { response: { status: 403, data: { code: 40308, message: 'untrusted server wording' } } };
  }, useAuthStore.getState());
  const state = useAuthStore.getState();
  assert.equal(state.bootstrapPending, false);
  assert.match(state.bootstrapError, /签名密码已过期/);
  assert.match(state.bootstrapError, /安全渠道/);
  assert.doesNotMatch(state.bootstrapError, /untrusted server wording|无法确认当前登录配置/);
  assert.equal(state.authMode, null);
  assert.equal(state.user, null);
  assert.equal(state.isAdmin, false);
  assert.equal(state.nativeLoginEnabled, false);
  assert.equal(items.has('cmab_access_token'), false);
});

test('compatible OIDC deployment describes its expired MDM password without claiming signing-only use', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'expired-compatible-bootstrap');
  await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: true }), async () => {
    throw { response: { status: 403, data: { code: 40308 } } };
  }, useAuthStore.getState());
  assert.match(useAuthStore.getState().bootstrapError, /MDM 临时密码已过期/);
  assert.doesNotMatch(useAuthStore.getState().bootstrapError, /签名密码|不能用于登录/);
  assert.equal(useAuthStore.getState().authMode, null);
});

test('configuration errors cannot be mislabelled as an expired authenticated signing bootstrap', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'config-error-not-expiry');
  let sessionReads = 0;
  await restoreOidcAuth(async () => {
    throw { response: { status: 403, data: { code: 40308 } } };
  }, async () => { sessionReads += 1; return null; }, useAuthStore.getState());
  assert.equal(sessionReads, 0);
  assert.match(useAuthStore.getState().bootstrapError, /无法确认当前登录配置或会话/);
  assert.equal(useAuthStore.getState().authMode, null);
});

test('other session failures and lookalike expiry responses retain the fail-closed generic notice', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'unknown-session-errors');
  for (const error of [
    { response: { status: 403, data: { code: 40307 } } },
    { response: { status: 500, data: { code: 40308 } } },
    { response: { status: 403, data: { code: '40308' } } },
    new Error('temporary_password_expired'),
    null,
  ]) {
    await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: false }), async () => {
      throw error;
    }, useAuthStore.getState());
    assert.match(useAuthStore.getState().bootstrapError, /无法确认当前登录配置或会话/);
    assert.equal(useAuthStore.getState().authMode, null);
    assert.equal(useAuthStore.getState().user, null);
    assert.equal(useAuthStore.getState().nativeLoginEnabled, false);
  }
});

test('native recovery remains reachable even if a stale OIDC cookie cannot be restored', async () => {
  const { restoreOidcAuth } = await bundle('shared/oidcBootstrap.ts', 'oidc-bootstrap');
  let reads = 0;
  await restoreOidcAuth(async () => ({ enabled: true, native_login_enabled: true }), async () => { reads += 1; throw new Error('stale cookie'); }, useAuthStore.getState(), true);
  assert.equal(reads, 0);
  assert.equal(useAuthStore.getState().bootstrapError, null);
});

test('cookie mode counts as authenticated for routing and safe app-update prompts', async () => {
  const { hasUiSession } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  assert.equal(hasUiSession(null, 'oidc', true), true);
  assert.equal(hasUiSession('synthetic-native-token', 'native', true), true);
  assert.equal(hasUiSession(null, 'oidc', false), false);
  assert.equal(hasUiSession(null, null, false), false);
});

test('live non-admin permission changes notify existing permission-function selectors', () => {
  useAuthStore.getState().setOidcSession({ ...user, permissions: ['project:read', 'project:update'] }, '2030-01-01T00:00:00Z', true);
  const previousCheck = useAuthStore.getState().hasPermission;
  let selectorChanged = false;
  const unsubscribe = useAuthStore.subscribe((state, previous) => { selectorChanged ||= state.hasPermission !== previous.hasPermission; });
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', true);
  unsubscribe();
  assert.equal(selectorChanged, true);
  assert.notEqual(useAuthStore.getState().hasPermission, previousCheck);
  assert.equal(useAuthStore.getState().hasPermission('project:update'), false);
});

const logoutReturn = 'http://127.0.0.1:5188/mdm/login?reason=logout';
const providerLogout = 'http://127.0.0.1:8018/api/logout?client_id=isolated-mdm&post_logout_redirect_uri=' + encodeURIComponent(logoutReturn);

test('provider browser logout is followed only for confirmed requested global logout', async () => {
  const { oidcLogoutPlan } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const reply = { local_logout: true, global_logout: true, login_url: '/mdm/login?reason=logout', logout_url: providerLogout };
  assert.equal(oidcLogoutPlan(reply, true, logoutReturn).providerUrl, providerLogout);
  assert.equal(oidcLogoutPlan(reply, false, logoutReturn).providerUrl, null);
  assert.equal(oidcLogoutPlan({ ...reply, global_logout: false }, true, logoutReturn).providerUrl, null);
  assert.equal(oidcLogoutPlan({ ...reply, logout_url: undefined }, true, logoutReturn).providerUrl, null);
});

test('confirmed global logout may return exactly to the fixed local login without a warning or external navigation', async () => {
  const { oidcLogoutPlan, completeOidcLogout } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const reply = { local_logout: true, global_logout: true, login_url: '/mdm/login?reason=logout', logout_url: logoutReturn };
  assert.deepEqual(oidcLogoutPlan(reply, true, logoutReturn), { providerUrl: null, warning: null });
  const events = [];
  completeOidcLogout(reply, true, logoutReturn, {
    clearLocal: () => events.push('clear'), navigateLocal: () => events.push('login'),
    navigateProvider: () => events.push('provider'), warn: () => events.push('warning'),
  });
  assert.deepEqual(events, ['clear', 'login']);
});

test('local logout return requires byte-exact fixed URL and rejects extra, duplicate, credential and alternate destinations', async () => {
  const { oidcLogoutPlan } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  for (const bad of [logoutReturn + '&reason=logout', logoutReturn + '&token=synthetic', logoutReturn + '&access_token=synthetic',
    logoutReturn + '#token=synthetic', logoutReturn.replace('/login?', '/projects?'),
    logoutReturn.replace('127.0.0.1:5188', 'user:synthetic@127.0.0.1:5188'),
    logoutReturn.replace('127.0.0.1', 'localhost'), logoutReturn.replace('reason=logout', 'reason=%6Cogout')]) {
    const plan = oidcLogoutPlan({ local_logout: true, global_logout: true, login_url: '/mdm/login?reason=logout', logout_url: bad }, true, logoutReturn);
    assert.equal(plan.providerUrl, null, bad);
    assert.match(plan.warning, /安全检查/, bad);
  }
});

test('a fixed local logout return still displays an existing partial warning before navigation', async () => {
  const { completeOidcLogout } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const events = [];
  let acknowledge;
  completeOidcLogout({ local_logout: true, global_logout: false, login_url: '/mdm/login?reason=logout', logout_url: logoutReturn, warning: '部分应用注销未确认' }, true, logoutReturn, {
    clearLocal: () => events.push('clear'), navigateLocal: () => events.push('login'), navigateProvider: () => events.push('provider'),
    warn: (text, done) => { events.push(text); acknowledge = done; },
  });
  assert.deepEqual(events, ['部分应用注销未确认']);
  acknowledge();
  assert.deepEqual(events, ['部分应用注销未确认', 'clear', 'login']);
});

test('provider logout URL cannot carry credentials or change the local return destination', async () => {
  const { oidcLogoutPlan } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  for (const bad of [providerLogout + '&id_token_hint=synthetic', providerLogout + '#token=synthetic',
    providerLogout.replace('127.0.0.1:8018', 'user:synthetic@127.0.0.1:8018'),
    providerLogout.replace('127.0.0.1:8018', 'outside.invalid'),
    providerLogout.replace('/api/logout?', '/other?'),
    providerLogout.replace(encodeURIComponent(logoutReturn), encodeURIComponent('https://outside.invalid/login'))]) {
    assert.equal(oidcLogoutPlan({ local_logout: true, global_logout: true, login_url: '/mdm/login?reason=logout', logout_url: bad }, true, logoutReturn).providerUrl, null);
  }
});

test('partial logout warning is displayed and acknowledged before clearing local state or navigating', async () => {
  const { completeOidcLogout } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const events = [];
  let acknowledge;
  const shown = completeOidcLogout({ local_logout: true, global_logout: false, login_url: '/mdm/login?reason=logout', warning: '统一注销通知未完成', logout_url: providerLogout }, true, logoutReturn, {
    clearLocal: () => events.push('clear'), navigateLocal: () => events.push('login'), navigateProvider: () => events.push('provider'),
    warn: (text, done) => { events.push(text); acknowledge = done; },
  });
  assert.equal(shown, true);
  assert.deepEqual(events, ['统一注销通知未完成']);
  acknowledge();
  assert.deepEqual(events, ['统一注销通知未完成', 'clear', 'login']);
});

test('successful browser logout with a server warning waits for acknowledgement too', async () => {
  const { completeOidcLogout } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const events = [];
  let acknowledge;
  completeOidcLogout({ local_logout: true, global_logout: true, login_url: '/mdm/login?reason=logout', warning: '请核对其他应用注销结果', logout_url: providerLogout }, true, logoutReturn, {
    clearLocal: () => events.push('clear'), navigateLocal: () => events.push('login'), navigateProvider: (url) => events.push(url),
    warn: (text, done) => { events.push(text); acknowledge = done; },
  });
  assert.deepEqual(events, ['请核对其他应用注销结果']);
  acknowledge();
  assert.deepEqual(events, ['请核对其他应用注销结果', 'clear', providerLogout]);
});

test('an unconfirmed local logout does not clear or navigate', async () => {
  const { completeOidcLogout } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const events = [];
  const ok = completeOidcLogout({ local_logout: false, global_logout: false, login_url: '/mdm/login?reason=logout' }, true, logoutReturn, {
    clearLocal: () => events.push('clear'), navigateLocal: () => events.push('login'), navigateProvider: () => events.push('provider'), warn: () => events.push('warning'),
  });
  assert.equal(ok, false);
  assert.deepEqual(events, []);
});

test('a session response started before explicit logout cannot restore the old user', async () => {
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', true);
  const startedEpoch = useAuthStore.getState().authEpoch ?? 0;
  let resolveSession;
  const response = new Promise((resolve) => { resolveSession = resolve; });
  const pending = response.then((session) => useAuthStore.getState().setOidcSession(session.user, session.expires_at, session.pm_delegated, startedEpoch));
  useAuthStore.getState().logout('logout');
  resolveSession({ user, expires_at: '2030-01-01T00:00:00Z', pm_delegated: true });
  await pending;
  assert.equal(useAuthStore.getState().authMode, null);
  assert.equal(useAuthStore.getState().user, null);
  assert.equal(useAuthStore.getState().authExitReason, 'logout');
});

test('late 401 routing preserves an explicit logout and never creates an automatic SSO entry', async () => {
  const { authFailureLoginPath, shouldAutoStartOidc } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  const target = authFailureLoginPath('/projects/CMAB-PRJ-2026-0001', '?tab=pm', 'logout');
  const params = new URL(target, 'https://mdm.invalid').searchParams;
  assert.equal(params.get('reason'), 'logout');
  assert.equal(params.get('redirect'), '/projects/CMAB-PRJ-2026-0001?tab=pm');
  assert.equal(shouldAutoStartOidc(true, false, params.get('reason'), null), false);
  assert.equal(shouldAutoStartOidc(true, false, 'expired', null), false);
  assert.equal(shouldAutoStartOidc(true, false, null, null), true);
});

test('starting logout invalidates old responses while retaining the warning acknowledgement view', async () => {
  const { authResultIsCurrent } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  useAuthStore.getState().setOidcSession(user, '2030-01-01T00:00:00Z', true);
  const oldEpoch = useAuthStore.getState().authEpoch;
  const intent = useAuthStore.getState().beginLogout();
  assert.equal(useAuthStore.getState().user.user_id, user.user_id);
  assert.equal(authResultIsCurrent(oldEpoch, useAuthStore.getState().authEpoch, useAuthStore.getState().authExitReason), false);
  assert.equal(authResultIsCurrent(intent, intent, 'logout'), false);
  useAuthStore.getState().cancelLogout(intent);
  assert.equal(useAuthStore.getState().authExitReason, null);
  assert.equal(useAuthStore.getState().authMode, 'oidc');
});

test('only native mode may attempt native JWT refresh after an authentication failure', async () => {
  const { mayRefreshNative } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  assert.equal(mayRefreshNative('native', null), true);
  assert.equal(mayRefreshNative('oidc', null), false);
  assert.equal(mayRefreshNative(null, 'logout'), false);
  assert.equal(mayRefreshNative('native', 'logout'), false);
});

test('OIDC mapping, account and disabled-config errors have distinct safe explanations', async () => {
  const { oidcErrorNotice } = await bundle('shared/oidcPolicy.ts', 'oidc-policy');
  assert.match(oidcErrorNotice('mapping'), /关联|映射/);
  assert.match(oidcErrorNotice('account'), /用户.*禁用|用户.*锁定/);
  assert.match(oidcErrorNotice('disabled'), /环境.*启用/);
  assert.notEqual(oidcErrorNotice('account'), oidcErrorNotice('disabled'));
  assert.equal(oidcErrorNotice('unknown-untrusted-code').includes('unknown-untrusted-code'), false);
});
