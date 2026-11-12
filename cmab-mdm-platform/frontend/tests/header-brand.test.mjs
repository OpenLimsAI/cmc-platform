import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { buildSync } = require(createRequire(require.resolve('vite')).resolve('esbuild'));
mkdirSync('/tmp/mdm-brand-tests', { recursive: true });
buildSync({ stdin: { contents: `import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {ApplicationBrand} from './src/shared/layouts/ApplicationBrand';
export function renderBrand() { return renderToStaticMarkup(<ApplicationBrand/>); }`,
  resolveDir: '/app', loader: 'tsx' }, outfile: '/tmp/mdm-brand-tests/brand.cjs',
  define: { 'import.meta.env.BASE_URL': JSON.stringify('/mdm/') },
  bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', logLevel: 'silent' });
const { renderBrand } = require('/tmp/mdm-brand-tests/brand.cjs');

test('the application brand identifies the Maibo main-data workspace', () => {
  const html = renderBrand();
  assert.match(html, /aria-label="迈博主数据管理"/);
  assert.match(html, />主数据管理</);
  assert.match(html, /MASTER DATA STUDIO/);
  assert.doesNotMatch(html, /CMAB MDM Portal|favicon\.svg/);
});

test('the application mark is decorative and does not introduce a second navigation target', () => {
  const html = renderBrand();
  assert.match(html, /class="mdm-app-mark"/);
  assert.match(html, /<svg[^>]*aria-hidden="true"/);
  assert.doesNotMatch(html, /<a\b|<button\b/);
});
