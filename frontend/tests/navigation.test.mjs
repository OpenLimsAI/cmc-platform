import test from 'node:test'
import assert from 'node:assert/strict'
import {pageTitles,readPage,pageURL} from '../src/navigation.ts'

test('only overview and trends remain, old pages return to overview with a notice',()=>{
  assert.deepEqual(Object.keys(pageTitles),['overview','trends'])
  assert.deepEqual(readPage('/water/trends'),{section:'trends',removed:false})
  for(const page of ['results','summaries','quality']) {
    assert.deepEqual(readPage(`/water/${page}`),{section:'overview',removed:true})
  }
  assert.deepEqual(readPage('/water/'),{section:'overview',removed:false})
})

test('overview URL never retains trend filters; trend deep links retain them',()=>{
  const filters='water_type=PW&samplepoint_id=SP-A&date_from=2026-01-01'
  assert.equal(pageURL('overview',filters),'/water/overview')
  assert.equal(pageURL('trends',filters),'/water/trends?'+filters)
  assert.equal(pageURL('trends'),'/water/trends')
})
