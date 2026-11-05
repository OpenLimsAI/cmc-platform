import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
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

test('the application brand uses the company identity and main-data subtitle', () => {
  const html = renderBrand();
  assert.match(html, />MBERP</);
  assert.match(html, /迈博药业 · 主数据/);
  assert.match(html, /alt="迈博药业"/);
  assert.doesNotMatch(html, /CMAB MDM Portal|favicon\.svg/);
});

test('the logo stays under the MDM base path and is an available PNG asset', () => {
  assert.match(renderBrand(), /src="\/mdm\/brand\/maibo-pharma-logo\.png"/);
  const bytes = readFileSync('/app/public/brand/maibo-pharma-logo.png');
  assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.ok(bytes.length > 1000);
});
