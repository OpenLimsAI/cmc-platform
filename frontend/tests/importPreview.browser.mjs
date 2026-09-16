/** 浏览器契约测试：接口/身份全部模拟，拒绝所有非本机请求，不连接 MDM 或数据库。
 * 启动 pnpm dev 后执行；QAP_PLAYWRIGHT_MODULE 可指定本机已有 playwright 包。
 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.QAP_PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, channel: process.env.QAP_BROWSER_CHANNEL || 'chrome' })
const origin = 'http://127.0.0.1:5140'
const env = (data) => ({ data, meta: {}, errors: [] })
const token = (suffix) => `synthetic.${Buffer.from(JSON.stringify({ exp: Date.now() / 1000 + 3600 })).toString('base64url')}.${suffix}`
const identity = { username: 'TEST-0042', full_name: '合成员工', subject: '42', roles: ['TEST_PREVIEW'], can_read: false, can_preview: true, can_commit: false }
const headers = ['project_code', 'batch_number', 'attribute', 'value', 'unit']
const fields = ['source_project_ref', 'batch_number', 'source_attribute', 'value_raw', 'source_unit']
const values = ['SYNTHETIC-PROJECT', 'SYNTHETIC-001', '合成检测项', 0.98, '%']
const result = {
  actor: identity, preview_only: true, total_row_count: 1, total_issue_count: 0,
  rows_truncated: false, issues_truncated: false,
  preview: {
    original_filename: 'synthetic.xlsx', file_sha256: 'a'.repeat(64), byte_size: 16,
    template_code: 'qap_long_preview_v1', template_version: '1', sheet_name: '质量数据',
    rows: [{ row_number: 2, cells: headers.map((header, i) => ({
      source_header: header, field_name: fields[i], coordinate: `${String.fromCharCode(65 + i)}2`,
      value: values[i], data_type: i === 3 ? 'n' : 's', number_format: i === 3 ? '0.00%' : 'General', cached_value: null,
    })) }],
    issues: [], blank_row_count: 0, parser_version: 'test-contract', business_validation: 'pending', can_commit: false, structure_valid: true,
  },
}

async function setup({ configured = true, canPreview = true } = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  await context.addInitScript(({ token }) => {
    localStorage.setItem('cmab_access_token', token)
    localStorage.setItem('cmab_last_active', String(Date.now()))
  }, { token: token('initial') })
  const state = { previews: 0, refreshes: 0, logins: 0, expireOnce: false, delayPreview: 0, meDelay: 0, identity: { ...identity, can_preview: canPreview }, unexpected: [] }
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.origin !== origin) { state.unexpected.push(url.origin); return route.abort() }
    const json = (data, status = 200) => route.fulfill({ status, json: env(data) })
    switch (url.pathname) {
      case '/health': return json({ status: 'ok' })
      case '/api/v1/auth/status': return json({ auth_required: configured, configured })
      case '/api/v1/auth/me':
        if (state.meDelay) await new Promise((resolve) => setTimeout(resolve, state.meDelay))
        return json(state.identity)
      case '/api/v1/imports/capabilities': return json({ can_commit: false, business_validation: 'pending', templates: [{
        template_code: 'qap_long_preview_v1', version: '1', label: '通用长表（结构预览）', sheet_name: '质量数据', headers,
        max_file_bytes: 10485760, approval_state: 'draft',
      }] })
      case '/api/v1/imports/preview':
        state.previews += 1
        assert.match(route.request().headers()['content-type'], /multipart\/form-data; boundary=/)
        assert.ok(route.request().postDataBuffer().includes(Buffer.from('synthetic.xlsx')))
        if (state.expireOnce) { state.expireOnce = false; return json(null, 401) }
        if (state.delayPreview) await new Promise((resolve) => setTimeout(resolve, state.delayPreview))
        return json(result)
      case '/mdm/api/v1/auth/refresh':
        state.refreshes += 1
        return json({ access_token: token('renewed') })
      case '/mdm/api/v1/auth/login':
        assert.deepEqual(route.request().postDataJSON(), { username: 'SYNTHETIC-LOGIN', password: 'synthetic-form-input' })
        state.logins += 1
        return json({ access_token: token('login'), user: { ...state.identity, user_id: 43 }, token_type: 'bearer', expires_in: 900 })
      case '/mdm/api/v1/auth/session-policy': return json({ access_token_minutes: 15, idle_timeout_minutes: 30, absolute_max_hours: 12, display_mode: false })
      case '/mdm/api/v1/auth/logout': return json(null)
      default:
        if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/mdm/')) {
          state.unexpected.push(url.pathname)
          return route.abort()
        }
        return route.continue()
    }
  })
  const page = await context.newPage()
  page.setDefaultTimeout(10000)
  page.on('pageerror', (error) => state.unexpected.push(error.message))
  await page.goto(`${origin}/imports`)
  return { context, page, state }
}

const syntheticFile = { name: 'synthetic.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('synthetic UI contract bytes; parser tested separately') }
let debugPage
try {
  for (const settings of [{ configured: false }, { canPreview: false }]) {
    const { context, page, state } = await setup(settings)
    await page.getByText(settings.configured === false ? 'MDM 接入尚未就绪，结构预览未开放' : '当前账号尚无结构预览权限', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: '选择 Excel 文件', exact: true }).count(), 0)
    assert.deepEqual(state.unexpected, [])
    await context.close()
  }
  console.log('PASS: 未配置身份及无预览权限均没有上传控件')

  const { context, page, state } = await setup()
  debugPage = page
  await page.getByRole('button', { name: '选择 Excel 文件', exact: true }).waitFor()
  await page.locator('input[type=file]').setInputFiles(syntheticFile)
  state.expireOnce = true
  state.meDelay = 500
  await page.getByRole('button', { name: '校验并预览结构', exact: true }).click()
  await page.getByText('结构预览完成，尚未导入', { exact: true }).waitFor()
  for (const value of values) await page.getByRole('cell', { name: String(value), exact: false }).first().waitFor()
  assert.equal(state.previews, 2)
  assert.equal(state.refreshes, 1)
  await page.getByText(/^synthetic\.xlsx（/).waitFor()
  assert.equal(await page.getByRole('button', { name: '校验并预览结构', exact: true }).isEnabled(), true)
  assert.equal(await page.getByRole('button', { name: /确认导入|保存|发布/ }).count(), 0)
  console.log('PASS: 401 续期重放保留文件，五列原值/百分数正确显示，无提交按钮')

  state.meDelay = 0
  state.delayPreview = 700
  await page.getByRole('button', { name: '校验并预览结构', exact: true }).click()
  await page.getByRole('button', { name: '移除', exact: true }).click()
  await page.waitForTimeout(800)
  assert.equal(await page.getByText('结构预览完成，尚未导入', { exact: true }).count(), 0)
  assert.equal(await page.getByRole('button', { name: '校验并预览结构', exact: true }).isDisabled(), true)
  console.log('PASS: 更换/移除文件后迟到结果不会恢复旧预览')

  await page.locator('input[type=file]').setInputFiles(syntheticFile)
  state.identity = { ...identity, username: 'TEST-OTHER', subject: '43' }
  await page.evaluate((nextToken) => {
    localStorage.setItem('cmab_access_token', nextToken)
    window.dispatchEvent(new CustomEvent('cmab-token-changed'))
  }, token('other'))
  await page.getByRole('button', { name: '移除', exact: true }).waitFor({ state: 'detached' })
  assert.equal(await page.getByRole('button', { name: '校验并预览结构', exact: true }).isDisabled(), true)
  console.log('PASS: 切换已验证员工身份后丢弃上一人的文件')

  await page.evaluate(() => {
    localStorage.removeItem('cmab_access_token')
    window.dispatchEvent(new StorageEvent('storage', { key: 'cmab_access_token', newValue: null }))
  })
  await page.getByText('使用 MDM 员工账号登录', { exact: true }).waitFor()
  assert.equal(await page.locator('input[type=file]').count(), 0)
  console.log('PASS: 跨标签退出清除受限页面')

  await page.getByLabel('员工工号', { exact: true }).fill('SYNTHETIC-LOGIN')
  await page.getByLabel('密码', { exact: true }).fill('synthetic-form-input')
  await page.getByRole('button', { name: '登录 MDM', exact: true }).click()
  await page.getByRole('button', { name: '选择 Excel 文件', exact: true }).waitFor()
  assert.equal(state.logins, 1)
  assert.equal(await page.evaluate(() => Object.values(localStorage).some((value) => value.includes('synthetic-form-input'))), false)
  assert.deepEqual(state.unexpected, [])
  await context.close()
  console.log('PASS: 登录表单直达模拟 MDM，后端核验后进入授权页面，密码不进入存储；无真实业务请求及页面异常')
} catch (error) {
  if (debugPage) {
    console.error((await debugPage.locator('body').innerText()).slice(0, 6000))
    console.error(await debugPage.locator('body').ariaSnapshot())
    await debugPage.screenshot({ path: '/tmp/qap-preview-browser-failure.png', fullPage: true })
  }
  throw error
} finally {
  await browser.close()
}
