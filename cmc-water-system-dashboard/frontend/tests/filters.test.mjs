import test from 'node:test'
import assert from 'node:assert/strict'
import {changeFilters,choices} from '../src/filters.ts'

const selected={water_type:'注射用水',samplepoint_code:'WFI002',samplepoint_id:'SP-A',workitem_id:'电导率',paramlist_id:'方法甲',paramlist_version_id:'1',variant_id:'阶段甲',param_id:'结果',unit:'µS/cm',date_from:'2026-07-09',date_to:'2026-10-10',sample_status:['Reviewed']}

test('switch or clear water type removes old point and method constraints',()=>{
  const next=changeFilters(selected,{water_type:'纯化水'})
  assert.deepEqual(next,{water_type:'纯化水',date_from:selected.date_from,date_to:selected.date_to,sample_status:['Reviewed']})
  assert.equal(selected.samplepoint_code,'WFI002')
  assert.equal(changeFilters(selected,{water_type:undefined}).samplepoint_id,undefined)
})
test('each upstream selection resets later selections and preserves preceding ones',()=>{
  const point=changeFilters(selected,{samplepoint_code:'WFI003'})
  assert.equal(point.water_type,'注射用水');assert.equal(point.samplepoint_code,'WFI003')
  assert.equal(point.samplepoint_id,undefined);assert.equal(point.workitem_id,undefined)
  const version=changeFilters(selected,{paramlist_version_id:'2'})
  assert.equal(version.paramlist_id,'方法甲');assert.equal(version.paramlist_version_id,'2')
  assert.equal(version.variant_id,undefined);assert.equal(version.unit,undefined)
  const unit=changeFilters(selected,{unit:'mS/cm'})
  assert.equal(unit.param_id,'结果');assert.equal(unit.unit,'mS/cm')
})
test('date and status changes preserve water type and clear downstream selections',()=>{
  for(const changes of [{date_from:'2026-04-09',date_to:'2026-10-10'},{sample_status:['Completed']}]) {
    const next=changeFilters(selected,changes)
    assert.equal(next.water_type,'注射用水');assert.equal(next.samplepoint_code,undefined);assert.equal(next.unit,undefined)
    for(const [key,value] of Object.entries(changes)) assert.deepEqual(next[key],value)
  }
})
test('point choices keep server labels and never fall back to unscoped internal IDs',()=>{
  const point={value:'SP-A',code:'WFI002',label:'WFI002 / 测试总送 / SP-A'}
  assert.deepEqual(choices({point_options:[point]},'samplepoint_id','samplepointid'),[point])
  assert.deepEqual(choices({point_options:[],options:{samplepointid:['OLD']}},'samplepoint_id','samplepointid'),[])
  assert.deepEqual(choices({options:{unit:[null,'µS/cm']}},'unit','unit'),[{value:'µS/cm',label:'µS/cm'}])
})
