/** Real UI scenarios for the supported CUA browser adapter. Never launches a
 * second browser technology, injects a session, or reads a password/token.
 * Supply the newly generated approved fixture directly from driver memory.
 */
export const origins = Object.freeze({portal:'http://localhost:19092', mdm:'http://localhost:19090', pm:'http://localhost:19091', idp:'http://localhost:19081'});

export function checkedBusinessLink(value, service) {
  const url = new URL(value);
  if (url.origin !== origins[service] || url.username || url.password || url.search || url.hash) throw Error('Unsafe business deep link');
  if (!url.pathname.startsWith(service === 'pm' ? '/projects/' : '/mdm/')) throw Error('Unexpected business deep link path');
  return url.href;
}

export class BrowserCaseBlocked extends Error {
  constructor(stage,safetyStop=false) { super('Real browser case blocked: '+stage); this.name='BrowserCaseBlocked'; this.stage=stage; this.safetyStop=safetyStop; }
}

function stopped(error) {
  return /computer use.*stopped|safety stop|paused document response|access denied|user.*cancel/i.test(String(error?.message));
}

export async function observe(tab) {
  try { return await tab.playwright.domSnapshot(); }
  catch (error) {
    // A normal DOM read timeout is distinct from a safety stop or a paused
    // response. Only the documented AX observation is tried, never raw CDP.
    if (stopped(error) || !String(error?.message).includes('Runtime.evaluate')) throw new BrowserCaseBlocked('document-observation',stopped(error));
    return await tab.getAXState({emit:false});
  }
}

async function ready(locator, stage, timeoutMs=10000) {
  const deadline=Date.now()+timeoutMs;
  const attempts=Math.min(15,Math.ceil(timeoutMs/3000));
  for(let attempt=0;attempt<attempts;attempt++) {
    try {await locator.waitFor({state:'visible',timeoutMs:Math.max(1,deadline-Date.now())});return;}
    catch(error) {
      if(stopped(error) || !/timed out|timeout|deadline exceeded/i.test(String(error.message)) || Date.now()>=deadline || attempt===attempts-1) throw new BrowserCaseBlocked(stage,stopped(error));
    }
  }
}

async function openedTab(browser, previous, expectedOrigin, owner) {
  for (let attempt=0; attempt<3; attempt++) {
    const tabs=await browser.tabs.list();
    const candidates=tabs.filter(t=>!previous.has(t.id) && t.url && new URL(t.url).origin===expectedOrigin);
    if (candidates.length===1) {
      const tab=await browser.tabs.get(candidates[0].id);
      await observe(tab);
      return tab;
    }
    if (candidates.length>1) throw new BrowserCaseBlocked('ambiguous-new-tab');
    const pending=tabs.filter(t=>!previous.has(t.id));
    if (pending.length===1) {
      const tab=await browser.tabs.get(pending[0].id);
      try {await tab.playwright.waitForURL(expectedOrigin+'/**',{timeoutMs:15000});}
      catch(error) {throw new BrowserCaseBlocked('new-tab-did-not-reach-expected-app',stopped(error));}
      await observe(tab);
      return tab;
    }
    await observe(owner);
  }
  throw new BrowserCaseBlocked('expected-new-tab-not-observed');
}

async function nativeDate(locator, year, month, day) {
  await locator.click();
  await locator.press('ArrowLeft'); await locator.press('ArrowLeft');
  await locator.pressSequentially(year); await locator.press('ArrowRight');
  await locator.pressSequentially(month); await locator.press('ArrowRight');
  await locator.pressSequentially(day); await locator.press('Tab');
  if (await locator.evaluate(el=>el.value) !== `${year}-${month}-${day}`) throw new BrowserCaseBlocked('date-input-not-committed');
}

