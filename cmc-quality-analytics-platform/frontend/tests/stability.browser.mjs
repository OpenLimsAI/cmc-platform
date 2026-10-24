/** Mac浏览器契约验证：合成身份/观察，所有非本机请求拒绝。 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.QAP_PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, channel: process.env.QAP_BROWSER_CHANNEL || 'chrome' })
const origin = 'http://127.0.0.1:5140'
const context = await browser.newContext({ viewport: { width: 1500, height: 1050 }, reducedMotion: 'reduce' })
const state = { requests: [], optionRequests: [], failures: [], optionDelay: 0, analysisDelay: 0, empty: false, fail: false }
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const options = (project) => ({ sample_types: ['成品', '原液'], test_types: ['长期试验', '加速试验'], production_line_ids: [project + '-LINE'], group_ids: ['G1', 'G2'], batch_numbers: [' SYNTHETIC-A ', 'SYNTHETIC-B'], attributes: [{ attribute_name: 'sec_monomer_pct', attribute_raws: ['合成SEC单体'], n: 12 }], row_count: 12, project_row_count: 12 })
function panel(unknown = false) {
  const batches = [' SYNTHETIC-A ', 'SYNTHETIC-B'].map((batch, index) => {
    const points = [0, 3, 6].map((time, i) => ({ observation_id: `${batch}-${i}`, batch_number: batch, production_line_id: 'L' + (index + 1), group_id: 'G' + (index + 1), source_system: 'rd_samplemanager', sample_id: `SAMPLE-${index}-${i}`, source_test_id: `TEST-${index}-${i}`, source_result_id: `RESULT-${index}-${i}`, value_str: null, received_dt: null, timepoint: time, timepoint_raw: String(time), value: .98 + index * .01 - i * .02, value_raw: String(.98 + index * .01 - i * .02), issues: [], plottable: true }))
    return { series_id: batch, batch_number: batch, production_line_id: points[0].production_line_id, group_id: points[0].group_id, connect_points: true, points,
      fit: unknown ? { available: false, reason: '时间或结果单位未提供' } : { available: true, n: 3, slope: -.02 / 3, intercept: points[0].value, r_squared: 1, x: [0, 6], y: [points[0].value, points[2].value] } }
  })
  return { panel_id: unknown ? 'unknown-unit' : 'month', attribute_name: 'sec_monomer_pct', attribute_raw: '合成SEC单体', sample_type: '成品', test_type: '长期试验', method_code: 'SYNTHETIC-METHOD', unit: '%', timepoint_unit: unknown ? '' : '月', n: 6, plotted_n: 6, timepoint_count: 3, statistics_available: !unknown,
    warnings: unknown ? ['时间或结果单位未提供：仅显示原始观察，均值SD与拟合未开放'] : [], observations: batches.flatMap((batch) => batch.points), batches,
    groups: unknown ? [] : batches.map((batch) => ({ series_id: 'group-' + batch.group_id, production_line_id: batch.production_line_id, group_id: batch.group_id, fit: batch.fit, points: batch.points.map((point) => ({ timepoint: point.timepoint, n: 1, mean: point.value, sd: null })) })) }
}
await context.route('**/*', async (route) => {
  const url = new URL(route.request().url())
  if (url.origin !== origin) { state.failures.push(url.origin); return route.abort() }
  const reply = (data, meta = {}) => route.fulfill({ json: { data, meta, errors: [] } })
  if (url.pathname === '/qap/health') return reply({ status: 'ok' })
  if (url.pathname === '/qap/api/v1/auth/status') return reply({ configured: false, auth_required: false })
  if (url.pathname === '/qap/api/v1/meta/projects') return reply([{ project_id: 'P-A', n: 24 }, { project_id: 'P-B', n: 24 }])
  if (url.pathname === '/qap/api/v1/analysis/stability/options') {
    const request = route.request().postDataJSON(); state.optionRequests.push(request)
    if (request.project_id === 'P-A') await pause(state.optionDelay)
    return reply(options(request.project_id))
  }
  if (url.pathname === '/qap/api/v1/analysis/stability') {
    const request = route.request().postDataJSON(); state.requests.push(request)
    await pause(state.analysisDelay)
    if (state.fail) return route.fulfill({ status: 503, json: { data: null, meta: {}, errors: [{ code: 'test_failure', message: '合成服务暂不可用' }] } })
    return reply(state.empty ? [] : [panel(), panel(true)], { row_count: state.empty ? 0 : 12, applied_filters: request })
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
async function ready() {
  await page.waitForFunction(() => !document.querySelector('#stability-attributes')?.disabled)
}
async function plotsReady() {
  await page.waitForFunction(() => { const nodes = [...document.querySelectorAll('.js-plotly-plot .svg-container')]; return nodes.length === 2 && nodes.every((node) => node.getBoundingClientRect().height >= 430) })
}
try {
  await page.goto(origin + '/qap/stability')
  await page.getByRole('heading', { name: '从一个稳定性项目开始' }).waitFor()
  await pick('项目', 'P-A（24条来源记录）'); await ready()
  await pick('样品类型', '成品'); await ready()
  await pick('检验类别', '长期试验'); await ready()
  await pick('产线', 'P-A-LINE'); await ready()
  await pick('批号', ' SYNTHETIC-A '); await ready()
  await page.getByRole('button', { name: '分子大小变异体', exact: true }).click()
  await plotsReady()
  assert.deepEqual(state.requests.at(-1), { project_id: 'P-A', sample_types: ['成品'], test_types: ['长期试验'], production_line_ids: ['P-A-LINE'], group_ids: [], batch_numbers: [' SYNTHETIC-A '], placement_statuses: [], attribute_names: ['sec_monomer_pct'], data_source: 'RD' })
  const first = page.locator('.qap-attribute').first()
  const second = page.locator('.qap-attribute').nth(1)
  const raw = await first.locator('.js-plotly-plot').evaluate((plot) => ({ x: plot.data[0].x, y: plot.data[0].y, axis: plot.layout.xaxis.type }))
  assert.deepEqual(raw.x, [0, 3, 6]); assert.equal(raw.y[0], .98); assert.equal(raw.axis, 'linear')
  assert.equal(await second.getByRole('tab', { name: '组均值 ± SD', exact: true }).getAttribute('aria-disabled'), 'true')
  assert.equal(await second.getByRole('tab', { name: '逐批拟合', exact: true }).getAttribute('aria-disabled'), 'true')
  console.log('PASS: 级联筛选原样进入请求；时间轴为数值；百分数未乘100；缺失单位禁用统计')

  await first.getByRole('tab', { name: '组均值 ± SD', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot')?.data[0]?.error_y?.visible === true)
  await first.getByRole('tab', { name: '逐批拟合', exact: true }).click()
  await first.getByText('仅描述趋势', { exact: true }).first().waitFor()
  const fittedX = await first.locator('.js-plotly-plot').evaluate((plot) => plot.data[0].x)
  assert.deepEqual(fittedX, [0, 6])
  await first.getByRole('tab', { name: '组拟合', exact: true }).click()
  await first.getByRole('tab', { name: '逐批观察', exact: true }).click()
  await first.getByText('查看原始记录（6条，入图6条）', { exact: true }).click()
  await first.getByText('RESULT-0-0', { exact: true }).waitFor()
  await first.getByText('查看原始记录（6条，入图6条）', { exact: true }).click()
  await page.locator('.qap-page-title').scrollIntoViewIfNeeded()
  await page.screenshot({ path: '/tmp/qap-stability-desktop.png', fullPage: false })
  console.log('PASS: 四种视图可切换；拟合限定在观察范围；原始记录含来源结果编号')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.locator('.qap-filter-section').evaluate((node) => { node.open = false })
  await plotsReady()
  await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth + 1)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true)
  await first.getByTestId('stability-chart').screenshot({ path: '/tmp/qap-stability-mobile-chart.png' })
  await page.locator('.qap-page-title').scrollIntoViewIfNeeded()
  await page.screenshot({ path: '/tmp/qap-stability-mobile.png', fullPage: false })
  console.log('PASS: 手机无横向溢出，时间图保持完整高度')

  await page.setViewportSize({ width: 1500, height: 1050 })
  await page.locator('.qap-filter-section').evaluate((node) => { node.open = true })
  state.analysisDelay = 700
  await page.getByRole('button', { name: '分子大小变异体', exact: true }).click()
  await page.getByRole('button', { name: '重置稳定性筛选', exact: true }).click(); await ready(); await plotsReady()
  assert.deepEqual(state.requests.at(-1).attribute_names, [])
  state.optionDelay = 700
  await pick('项目', 'P-B（24条来源记录）')
  await pick('项目', 'P-A（24条来源记录）')
  await pick('项目', 'P-B（24条来源记录）'); await ready(); await pause(850)
  await pick('产线', 'P-B-LINE'); await ready()
  state.analysisDelay = 0; state.empty = true
  await page.getByRole('button', { name: '分子大小变异体', exact: true }).click()
  await page.getByRole('heading', { name: '当前条件下没有稳定性记录' }).waitFor()
  assert.deepEqual(state.requests.at(-1).sample_types, [])
  assert.deepEqual(state.requests.at(-1).batch_numbers, [])
  console.log('PASS: 重置拦截迟到结果；快速换项目不串条件；空结果有明确反馈')

  state.empty = false; state.fail = true
  await page.getByRole('button', { name: '分子大小变异体', exact: true }).click()
  await page.getByText('合成服务暂不可用', { exact: true }).waitFor()
  assert.equal(await page.locator('.qap-attribute').count(), 0)
  state.fail = false
  await page.getByRole('button', { name: '重试分析', exact: true }).click(); await plotsReady()
  assert.deepEqual(state.failures, [])
  console.log('PASS: 服务失败可重试且不保留旧图；无页面异常、MDM或非本机请求')
} catch (error) {
  await page.screenshot({ path: '/tmp/qap-stability-failure.png', fullPage: false })
  console.error(await page.locator('body').evaluate(() => [...document.querySelectorAll('body *')].filter((node) => node.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map((node) => ({ tag: node.tagName, class: node.getAttribute('class'), width: node.getBoundingClientRect().width }))))
  console.error((await page.locator('body').innerText()).slice(0, 2000))
  throw error
} finally { await browser.close() }
