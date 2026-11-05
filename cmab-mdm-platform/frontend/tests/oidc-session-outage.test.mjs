import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { buildSync } = require(createRequire(require.resolve('vite')).resolve('esbuild'));
mkdirSync('/tmp/mdm-session-outage-tests', { recursive: true });
buildSync({ entryPoints:['/app/src/shared/oidcSessionCheck.ts'], outfile:'/tmp/mdm-session-outage-tests/check.mjs',
  bundle:true, platform:'node', format:'esm', logLevel:'silent' });
const { checkOidcSession, maySendBusinessWrite } = await import('/tmp/mdm-session-outage-tests/check.mjs');

function fixture() {
  const now=Date.parse('2030-01-01T00:00:00Z');
  const context={authEpoch:7,authExitReason:null,userId:29,expiresAt:new Date(now+60000).toISOString()};
  const session={user:{user_id:29},expires_at:context.expiresAt,pm_delegated:false};
  const calls=[];
  const draft={reason:'unsent business reason',signatureReason:'unsent signature intention'};
  const deps={context:()=>context,now:()=>now,loadSession:async()=>session,
    verified:(value,epoch)=>calls.push(['verified',value.user.user_id,epoch]),
    unavailable:()=>calls.push(['unavailable']),expired:()=>calls.push(['expired'])};
  return {context,session,calls,draft,deps};
}

test('502 suspends operations without expiring identity or discarding the business draft; successful retry restores same session',async()=>{
  const f=fixture();
  f.deps.loadSession=async()=>{throw {response:{status:502}};};
  await checkOidcSession(f.deps);
  assert.deepEqual(f.calls,[['unavailable']]);
  assert.equal(f.context.authExitReason,null);
  assert.equal(f.draft.reason,'unsent business reason');
  f.deps.loadSession=async()=>f.session;
  await checkOidcSession(f.deps);
  assert.deepEqual(f.calls,[['unavailable'],['verified',29,7]]);
});
test('network errors and 503 remain unavailable, never interpreted as a successful check',async()=>{
  for(const error of [new Error('network unavailable'),{response:{status:503}}]) {
    const f=fixture();f.deps.loadSession=async()=>{throw error;};
    await checkOidcSession(f.deps);assert.deepEqual(f.calls,[['unavailable']]);
  }
});
test('real unauthenticated response and disabled/locked account remain terminal refusals',async()=>{
  const missing=fixture();missing.deps.loadSession=async()=>null;
  await checkOidcSession(missing.deps);assert.deepEqual(missing.calls,[['expired']]);
  for(const status of [401,403,423]) {
    const f=fixture();f.deps.loadSession=async()=>{throw {response:{status}};};
    await checkOidcSession(f.deps);assert.deepEqual(f.calls,[['expired']]);
  }
});
test('authoritative session expiry still refuses access during an outage, without unbounded grace',async()=>{
  const f=fixture();f.context.expiresAt='2029-12-31T23:59:59Z';
  f.deps.loadSession=async()=>{throw {response:{status:502}};};
  await checkOidcSession(f.deps);assert.deepEqual(f.calls,[['expired']]);
});
test('logout or a newer auth context fences all late successful and failed probes',async()=>{
  for(const failure of [false,true]) {
    const f=fixture();
    f.deps.loadSession=async()=>{f.context.authEpoch++;f.context.authExitReason='logout';
      if(failure)throw new Error('offline');return f.session;};
    await checkOidcSession(f.deps);assert.deepEqual(f.calls,[]);
  }
});
test('a recovered different account cannot inherit an existing user business form',async()=>{
  const f=fixture();f.deps.loadSession=async()=>({...f.session,user:{user_id:88}});
  await checkOidcSession(f.deps);assert.deepEqual(f.calls,[['expired']]);
});
test('uncertain OIDC sessions cannot send business writes, without changing native compatibility',()=>{
  for(const method of ['POST','patch','PUT','DELETE']) assert.equal(maySendBusinessWrite('oidc',true,method),false);
  assert.equal(maySendBusinessWrite('oidc',true,'GET'),true);
  assert.equal(maySendBusinessWrite('oidc',false,'POST'),true);
  assert.equal(maySendBusinessWrite('native',true,'POST'),true);
});