export async function portalToMdm({browser, portal, fixture, capture}) {
  if (await portal.url() !== origins.portal+'/') await portal.goto(origins.portal+'/');
  await observe(portal);
  const username=portal.playwright.getByRole('textbox',{name:'用户名',exact:true});
  const entry=portal.playwright.getByRole('link',{name:'进入主数据管理（新标签页）',exact:true});
  await ready(username.or(entry).first(),'portal-login-or-existing-session');
  if (await username.count() && await username.isVisible()) {
    await username.fill(fixture.users.signer.username);
    await portal.playwright.getByRole('textbox',{name:'密码',exact:true}).fill(fixture.users.signer.password);
    await portal.playwright.getByRole('button',{name:'登录',exact:true}).click();
  }
  await ready(portal.playwright.getByRole('link',{name:'Synthetic signer',exact:true}),'expected-synthetic-portal-identity');
  await ready(portal.playwright.getByRole('link',{name:'进入主数据管理（新标签页）',exact:true}),'portal-authenticated');
  await capture(portal,'01-authenticated-portal.jpg');
  const previous=new Set((await browser.tabs.list()).map(t=>t.id));
  await portal.playwright.getByRole('link',{name:'进入主数据管理（新标签页）',exact:true}).click();
  const mdm=await openedTab(browser,previous,origins.mdm,portal);
  await ready(mdm.playwright.getByRole('button',{name:'plus 新建项目',exact:true}),'mdm-sso-and-permission');
  await capture(mdm,'02-sso-entered-mdm.jpg');
  return mdm;
}

export async function createAndLink({browser, mdm, runKey, capture, control, recover=false}) {
  const mdmName='Synthetic MDM regression '+runKey;
  const pmName='Synthetic PM regression '+runKey;
  await mdm.playwright.getByRole('button',{name:'plus 新建项目',exact:true}).click();
  await observe(mdm);
  await ready(mdm.playwright.getByRole('textbox',{name:'* 项目名称',exact:true}),'new-project-form-visible');
  await mdm.playwright.getByRole('textbox',{name:'* 项目名称',exact:true}).fill(mdmName);
  await mdm.playwright.getByRole('textbox',{name:'项目描述',exact:true}).fill('仅本机隔离合成用户流程回归；不接触真实项目');
  await mdm.playwright.getByRole('button',{name:'创建项目',exact:true}).click();
  await ready(mdm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}),'registered-project-created');
  return await linkRegisteredProject({browser,mdm,runKey,capture,mdmName,pmName,control,recover});
}

