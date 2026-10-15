const {_electron:electron}=require('playwright');
const {spawnSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'artifacts');
const dataDir=path.join(artifacts,'review-ui-data-'+Date.now());
fs.mkdirSync(dataDir,{recursive:true});
const seed=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',[
 'import sys',
 'from engine.core import Engine',
 'e=Engine(sys.argv[1])',
 "e.settings.allowlist=['BTCUSDT','ETHUSDT'];e.store.set('settings',e.settings.model_dump());e.mode='DEMO';e.save()",
 "e.store.report('e'*32,dict(kind='backtest',strategy='intraday',symbol='BTCUSDT',venue='Binance',market='spot',months=7,source='DEMO',summary=dict(count=1,net=100,fees=0,funding=0),holdout=dict(net=100,count=1),max_drawdown=0,curve=[],warnings=['Denetim için oluşturulmuş sentetik eski rapor.']))",
].join('\n'),path.join(dataDir,'data')],{cwd:root,env:{...process.env,KRIPTO_DISABLE_LOCAL_AI:'1'},encoding:'utf8',windowsHide:true});
assert.equal(seed.status,0,seed.stderr);
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:dataDir};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const app=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await app.firstWindow();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.getByText('Portföyün bir bakışta.',{exact:true}).waitFor({timeout:60000});
  const call=(route,body)=>page.evaluate(({route,body})=>window.terminal.request(route,body?'POST':'GET',body),{route,body});
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.locator('nav').getByRole('button',{name:/Test laboratuvarı/}).click();
  await page.getByText('Yeniden test edilmeli',{exact:true}).waitFor();
  await page.locator('.report-list button').first().click();
  const warning=page.locator('.report-detail .notice').filter({hasText:'önceki gerçekleşme'});
  await warning.waitFor();
  const legacy=await call('/report/'+'e'.repeat(32));
  assert(legacy.needs_retest);assert.equal(legacy.summary.net,100);
  const checks=[];
  for(const size of [[1440,960],[1280,800]]){
   await app.evaluate(({BrowserWindow},size)=>BrowserWindow.getAllWindows()[0].setSize(...size),size);
   await warning.scrollIntoViewIfNeeded();
   assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
   assert.equal(await warning.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
   await page.screenshot({path:path.join(artifacts,`review-legacy-report-${size[0]}.png`)});
   checks.push({size,legacyWarning:true,overflow:false});
  }
  console.log('Legacy report warning and window sizes passed; checking research worker.');
  const job=await call('/jobs',{kind:'backtest',strategy:'intraday',symbol:'BTCUSDT',venue:'Binance',market:'spot',source:'DEMO',months:7,fee_bps:10,slippage_bps:3});assert(job.ok,job.message);
  let current;
  for(let i=0;i<240;i++){
   const state=await call('/snapshot');current=state.jobs.find(j=>j.id===job.id);
   if(current.status!=='running')break;
   await page.waitForTimeout(500);
  }
  assert.equal(current.status,'done',JSON.stringify(current));
  const report=await call('/report/'+job.id);
  assert.equal(report.execution_model,'bar-causal-v2');assert.equal(report.needs_retest,false);
  console.log('Corrected research worker passed; checking mission limits.');
  assert((await call('/command',{kind:'mode',payload:{mode:'PAPER'}})).ok);
  const before=await call('/snapshot');
  assert.notEqual((await call('/settings',{...before.settings,leverage:5,max_positions:4})).ok,false);
  const plan=await call('/operations/plan',{capital:100,leverage:5,max_positions:4,duration_hours:24});assert(plan.ok,plan.message);
  assert((await call('/chat/action',{id:plan.action.id})).ok);
  // Tightening the account must tighten the existing mission, without expanding it.
  const settings=(await call('/snapshot')).settings;
  assert.notEqual((await call('/settings',{...settings,leverage:2,max_positions:2})).ok,false);
  assert((await call('/operations/pause',{})).ok);
  await page.locator('nav').getByRole('button',{name:'İşlem merkezi',exact:true}).click();
  const status=page.getByTestId('mission-status');
  await status.getByText('Yeni girişler duraklatıldı',{exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.operations-mission-meta')?.textContent.includes('en fazla ×2'));
  assert.match(await status.innerText(),/\/ 2 açık pozisyon · en fazla ×2/);
  const final=await call('/snapshot');const operations=await call('/operations');
  assert.equal(final.session.id,before.session.id);assert.equal(final.metrics.initial,before.metrics.initial);
  assert.equal(operations.mission.leverage,5);assert.equal(operations.mission.effective_leverage,2);assert.equal(operations.mission.effective_max_positions,2);
  await page.locator('.content').evaluate(el=>{el.scrollTop=0;});
  await page.screenshot({path:path.join(artifacts,'review-effective-caps.png')});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(artifacts,'review-ui-results.json'),JSON.stringify({version:final.version,time:new Date().toISOString(),packaged:!!process.argv[2],checks,legacyReport:{needsRetest:legacy.needs_retest,preservedNet:legacy.summary.net,synthetic:true},newReport:{executionModel:report.execution_model,needsRetest:report.needs_retest,synthetic:true},effectiveCaps:{approvedLeverage:5,effectiveLeverage:2,approvedPositions:4,effectivePositions:2},accountPreserved:true,errors},null,2));
  console.log('PASS: legacy report warning, corrected research worker, effective mission caps, two window sizes, account preserved.');
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
