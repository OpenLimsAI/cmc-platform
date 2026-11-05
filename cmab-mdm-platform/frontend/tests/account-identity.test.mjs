import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { buildSync } = require(createRequire(require.resolve('vite')).resolve('esbuild'));
mkdirSync('/tmp/mdm-account-tests', { recursive: true });
buildSync({ stdin: { contents: `import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {AccountIdentity} from './src/shared/layouts/AccountIdentity';
export function renderIdentity(user) { return renderToStaticMarkup(<AccountIdentity user={user}/>); }`,
  resolveDir: '/app', loader: 'tsx' }, outfile: '/tmp/mdm-account-tests/identity.cjs',
  bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', logLevel: 'silent' });
const { renderIdentity } = require('/tmp/mdm-account-tests/identity.cjs');

test('the account area shows the actual username and MDM business roles', () => {
  const html = renderIdentity({ username: 'synthetic.signer', full_name: '测试同事', roles: ['SYS_ADMIN', 'PROJECT_MANAGER'] });
  assert.match(html, /synthetic\.signer/);
  assert.match(html, /测试同事/);
  assert.match(html, /系统管理员/);
  assert.match(html, /项目经理/);
  assert.doesNotMatch(html, /Casdoor|原生登录|退出当前设备/);
});

test('unknown roles are displayed without inventing administrator privileges', () => {
  const html = renderIdentity({ username: 'synthetic.reader', full_name: '', roles: ['CUSTOM_READER'] });
  assert.match(html, /synthetic\.reader/);
  assert.match(html, /CUSTOM_READER/);
  assert.doesNotMatch(html, /系统管理员/);
});

test('missing identity or role does not display a privileged placeholder', () => {
  assert.match(renderIdentity(null), /未登录/);
  const html = renderIdentity({ username: 'synthetic.unassigned', roles: [] });
  assert.match(html, /未分配角色/);
  assert.doesNotMatch(html, /系统管理员/);
});

test('OIDC identity uses the same displayName as PM and keeps local user identity out of the visible name', () => {
  const html = renderIdentity({ username:'admin', full_name:'本地历史姓名', roles:['SYS_ADMIN'], identityUsername:'e2e.signer', displayName:'Synthetic signer' });
  assert.match(html, /Synthetic signer/);
  assert.doesNotMatch(html, /本地历史姓名|\(admin\)/);
  assert.match(html, /系统管理员/);
});

test('OIDC empty displayName falls back to the unified username rather than the local admin name', () => {
  for (const displayName of ['', '   ', undefined]) {
    const html = renderIdentity({ username:'admin', full_name:'本地历史姓名', roles:['READ_ONLY_USER'], identityUsername:'e2e.reader', displayName });
    assert.match(html, /e2e.reader/);
    assert.doesNotMatch(html, /本地历史姓名|\(admin\)/);
    assert.match(html, /只读用户/);
  }
});
