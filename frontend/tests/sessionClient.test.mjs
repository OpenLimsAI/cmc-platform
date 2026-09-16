import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import axios, { AxiosError } from 'axios'
import ts from 'typescript'

// 使用项目已有 TypeScript 编译器，不新增测试框架、不访问真实 MDM。
async function sourceModule(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
}

const { attachSessionInterceptors } = await sourceModule('../src/services/sessionClient.ts')

function rejection(config, status) {
  return new AxiosError(`status ${status}`, undefined, config, undefined, {
    status, statusText: String(status), config, headers: {}, data: {},
  })
}

function fixture(respond, refreshFails = false) {
  let token = 'synthetic-old-token'
  let refreshCount = 0
  let clearCount = 0
  const authorizations = []
  const client = axios.create({ adapter: async (config) => {
    authorizations.push(config.headers.get('Authorization'))
    const status = respond(authorizations.length)
    if (status !== 200) throw rejection(config, status)
    return { status, statusText: 'OK', config, headers: {}, data: { success: true } }
  } })
  attachSessionInterceptors(client, {
    getToken: () => token,
    refresh: async () => {
      refreshCount += 1
      if (refreshFails) throw new Error('synthetic refresh failure')
      token = 'synthetic-new-token'
      return token
    },
    clear: () => { token = null; clearCount += 1 },
  })
  return { client, authorizations, counts: () => ({ refreshCount, clearCount }) }
}

test('每次请求使用当前令牌，401 后只续期并重放一次', async () => {
  const f = fixture((attempt) => attempt === 1 ? 401 : 200)
  await f.client.post('/imports/preview', 'synthetic body')
  assert.deepEqual(f.authorizations, ['Bearer synthetic-old-token', 'Bearer synthetic-new-token'])
  assert.deepEqual(f.counts(), { refreshCount: 1, clearCount: 0 })
})

test('重放仍为 401 时清会话，不再循环续期', async () => {
  const f = fixture(() => 401)
  await assert.rejects(f.client.get('/auth/me'), (error) => error.response.status === 401)
  assert.equal(f.authorizations.length, 2)
  assert.deepEqual(f.counts(), { refreshCount: 1, clearCount: 1 })
})

test('403 临时密码或权限拒绝不续期，也不清除可供 MDM 改密码的会话', async () => {
  const f = fixture(() => 403)
  await assert.rejects(f.client.get('/auth/me'), (error) => error.response.status === 403)
  assert.equal(f.authorizations.length, 1)
  assert.deepEqual(f.counts(), { refreshCount: 0, clearCount: 0 })
})

test('续期失败清会话且不重放请求', async () => {
  const f = fixture(() => 401, true)
  await assert.rejects(f.client.get('/imports/capabilities'))
  assert.equal(f.authorizations.length, 1)
  assert.deepEqual(f.counts(), { refreshCount: 1, clearCount: 1 })
})

test('无会话时不沿用请求中残留的 Authorization', async () => {
  const client = axios.create({ adapter: async (config) => {
    assert.equal(config.headers.has('Authorization'), false)
    return { status: 200, statusText: 'OK', config, headers: {}, data: {} }
  } })
  attachSessionInterceptors(client, { getToken: () => null, refresh: async () => '', clear: () => {} })
  await client.get('/auth/status', { headers: { Authorization: 'Bearer stale-synthetic-token' } })
})

test('母本的并发续期共用一个请求，并更新统一存储', async () => {
  const session = await sourceModule('../src/shared/cmabSession.ts')
  const storage = new Map()
  const previousFetch = globalThis.fetch
  const previousStorage = globalThis.localStorage
  const previousWindow = globalThis.window
  let calls = 0
  let complete
  globalThis.localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  }
  globalThis.window = { dispatchEvent: () => {} }
  globalThis.fetch = async (url, options) => {
    calls += 1
    assert.equal(url, '/mdm/api/v1/auth/refresh')
    assert.equal(options.credentials, 'include')
    await new Promise((resolve) => { complete = resolve })
    return { ok: true, status: 200, json: async () => ({ data: { access_token: 'synthetic-renewed-token' } }) }
  }
  try {
    const first = session.mdmRefresh()
    const second = session.mdmRefresh()
    assert.equal(first, second)
    complete()
    assert.deepEqual(await Promise.all([first, second]), ['synthetic-renewed-token', 'synthetic-renewed-token'])
    assert.equal(calls, 1)
    assert.equal(storage.get(session.TOKEN_KEY), 'synthetic-renewed-token')
  } finally {
    globalThis.fetch = previousFetch
    globalThis.localStorage = previousStorage
    globalThis.window = previousWindow
  }
})