export async function linkRegisteredProject({browser,mdm,runKey,capture,mdmName,pmName,control,recover=false}) {
  await mdm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}).click();
  await observe(mdm);
  await ready(mdm.playwright.getByRole('tab',{name:'创建并关联 PM 项目',exact:true}),'pm-create-permission');
  await mdm.playwright.getByRole('tab',{name:'创建并关联 PM 项目',exact:true}).click();
  const field=mdm.playwright.getByRole('textbox',{name:'* PM 项目编号',exact:true});
  const delegate=mdm.playwright.getByRole('link',{name:'授权 PM 项目操作',exact:true});
  await ready(field.or(delegate).first(),'pm-authority-check-complete');
  if (await delegate.count() && await delegate.isVisible()) {
    await delegate.click();
    await ready(mdm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}),'pm-user-delegation-callback');
    await mdm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}).click();
    await ready(mdm.playwright.getByRole('tab',{name:'创建并关联 PM 项目',exact:true}),'pm-create-after-delegation');
    await mdm.playwright.getByRole('tab',{name:'创建并关联 PM 项目',exact:true}).click();
  }
  await ready(field,'pm-required-fields-loaded');
  await mdm.playwright.getByRole('textbox',{name:'* PM 项目编号',exact:true}).fill('REG-'+runKey);
  await mdm.playwright.getByRole('textbox',{name:'* PM 项目名称',exact:true}).fill(pmName);
  for (const [label,option] of [['* PM 产品类型','单抗'],['* PM 当前执行阶段','临床前'],['* PM 目标阶段','IND'],['* PM 执行负责人','Synthetic signer']]) {
    const select=mdm.playwright.getByRole('combobox',{name:label,exact:true});
    await select.click();
    await observe(mdm);
    const controls=await select.getAttribute('aria-controls');
    if (!controls || !/^[a-zA-Z0-9_-]+$/.test(controls)) throw new BrowserCaseBlocked('select-popup-not-identified');
    await mdm.playwright.locator('.ant-select-dropdown').filter({has:mdm.playwright.locator('[id="'+controls+'"]')}).getByText(option,{exact:true}).filter({visible:true}).click();
  }
  await nativeDate(mdm.playwright.getByRole('textbox',{name:'* PM 计划开始日期',exact:true}),'2026','11','03');
  await nativeDate(mdm.playwright.getByRole('textbox',{name:'* PM 计划结束日期',exact:true}),'2026','12','03');
  await mdm.playwright.getByRole('tabpanel',{name:'创建并关联 PM 项目',exact:true}).getByRole('textbox').last().fill('合成回归明确创建执行项目并建立严格一对一关联');
  const mdmUrl=checkedBusinessLink(await mdm.url(),'mdm');
  const projectCode=new URL(mdmUrl).pathname.split('/').at(-1);
  if (!/^CMAB-PRJ-\d{4}-\d{4,8}$/.test(projectCode)) throw new BrowserCaseBlocked('unrecognized-registered-project-code');
  let baseline,failed,recoveryProof;
  if (recover) {
    if (!control) throw new BrowserCaseBlocked('missing-owned-fixture-controller');
    baseline=await control('snapshot',{stage:'before-link-fault'});
    await control('fault-next-link',{project_code:projectCode});
  }
  await mdm.playwright.getByRole('button',{name:'创建 PM 执行项目并关联',exact:true}).dblclick();
  if (recover) {
    await ready(mdm.playwright.getByText('PM 已创建，正在完成本地关联',{exact:true}).first(),'remote-created-local-failed',15000);
    failed=await control('snapshot',{stage:'remote-created-local-failed'});
    const oldIds=new Set((baseline.pm.projects||[]).map(p=>p.id));
    const remote=(failed.pm.projects||[]).filter(p=>!oldIds.has(p.id));
    if (remote.length!==1 || (failed.mdm.links||[]).length!==(baseline.mdm.links||[]).length || failed.pm.receipts!==baseline.pm.receipts+1) throw new BrowserCaseBlocked('fault-did-not-isolate-local-commit');
    const operation=failed.mdm.requests.find(r=>r.pm_project_id===remote[0].id);
    if (!operation || operation.status!=='remote_created' || operation.attempts!==1) throw new BrowserCaseBlocked('remote-result-not-persisted-before-retry');
    recoveryProof={request_id:operation.request_id,pm_project_id:remote[0].id};
    await capture(mdm,'recovery-01-remote-created-local-failed.jpg');
    if (recover==='prepare') return {status:'awaiting-retry',pmName,mdmName,mdmUrl,projectCode,recoveryProof,baseline,failed,mdm_tab_id:mdm.id};
    await ready(mdm.playwright.getByRole('button',{name:'沿用同一请求重试',exact:true}),'retry-lease-expired',45000);
    await mdm.playwright.getByRole('button',{name:'沿用同一请求重试',exact:true}).dblclick();
  }
  return await verifyLinkedProject({browser,mdm,pmName,mdmName,mdmUrl,projectCode,capture,control,recover,recoveryProof,baseline,failed});
}

export async function finishRecoveryScenario({browser,mdm,plan,capture,control}) {
  if (await mdm.url()!==plan.mdmUrl || plan.status!=='awaiting-retry') throw new BrowserCaseBlocked('retry-context-changed');
  await ready(mdm.playwright.getByRole('button',{name:'沿用同一请求重试',exact:true}),'retry-lease-expired',45000);
  await mdm.playwright.getByRole('button',{name:'沿用同一请求重试',exact:true}).dblclick();
  return await verifyLinkedProject({...plan,browser,mdm,capture,control,recover:true});
}

