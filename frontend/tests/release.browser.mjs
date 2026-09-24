/** 本机浏览器契约回归；合成响应，阻止一切非本机访问，不读取业务库。 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.QAP_PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, channel: process.env.QAP_BROWSER_CHANNEL || 'chrome' })
const origin = 'http://127.0.0.1:5140'
const context = await browser.newContext({ viewport: { width: 1500, height: 1040 }, reducedMotion: 'reduce' })
const state = { requests: [], failures: [], optionDelay: 0, analysisDelay: 0, empty: false }
const names = ['sec_aggregate_pct', 'sec_monomer_pct', 'sec_fragment_pct']
const options = (project) => ({
  production_line_ids: [project + '-LINE'], group_ids: ['Group A', 'Group B'], batch_numbers: [' 007-202601A ', '007-202602A'],
  test_types: ['成品放行'], sample_types: ['成品', '原液'], batch_years: [2026], unknown_batch_year_count: 1,
  row_count: 36, year_basis: 'legacy_batch_number_inference',
  attributes: names.map((name) => ({ attribute_name: name, attribute_raws: [name], n: 12 })),
})
const attribute = (name, offset) => ({
  attribute_name: name, units: ['%'], is_pct: true, n: 12, mean: 1.2 + offset, sd_sample: 0.2, sd_population: 0.18,
  min: 0.9 + offset, max: 1.5 + offset, rsd_pct: 16.67,
  spec: { lsl: 0, usl: 2 + offset }, capability: { value: 1.3, label: 'PPU', mode: 'population' },
  sd_lines: { mean: 1.2 + offset, plus_1_5sd: 1.5 + offset, minus_1_5sd: 0.9 + offset, plus_3sd: 1.8 + offset, minus_3sd: 0.6 + offset },
  groups: [{ group_id: 'Group A', n: 6, mean: 1.1 + offset, sd: 0.1 }, { group_id: 'Group B', n: 6, mean: 1.3 + offset, sd: 0.15 }],
  points: Array.from({ length: 12 }, (_, i) => ({ batch_number: 'SYNTHETIC-2026' + String(i + 1).padStart(2, '0'), value: 1 + (i % 5) * 0.1 + offset, group_id: i % 2 === 0 ? 'Group A' : 'Group B', lot_sort_key: 202601 + i, year: 2026 })),
})
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
await context.addInitScript(() => localStorage.setItem('qap.release.filter', '{invalid-json'))
await context.route('**/*', async (route) => {
  const url = new URL(route.request().url())
  if (url.origin !== origin) { state.failures.push(url.origin); return route.abort() }
  const reply = (data, meta = {}) => route.fulfill({ json: { data, meta, errors: [] } })
  if (url.pathname === '/qap/health') return reply({ status: 'ok' })
  if (url.pathname === '/qap/api/v1/auth/status') return reply({ configured: false, auth_required: false })
  if (url.pathname === '/qap/api/v1/meta/projects') return reply([{ project_id: 'P-A', n: 36 }, { project_id: 'P-B', n: 36 }])
  if (url.pathname === '/qap/api/v1/analysis/release/options') {
    const project = url.searchParams.get('project_id')
    if (project === 'P-A') await pause(state.optionDelay)
    return reply(options(project))
  }
  if (url.pathname === '/qap/api/v1/analysis/release') {
    const request = route.request().postDataJSON()
    state.requests.push(request)
    if (state.analysisDelay) await pause(state.analysisDelay)
    const selected = request.attribute_names?.length ? request.attribute_names : names
    return reply(state.empty ? [] : selected.map((name) => attribute(name, names.indexOf(name))), { project_id: request.project_id, row_count: state.empty ? 0 : 36, applied_filters: request })
  }
  if (url.pathname.startsWith('/qap/api/') || url.pathname.startsWith('/mdm/')) { state.failures.push(url.pathname); return route.abort() }
  return route.continue()
})
const page = await context.newPage()
page.setDefaultTimeout(15000)
page.on('pageerror', (error) => state.failures.push(error.message))
async function pick(label, text) {
  await page.locator('.ant-select').filter({ has: page.getByLabel(label, { exact: true }) }).locator('.ant-select-selector').click()
  await page.locator('.ant-select-dropdown:visible').getByText(text, { exact: true }).last().click()
  await page.getByLabel(label, { exact: true }).press('Escape')
}
try {
  await page.goto(origin + '/qap/release')
  await page.getByRole('heading', { name: '从一个项目开始' }).waitFor()
  await pick('项目', 'P-A（36条来源记录）')
  await page.getByRole('button', { name: '分子大小变异体', exact: true }).click()
  await page.getByText('已选 3 项', { exact: false }).waitFor()
  await pick('产线', 'P-A-LINE')
  await pick('组别', 'Group A')
  await pick('检验类别', '成品放行')
  await pick('批号年份（推算）', '2026')
  await page.getByRole('button', { name: '分析', exact: true }).click()
  await page.getByRole('heading', { name: 'SEC聚合体(％)', exact: true }).waitFor()
  await page.waitForFunction(() => document.querySelectorAll('.js-plotly-plot').length === 6)
  assert.deepEqual(state.requests.at(-1).attribute_names, names)
  assert.deepEqual(state.requests.at(-1).production_line_ids, ['P-A-LINE'])
  assert.deepEqual(state.requests.at(-1).group_ids, ['Group A'])
  assert.deepEqual(state.requests.at(-1).test_types, ['成品放行'])
  assert.deepEqual(state.requests.at(-1).batch_years, [2026])
  assert.equal(await page.getByRole('checkbox', { name: '旧配置规格线' }).isChecked(), false)
  const geometries = await page.locator('.qap-chart-pair').first().locator('.qap-chart').evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().toJSON()))
  assert.equal(Math.round(geometries[0].y), Math.round(geometries[1].y))
  assert.ok(geometries[0].width > geometries[1].width)
  const plottedOrder = await page.getByTestId('release-trend-chart').first().locator('.js-plotly-plot').evaluate((plot) => plot.layout.xaxis.categoryarray)
  assert.deepEqual(plottedOrder, attribute(names[0], 0).points.map((point) => point.batch_number))
  await page.screenshot({ path: '/tmp/qap-release-desktop.png', fullPage: false })
  console.log('PASS: 损坏缓存安全恢复；旧组合准确匹配；筛选进入请求；图表并排；规格线默认关闭')

  await pick('组别', 'Group B')
  assert.equal(await page.locator('.qap-attribute').count(), 0)
  state.analysisDelay = 700
  await page.getByRole('button', { name: '分析', exact: true }).click()
  await page.getByRole('button', { name: '重置筛选', exact: true }).click()
  await pause(850)
  assert.equal(await page.locator('.qap-attribute').count(), 0)
  console.log('PASS: 条件变更清除旧图；重置后迟到结果不能回填')

  state.optionDelay = 700
  await pick('项目', 'P-B（36条来源记录）')
  await pick('项目', 'P-A（36条来源记录）')
  await pick('项目', 'P-B（36条来源记录）')
  await pause(850)
  await pick('产线', 'P-B-LINE')
  assert.equal(await page.getByLabel('组别', { exact: true }).inputValue(), '')
  console.log('PASS: 快速切换项目不会使用上一项目的选项或条件')

  state.analysisDelay = 0; state.empty = true
  await page.getByRole('button', { name: '分析', exact: true }).click()
  await page.getByRole('heading', { name: '当前条件下没有放行数值结果' }).waitFor()
  assert.equal(await page.locator('.qap-attribute').count(), 0)
  assert.deepEqual(state.requests.at(-1).group_ids, [])
  assert.deepEqual(state.requests.at(-1).test_types, [])
  assert.deepEqual(state.requests.at(-1).batch_years, [])
  console.log('PASS: 空结果有明确反馈，不保留上一份图表')

  state.empty = false
  await page.getByRole('button', { name: '分析', exact: true }).click()
  await page.getByRole('heading', { name: 'SEC聚合体(％)', exact: true }).waitFor()
  await page.waitForFunction(() => document.querySelectorAll('.js-plotly-plot .svg-container').length === 6)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.locator('.qap-filter-section').evaluate((details) => { details.open = false })
  await page.waitForTimeout(250)
  await page.waitForFunction(() => {
    const plots = [...document.querySelectorAll('.js-plotly-plot .svg-container')]
    return plots.length === 6 && plots.every((plot) => plot.getBoundingClientRect().height >= 380)
  })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true)
  const mobile = await page.locator('.qap-chart-pair').first().locator('.qap-chart').evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().toJSON()))
  assert.ok(mobile[1].y > mobile[0].y)
  await page.locator('.qap-page-title').scrollIntoViewIfNeeded()
  await page.screenshot({ path: '/tmp/qap-release-mobile.png', fullPage: false })
  await page.locator('.qap-chart-pair').first().screenshot({ path: '/tmp/qap-release-mobile-charts.png' })
  assert.deepEqual(state.failures, [])
  console.log('PASS: 手机宽度无横向溢出，图表上下排列；无页面异常或外部请求')
} catch (error) {
  await page.screenshot({ path: '/tmp/qap-release-failure.png', fullPage: false })
  console.error((await page.locator('body').innerText()).slice(0, 2200))
  throw error
} finally { await browser.close() }
