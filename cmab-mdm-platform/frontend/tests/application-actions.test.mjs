import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { buildSync } = require(createRequire(require.resolve('vite')).resolve('esbuild'));
mkdirSync('/tmp/mdm-application-actions-tests', { recursive: true });
buildSync({ stdin: { contents: `import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {StaticRouter} from 'react-router-dom/server';
import {ApplicationActions} from './src/shared/layouts/ApplicationActions';
export function renderActions(path) { return renderToStaticMarkup(
  <StaticRouter basename="/mdm" location={path}>
    <ApplicationActions><button>测试同事</button></ApplicationActions>
  </StaticRouter>); }`, resolveDir: '/app', loader: 'tsx' },
  outfile: '/tmp/mdm-application-actions-tests/actions.cjs',
  define: { 'import.meta.env.BASE_URL': JSON.stringify('/mdm/') },
  bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', logLevel: 'silent' });
const { renderActions } = require('/tmp/mdm-application-actions-tests/actions.cjs');

test('the header shows labeled feedback, workspace and account actions in order', () => {
  const html = renderActions('/mdm/projects');
  assert.match(html, /<span>回音壁<\/span>/);
  assert.match(html, /<span>工作台<\/span>/);
  assert.ok(html.indexOf('mdm-feedback-link') < html.indexOf('mdm-workbench-link'));
  assert.ok(html.indexOf('mdm-workbench-link') < html.indexOf('测试同事'));
  assert.doesNotMatch(html, /切换主题|mdm-theme-toggle/);
  assert.match(html, /href="\/" aria-label="应用工作台"/);
  assert.match(html, /target="_blank" rel="noopener noreferrer"/);
});

test('feedback carries the MDM page and omits query and auth fragments', () => {
  const html = renderActions('/mdm/projects?access_token=private#auth-code');
  assert.match(html, /application=mdm/);
  assert.match(html, /source_path=%2Fmdm%2Fprojects/);
  assert.doesNotMatch(html, /private|auth-code|access_token/);
});