async function verifyLinkedProject({browser,mdm,pmName,mdmName,mdmUrl,projectCode,capture,control,recover,recoveryProof,baseline,failed}) {
  const link=mdm.playwright.getByRole('link',{name:'打开 PM 执行项目',exact:true});
  await ready(link,'real-pm-project-created-and-linked',15000);
  const pmUrl=checkedBusinessLink(await link.getAttribute('href'),'pm');
  await capture(mdm,'03-created-and-linked.jpg');
  const previous=new Set((await browser.tabs.list()).map(t=>t.id));
  await link.click();
  const pm=await openedTab(browser,previous,origins.pm,mdm);
  await ready(pm.playwright.getByRole('heading',{name:pmName,exact:true}),'real-pm-project-detail',15000);
  await capture(pm,'04-real-pm-project.jpg');
  await pm.playwright.getByRole('button',{name:'打开 MDM 登记项目',exact:true}).click();
  await ready(pm.playwright.getByRole('heading',{name:mdmName,exact:true}),'pm-to-mdm-context');
  await pm.reload();
  await ready(pm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}),'persisted-mdm-context');
  await pm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}).click();
  await ready(pm.playwright.getByRole('link',{name:'打开 PM 执行项目',exact:true}),'link-survives-refresh');
  await capture(pm,'05-returned-link-persists.jpg');
  if (recover) {
    const recovered=await control('snapshot',{stage:'same-request-recovered'});
    const operation=recovered.mdm.requests.find(r=>r.request_id===recoveryProof.request_id);
    if (!operation || operation.status!=='linked' || operation.attempts!==2 || operation.pm_project_id!==recoveryProof.pm_project_id || recovered.pm.receipts!==failed.pm.receipts || JSON.stringify(recovered.pm.projects.map(p=>p.id).sort())!==JSON.stringify(failed.pm.projects.map(p=>p.id).sort()) || recovered.mdm.links.length!==baseline.mdm.links.length+1) throw new BrowserCaseBlocked('retry-created-duplicates-or-changed-identity');
    await capture(pm,'recovery-02-same-request-one-remote-project.jpg');
  }
  return {pmUrl,mdmUrl,projectCode,mdmName,pmName,recoveryProof,mdm_tab_id:pm.id};
}

export async function activeProjectTab(browser,project) {
  const tab=await browser.tabs.get(project.mdm_tab_id);
  if (await tab.url()!==project.mdmUrl) throw new BrowserCaseBlocked('returned-project-tab-changed');
  await observe(tab);
  return tab;
}

export async function signRegisteredProject({mdm,fixture,capture}) {
  await reauthenticateProject({mdm,fixture,capture});
  await confirmVerifiedSignature({mdm,capture});
}

/** Invoke this and confirmVerifiedSignature in separate supported CUA cells.
 * The adapter must observe the verified parent document between the phases. */
export async function reauthenticateProject({mdm,fixture,capture}) {
  const frame=await beginActionProof({mdm,actionLabel:'审批立项',capture});
  await frame.getByRole('textbox',{name:'Username',exact:true}).fill(fixture.users.signer.username);
  await frame.getByRole('textbox',{name:'Password',exact:true}).fill(fixture.users.signer.password);
  await frame.getByRole('button',{name:'Sign In',exact:true}).click();
  await observe(mdm);
  await ready(mdm.playwright.getByRole('button',{name:'确认签署并提交',exact:true}),'fresh-identity-verified');
  await mdm.playwright.locator('iframe[title="签名密码验证"]').waitFor({state:'detached',timeoutMs:10000});
  await observe(mdm);
  await capture(mdm,'07-fresh-identity-verified.jpg');
}

export async function confirmVerifiedSignature({mdm,capture}) {
  await observe(mdm);
  if (await mdm.playwright.locator('form[data-signature-phase]').getAttribute('data-signature-phase') !== 'verified') throw new BrowserCaseBlocked('proof-no-longer-verified');
  await mdm.playwright.getByRole('button',{name:'确认签署并提交',exact:true}).click();
  await mdm.playwright.getByRole('dialog').waitFor({state:'hidden',timeoutMs:10000});
  await ready(mdm.playwright.getByText('已立项',{exact:true}).first(),'signed-business-status');
  await observe(mdm);
  await capture(mdm,'08-signed-project.jpg');
}

