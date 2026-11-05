/** Stateful, bounded CUA calls for one fresh fixture. Each method is invoked in
 * a separate supported tool cell; no human credentials or UI repair is needed.
 * Unknown outcomes stop the plan instead of replaying a mutating step. */
export async function createRegressionPlan({browser,portal,directory,fixture,runKey}) {
  // A unique owned run directory pins the modules in persistent CUA sessions;
  // a prior run's Node module cache must not silently test older source files.
  const version=encodeURIComponent(directory);
  const uiUrl=new URL('./joint-scenarios.mjs',import.meta.url);
  const driverUrl=new URL('./fixture-driver.mjs',import.meta.url);
  const ui=await import(uiUrl.href+'?run='+version);
  const {createCapture,createController,finishRun,saveCase}=await import(driverUrl.href+'?run='+version);
  const control=createController(directory);
  const state={};
  const cases=[];
  const capture=prefix=>createCapture(directory,prefix);
  async function step(name,prerequisite,fn) {
    if(!prerequisite || cases.some(c=>c.name===name || c.status==='blocked')) throw Error('Plan stage missing, blocked or already attempted; inspect before repeating');
    try {
      const result=await fn();
      const record={name,status:'passed',time_utc:new Date().toISOString()};
      cases.push(record);await saveCase(directory,{...record,result});return result;
    } catch(error) {
      const record={name,status:'blocked',stage:error.stage||'fixture-or-ui',tool_stop:Boolean(error.safetyStop),time_utc:new Date().toISOString()};
      cases.push(record);await saveCase(directory,record);
      throw new ui.BrowserCaseBlocked(record.stage,record.tool_stop);
    }
  }
  return {
    async phaseOne() {return await step('empty-db-login-create-link-reauth',!state.one,async()=>{
      const baseline=await control('snapshot',{stage:'empty-business-baseline'});
      if(baseline.mdm.projects!==null || baseline.pm.projects!==null || baseline.mdm.signatures!==0) throw Error('Not an empty fixture');
      const result=await ui.runJointCases({browser,portal,fixture,runKey,capture:capture('core-')});
      if(result.status!=='awaiting-confirmation') throw new ui.BrowserCaseBlocked(result.blocker||'phase-one',result.tool_stop);
      state.one=result;return result;
    });},
    async phaseTwo() {return await step('separate-call-confirmed-business-signature',Boolean(state.one),async()=>{
      const mdm=await browser.tabs.get(state.one.mdm_tab_id);
      await ui.confirmVerifiedSignature({mdm,capture:capture('core-')});
      const snapshot=await control('snapshot',{stage:'after-unattended-signature'});
      if(snapshot.mdm.signatures!==1 || snapshot.mdm.status_history!==1 || snapshot.mdm.projects.length!==1 || snapshot.pm.projects.length!==1 || snapshot.pm.receipts!==1 || snapshot.mdm.proofs?.consumed!==1) throw Error('Signature transaction did not persist exactly once');
      state.signed=true;return {status:'passed',human_input:false,snapshot};
    });},
    async prepareRecovery() {return await step('remote-created-local-commit-failed',state.signed===true,async()=>{
      const mdm=await browser.tabs.get(state.one.mdm_tab_id);
      state.retry=await ui.recoveryCreateScenario({browser,mdm,runKey:runKey+'-R',capture:capture('rec-'),control});
      if(state.retry.status!=='awaiting-retry') throw Error('Expected persisted remote result before retry');
      return state.retry;
    });},
    async finishRecovery() {return await step('same-request-double-retry-no-duplicate',Boolean(state.retry),async()=>{
      const mdm=await browser.tabs.get(state.retry.mdm_tab_id);
      state.recovered=await ui.finishRecoveryScenario({browser,mdm,plan:state.retry,capture:capture('rec-'),control});
      return state.recovered;
    });},
    async restartApplications() {return await step('app-restart-keeps-real-browser-sessions-and-links',Boolean(state.recovered),async()=>{
      const mdm=await ui.activeProjectTab(browser,state.recovered);
      state.restart=await ui.restartScenario({browser,portal,mdm,project:state.recovered,capture:capture('persist-'),control});
      return state.restart;
    });},
    async transientOutage() {return await step('real-502-keeps-form-session-and-recovers',Boolean(state.restart),async()=>{
      const mdm=await browser.tabs.get(state.restart.mdm_tab_id);
      const result=await ui.outageScenario({mdm,project:state.recovered,capture:capture('outage-'),control});
      state.outage=true;return result;
    });},
    async finish() {
      const result=await step('final-persisted-invariants',state.outage===true,async()=>{
      const snapshot=await control('snapshot',{stage:'final-unattended-invariants'});
      if(snapshot.mdm.projects.length!==2 || snapshot.mdm.links.length!==2 || snapshot.pm.projects.length!==2 || snapshot.pm.receipts!==2 || snapshot.mdm.signatures!==1 || snapshot.mdm.status_history!==1 || snapshot.mdm.link_audits!==2) throw Error('Final persisted counts differ');
      const recovered=snapshot.mdm.requests.find(r=>r.request_id===state.recovered.recoveryProof.request_id);
      if(!recovered || recovered.attempts!==2 || recovered.pm_project_id!==state.recovered.recoveryProof.pm_project_id || recovered.status!=='linked') throw Error('Recovered identity/request changed');
      return {status:'passed',snapshot,cleanup:'requested'};
      });
      await finishRun(directory,{status:'passed',cases,human_input:false,mocked_business_paths:false,signature_calls:2,production_cookie_risk_resolved:false});
      fixture=null;return result;
    },
    async abort(reason='blocked') {
      await finishRun(directory,{status:'blocked',cases,reason,production_cookie_risk_resolved:false});fixture=null;
    },
  };
}
