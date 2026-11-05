import assert from 'node:assert/strict';
import {test} from 'node:test';
import {activeProjectTab, checkedBusinessLink, observe, signRegisteredProject} from '../e2e/joint-scenarios.mjs';

test('business links stay on the approved service and never carry token-like query data',()=>{
  assert.equal(checkedBusinessLink('http://localhost:19091/projects/p-synthetic','pm'),'http://localhost:19091/projects/p-synthetic');
  for(const value of ['https://pm.openlims.ai/projects/p-one','http://localhost:19091/projects/p-one?token=secret','http://user:pass@localhost:19091/projects/p-one','http://localhost:19091/login']){
    assert.throws(()=>checkedBusinessLink(value,'pm'));
  }
});

test('a stopped document observation never falls back to another UI observation',async()=>{
  let alternativeReads=0;
  const tab={playwright:{domSnapshot:async()=>{throw Error('Runtime.evaluate unavailable: paused document response');}},getAXState:async()=>{alternativeReads++;return 'do not read';}};
  await assert.rejects(observe(tab));
  assert.equal(alternativeReads,0);
});

test('project continuation uses the actual returned tab and observes it',async()=>{
  let reads=0;
  const tab={url:async()=> 'http://localhost:19090/mdm/projects/CMAB-PRJ-2026-0001',playwright:{domSnapshot:async()=>{reads++;return 'project';}}};
  const browser={tabs:{get:async id=>{assert.equal(id,'returned-mdm-tab');return tab;}}};
  assert.equal(await activeProjectTab(browser,{mdm_tab_id:'returned-mdm-tab',mdmUrl:await tab.url()}),tab);
  assert.equal(reads,1);
});

test('a changed returned-tab URL stops before reading or acting on that page',async()=>{
  let reads=0;
  const tab={url:async()=> 'https://other.invalid/',playwright:{domSnapshot:async()=>{reads++;}}};
  const browser={tabs:{get:async()=>tab}};
  await assert.rejects(activeProjectTab(browser,{mdm_tab_id:'returned-mdm-tab',mdmUrl:'http://localhost:19090/mdm/projects/CMAB-PRJ-2026-0001'}),error=>error.stage==='returned-project-tab-changed');
  assert.equal(reads,0);
});

test('a safety stop during iframe readiness performs no further screenshot or UI input',async()=>{
  let captures=0;
  const ordinary={fill:async()=>{},click:async()=>{},count:async()=>0,waitFor:async()=>{}};
  const blocked={waitFor:async()=>{throw Error('Computer Use was stopped for this turn');}};
  const mdm={playwright:{getByRole:()=>ordinary,getByPlaceholder:()=>ordinary,
    domSnapshot:async()=>'',frameLocator:()=>({getByRole:()=>blocked})}};
  await assert.rejects(signRegisteredProject({mdm,fixture:{users:{signer:{username:'e2e.signer',password:'new-synthetic-fixture'}}},capture:async()=>{captures++;}}),error=>{
    assert.equal(error.stage,'signature-iframe-document-ready');
    assert.equal(error.safetyStop,true);
    return true;
  });
  assert.equal(captures,0);
});