export async function prepareActionForm({mdm,actionLabel}) {
  const existing=mdm.playwright.getByRole('dialog',{name:new RegExp('^'+actionLabel+' · 电子签名')});
  if (!(await existing.count())) {
    if (await mdm.playwright.getByRole('dialog').count()) throw new BrowserCaseBlocked('another-dialog-is-open');
    await mdm.playwright.getByRole('button',{name:actionLabel,exact:true}).click();
  }
  await observe(mdm);
  await ready(mdm.playwright.getByRole('textbox',{name:'* 变更原因（最少 5 字）',exact:true}),'signature-form-visible');
  await mdm.playwright.getByRole('textbox',{name:'* 变更原因（最少 5 字）',exact:true}).fill('仅合成回归：验证有权限业务动作的再次认证');
  await mdm.playwright.getByPlaceholder('如：Phase I 数据评审通过 / 批文已签发 / 合规终止',{exact:true}).fill('合成项目内容复核后确认立项签名');
}

export async function beginActionProof({mdm,actionLabel,capture}) {
  await prepareActionForm({mdm,actionLabel});
  await mdm.playwright.getByRole('button',{name:'重新验证密码',exact:true}).click();
  await observe(mdm);
  const frame=mdm.playwright.frameLocator('iframe[title="签名密码验证"]');
  try {
    await ready(frame.getByRole('textbox',{name:'Username',exact:true}),'signature-iframe-document-ready',12000);
  } catch (error) {
    if (!error.safetyStop) await capture(mdm,'06-blocked-signature-frame.jpg');
    throw error;
  }
  return frame;
}

export async function negativeSigningCases({mdm,fixture,capture}) {
  let frame=await beginActionProof({mdm,actionLabel:'取消立项',capture});
  await capture(mdm,'10-fresh-password-frame.jpg');
  await frame.getByRole('textbox',{name:'Username',exact:true}).fill(fixture.users.signer.username);
  await frame.getByRole('textbox',{name:'Password',exact:true}).fill(fixture.users.signer.password+'-incorrect');
  await frame.getByRole('button',{name:'Sign In',exact:true}).click();
  await ready(frame.getByText(/incorrect|invalid|wrong|错误/i).first(),'wrong-password-rejection-visible');
  const body=await frame.locator('body').innerText();
  if (!/incorrect|invalid|wrong|错误/i.test(body)) throw new BrowserCaseBlocked('wrong-password-error-not-observed');
  if (await mdm.playwright.getByRole('button',{name:'确认签署并提交',exact:true}).count()) throw new BrowserCaseBlocked('wrong-password-unexpected-proof');
  // A supported locator click scrolls the non-interactive error text into view.
  // Do not use DOM mutation, raw CDP or a screenshot of a clipped error as proof.
  await frame.getByText(/incorrect|invalid|wrong|错误/i).first().click();
  await capture(mdm,'11-wrong-password-rejected.jpg');
  await cancelProofKeepsForm({mdm,capture});
  await rejectOtherIdentity({mdm,fixture,capture});
  return ['wrong-password-rejected','cancel-keeps-form','different-identity-rejected'];
}

export async function cancelProofKeepsForm({mdm,capture}) {
  await mdm.playwright.getByRole('button',{name:'取消认证并返回表单',exact:true}).click();
  const comment=mdm.playwright.getByRole('textbox',{name:'* 变更原因（最少 5 字）',exact:true});
  await ready(comment,'cancelled-form-retained');
  if (await comment.evaluate(el=>el.value) !== '仅合成回归：验证有权限业务动作的再次认证') throw new BrowserCaseBlocked('cancel-lost-form');
  await capture(mdm,'12-cancelled-form-retained.jpg');
  await ready(mdm.playwright.getByRole('button',{name:/^取\s*消$/}),'cancel-proof-returned-to-form');
  await mdm.playwright.getByRole('button',{name:/^取\s*消$/}).click();
  await mdm.playwright.getByRole('dialog').waitFor({state:'hidden',timeoutMs:10000});
}

