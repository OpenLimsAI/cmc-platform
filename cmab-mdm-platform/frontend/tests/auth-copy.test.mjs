import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {buildSync}=require(createRequire(require.resolve('vite')).resolve('esbuild'));
buildSync({entryPoints:['/app/src/shared/authCopy.ts'],outfile:'/tmp/auth-copy.mjs',bundle:true,platform:'node',format:'esm'});
const {authCopy}=await import('/tmp/auth-copy.mjs');

test('login and signature explanatory copy never exposes provider or component names',()=>{
  for(const text of Object.values(authCopy)) {
    assert.equal(typeof text,'string');
    assert.doesNotMatch(text,/casdoor|\bmdm\b/i);
  }
});

test('the UI names unified login and requires a fresh password verification for signing',()=>{
  assert.equal(authCopy.loginButton,'统一身份登录');
  assert.match(authCopy.loginNotice,/签名时需重新验证密码/);
  assert.equal(authCopy.signatureButton,'重新验证密码');
  assert.match(authCopy.signatureNotice,/统一身份验证页面/);
});
