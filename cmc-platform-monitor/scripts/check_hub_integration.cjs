// 本地实际Hub代码的纯显隐规则验证；不登录或写MDM。
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../cmab-hub/frontend');
const ts = require(root + '/node_modules/typescript');
function load(file) {
  const exports = {};
  const source = fs.readFileSync(file, 'utf8');
  const output = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
  vm.runInNewContext(output, {exports});
  return exports;
}
const apps = load(root + '/src/config/apps.ts').HUB_APPS;
const canAccess = load(root + '/src/auth/access.ts').canAccess;
const ops = apps.find(app => app.id === 'ops');
assert(ops);
assert.equal(ops.path, '/ops/');
assert.deepEqual(Array.from(ops.requires), ['SYS_ADMIN']);
assert.equal(canAccess(ops, null), false);
for (const roles of [[], ['DEPT_ADMIN'], ['CMC_USP_MANAGER'], ['QA_REVIEWER'], ['DISPLAY_MODE']]) {
  assert.equal(canAccess(ops, {roles, permissions:['system:config'], department:'CMC', username:'admin'}), false);
}
assert.equal(canAccess(ops, {roles:['SYS_ADMIN'], username:'someone-else'}), true);
assert.equal(apps[9].id, 'water'); // 保留负责人指定的第三行第二格。
assert(fs.readFileSync(root + '/src/pages/HubPage.tsx','utf8').includes("locked={mustChangePassword && a.id !== 'mdm'}"));
assert.equal(fs.readFileSync(root + '/src/shared/cmabSession.ts','utf8'), fs.readFileSync(path.resolve(__dirname, '../frontend/src/shared/cmabSession.ts'),'utf8'));
console.log('PASS: SYS_ADMIN only; other roles and anonymous denied; no username bypass; temporary-password lock and shared session retained');