export async function rejectOtherIdentity({mdm,fixture,capture}) {
  const frame=await beginActionProof({mdm,actionLabel:'取消立项',capture});
  await frame.getByRole('textbox',{name:'Username',exact:true}).fill(fixture.users.other.username);
  await frame.getByRole('textbox',{name:'Password',exact:true}).fill(fixture.users.other.password);
  await frame.getByRole('button',{name:'Sign In',exact:true}).click();
  await ready(mdm.playwright.getByText('再次认证未通过：请使用当前用户重新验证；原登录会话和表单已保留。',{exact:true}),'different-identity-rejected');
  await capture(mdm,'13-account-mismatch-rejected.jpg');
  await mdm.playwright.getByRole('button',{name:/^取\s*消$/}).click();
  await mdm.playwright.getByRole('dialog').waitFor({state:'hidden',timeoutMs:10000});
  await ready(mdm.playwright.getByText('已立项',{exact:true}).first(),'negative-cases-no-business-change');
}

/** Candidate official current-browser logout, not the product global-logout
 * button and not a claim about all devices or password-change revocation. */
export async function rpLogoutCurrentBrowser({browser,portal,pm,capture}) {
  const logout=await browser.tabs.new();
  const target=new URL('/api/logout',origins.idp);
  target.searchParams.set('client_id','mdm-signing-login');
  target.searchParams.set('post_logout_redirect_uri',origins.mdm+'/mdm/login');
  await logout.goto(target.href);
  await ready(logout.playwright.getByRole('link',{name:'统一身份登录',exact:true}),'rp-mdm-login');
  await portal.reload(); await pm.reload();
  for (const [name,tab] of [['portal',portal],['pm',pm]]) {
    await ready(tab.playwright.getByRole('textbox',{name:'用户名',exact:true}),'rp-'+name+'-session-rejected');
    await capture(tab,'rp-'+name+'-logged-out.jpg');
  }
  return {scope:'current-browser-only',token_in_url:false,all_devices_verified:false};
}

export async function runRecoveryCases({browser,portal,mdm,fixture,runKey,capture,control}) {
  const plan=await recoveryCreateScenario({browser,mdm,runKey,capture,control});
  const project=await finishRecoveryScenario({browser,mdm,plan,capture,control});
  const current=await activeProjectTab(browser,project);
  const restarted=await restartScenario({browser,portal,mdm:current,project,capture,control});
  const returned=await browser.tabs.get(restarted.mdm_tab_id);
  await outageScenario({mdm:returned,project,capture,control});
  return {status:'passed',project,cases:['remote-success-local-failure-same-request-double-retry','application-restart-keeps-sessions-and-project-links','real-502-form-session-preservation-and-recovery'].map(name=>({name,status:'passed'}))};
}

export async function recoveryCreateScenario({browser,mdm,runKey,capture,control}) {
  await mdm.playwright.getByRole('button',{name:'arrow-left 返回列表',exact:true}).click();
  await ready(mdm.playwright.getByRole('button',{name:'plus 新建项目',exact:true}),'recovery-project-list');
  return await createAndLink({browser,mdm,runKey,capture,control,recover:'prepare'});
}

