import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const code = ts.transpileModule(await readFile(new URL('../src/services/releaseDraft.ts', import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
}).outputText
const { parseReleaseDraft, emptyDraft } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)

test('刷新恢复 QC 时保留来源、项目和批号原值，不回落成 RD', () => {
  const saved = { ...emptyDraft('SAME', 'QC'), batch_numbers: [' 0001 '] }
  assert.deepEqual(parseReleaseDraft(JSON.stringify(saved)), saved)
})

test('旧 ALL 或非法来源缓存连同筛选清除，不能当作 RD 重新查询', () => {
  for (const source of ['ALL', 'unknown', null]) {
    assert.deepEqual(parseReleaseDraft(JSON.stringify({ data_source: source, project_id: 'SAME', batch_numbers: ['0001'] })), emptyDraft())
  }
})

test('历史 RD 缓存兼容，损坏缓存恢复空选择', () => {
  assert.equal(parseReleaseDraft('{"project_id":"RD_PROJECT"}').data_source, 'RD')
  assert.equal(parseReleaseDraft('{"project_id":"RD_PROJECT"}').project_id, 'RD_PROJECT')
  assert.deepEqual(parseReleaseDraft('broken'), emptyDraft())
})

test('Excel 来源和放置状态刷新后保留，不能回落到 LIMS', () => {
  const saved = { ...emptyDraft('CMAB007', 'EXCEL'), placement_statuses: ['正置'], batch_numbers: ['000123'] }
  assert.deepEqual(parseReleaseDraft(JSON.stringify(saved)), saved)
})
