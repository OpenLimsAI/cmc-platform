import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { buildSync } = require(createRequire(require.resolve('vite')).resolve('esbuild'));
buildSync({entryPoints:['/app/src/shared/signatureMessage.ts'],outfile:'/tmp/signature-message.mjs',bundle:true,platform:'node',format:'esm'});
const { signatureMessage } = await import('/tmp/signature-message.mjs');

test('only the current signing frame and exact issuer origin may complete its state', () => {
  const frame = {};
  const context = { origin:'http://localhost:19081', source:frame, state:'synthetic-state' };
  const data = {type:'loginSuccess',data:{code:'synthetic-code',state:context.state}};
  assert.deepEqual(signatureMessage({origin:context.origin,source:frame,data},context),data.data);
  assert.equal(signatureMessage({origin:'http://evil.invalid',source:frame,data},context),null);
  assert.equal(signatureMessage({origin:context.origin,source:{},data},context),null);
  assert.equal(signatureMessage({origin:context.origin,source:frame,data:{...data,data:{...data.data,state:'stale'}}},context),null);
});