export async function restartScenario({browser,portal,mdm,project,capture,control}) {
  const before=await control('snapshot',{stage:'before-process-restart'});
  const restart=await control('restart-apps');
  if (restart.health.mdm!==200 || restart.health.pm!==200 || restart.database_restarted || restart.idp_restarted) throw new BrowserCaseBlocked('application-only-restart-not-confirmed');
  const after=await control('snapshot',{stage:'after-process-restart'});
  if (JSON.stringify(before.mdm.links)!==JSON.stringify(after.mdm.links) || JSON.stringify(before.pm.projects)!==JSON.stringify(after.pm.projects)) throw new BrowserCaseBlocked('restart-changed-persisted-context');
  await mdm.reload();
  await ready(mdm.playwright.getByRole('heading',{name:project.mdmName,exact:true}),'mdm-session-survives-restart');
  await mdm.playwright.getByRole('tab',{name:'PM 执行项目',exact:true}).click();
  await ready(mdm.playwright.getByRole('link',{name:'打开 PM 执行项目',exact:true}),'restarted-link-persists');
  await capture(mdm,'restart-01-mdm-session-and-link.jpg');
  const previous=new Set((await browser.tabs.list()).map(t=>t.id));
  await mdm.playwright.getByRole('link',{name:'打开 PM 执行项目',exact:true}).click();
  const pm=await openedTab(browser,previous,origins.pm,mdm);
  await ready(pm.playwright.getByRole('heading',{name:project.pmName,exact:true}),'pm-session-survives-restart');
  await capture(pm,'restart-02-pm-session-and-project.jpg');
  await portal.reload();
  await ready(portal.playwright.getByRole('link',{name:'Synthetic signer',exact:true}),'portal-session-survives-restart');
  await capture(portal,'restart-03-portal-session.jpg');
  await pm.playwright.getByRole('button',{name:'打开 MDM 登记项目',exact:true}).click();
  await ready(pm.playwright.getByRole('heading',{name:project.mdmName,exact:true}),'restart-pm-to-mdm-context');
  return {status:'passed',mdm_tab_id:pm.id};
}

export async function outageScenario({mdm,project,capture,control}) {
  const before=await control('snapshot',{stage:'before-transient-outage'});
  await prepareActionForm({mdm,actionLabel:'审批立项'});
  const comment=mdm.playwright.getByRole('textbox',{name:'* 变更原因（最少 5 字）',exact:true});
  await control('stop-mdm');
  await mdm.playwright.getByRole('button',{name:'重新验证密码',exact:true}).click();
  await ready(mdm.playwright.getByText('无法发起签名认证，请检查权限、对象状态和身份服务',{exact:true}),'outage-rejection-visible');
  if (await comment.evaluate(el=>el.value)!=='仅合成回归：验证有权限业务动作的再次认证' || await mdm.url()!==project.mdmUrl) throw new BrowserCaseBlocked('outage-lost-form-or-session');
  await capture(mdm,'outage-01-502-keeps-form.jpg');
  await control('start-mdm');
  await ready(mdm.playwright.getByRole('button',{name:'重新验证密码',exact:true}),'outage-retry-button-ready');
  await mdm.playwright.getByRole('button',{name:'重新验证密码',exact:true}).click();
  await ready(mdm.playwright.frameLocator('iframe[title="签名密码验证"]').getByRole('textbox',{name:'Username',exact:true}),'outage-recovered-real-frame');
  await capture(mdm,'outage-02-recovered-real-casdoor-frame.jpg');
  await cancelProofKeepsForm({mdm,capture});
  const final=await control('snapshot',{stage:'after-outage-recovery'});
  if (final.mdm.signatures!==before.mdm.signatures || final.mdm.status_history!==before.mdm.status_history) throw new BrowserCaseBlocked('outage-created-unconfirmed-business-change');
  return {status:'passed',form_preserved:true,session_preserved:true};
}

export async function runJointCases(context) {
  const cases=[];
  const record=(name,status)=>cases.push({name,status,time_utc:new Date().toISOString()});
  try {
    const mdm=await portalToMdm(context);
    record('portal-mdm-sso','passed');
    const project=await createAndLink({...context,mdm});
    record('create-link-doubleclick-deeplink-refresh','passed');
    const current=await activeProjectTab(context.browser,project);
    await reauthenticateProject({...context,mdm:current});
    record('fresh-embedded-reauthentication','passed');
    return {status:'awaiting-confirmation',cases,project,mdm_tab_id:current.id,synthetic_only:true};
  } catch(error) {
    const stage=error instanceof BrowserCaseBlocked ? error.stage : 'unexpected-ui-or-tool-result';
    record(stage,'blocked');
    let hint=String(error.message).slice(0,700);
    for(const item of Object.values(context.fixture?.users||{})) hint=hint.replaceAll(item.password,'[redacted]');
    return {status:'blocked',cases,blocker:stage,error_hint:hint,tool_stop:Boolean(error.safetyStop),synthetic_only:true};
  }
}
