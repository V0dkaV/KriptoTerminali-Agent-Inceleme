const {_electron:electron}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(artifacts,'execution-status-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const application=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await application.firstWindow();
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.getByText('Portföyün bir bakışta.',{exact:true}).waitFor({timeout:60000});
  const initial=await page.evaluate(()=>window.terminal.request('/snapshot'));
  const settings=await page.evaluate(body=>window.terminal.request('/settings','POST',body),{...initial.settings,auto_universe:false,allowlist:['BTCUSDT','ETHUSDT']});
  assert.notEqual(settings.ok,false,settings.message);
  const started=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'paper_session',payload:{balance:10000}}));
  assert.notEqual(started.ok,false,started.message);
  let state;
  let concurrentAnalysis;
  for(let i=0;i<120;i++){
   state=await page.evaluate(()=>window.terminal.request('/snapshot'));
   assert(state.execution,'Execution diagnostics missing');
   if(state.execution.analysis.completed>0&&state.execution.training.running&&state.execution.heartbeat_age!=null){concurrentAnalysis=state.execution;break;}
   if(i%20===0)console.log(JSON.stringify({seconds:i,execution:state.execution}));
   await page.waitForTimeout(1000);
  }
  assert.equal(state.mode,'PAPER');
  assert.equal(state.metrics.initial,10000);
  assert(state.execution.analysis.completed>0,'Real closed-candle analysis did not start');
  assert(concurrentAnalysis,'Closed-candle analysis and heartbeat must be available while background training is running');
  assert(state.execution.analysis.expected>=state.execution.analysis.completed);
  assert(state.execution.heartbeat_age>=0&&state.execution.heartbeat_age<30,'Position heartbeat missing or stale');
  assert.deepEqual(state.execution.signal_intervals,['15m','4h']);
  assert.equal(typeof state.execution.training.running,'boolean');
  assert(state.execution.training.queued>=0);
  assert(state.execution.reasons.every(reason=>reason.label&&reason.count>=0));
  const checks=[];
  for(const [width,height] of [[1440,960],[1280,800]]){
   await application.evaluate(({BrowserWindow},size)=>BrowserWindow.getAllWindows()[0].setSize(...size),[width,height]);
   for(const view of ['Sade','Pro']){
    await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:view,exact:true}).click();
    const card=page.getByTestId('execution-status').filter({visible:true});
    await card.waitFor({state:'visible'});
    assert.equal(await page.getByTestId('execution-status').filter({visible:true}).count(),1,'Exactly one diagnostics card should be visible');
    await card.scrollIntoViewIfNeeded();
    assert.match(await card.innerText(),/İşlem neden açılmıyor\?/);
    assert.match(await card.getByTestId('execution-analysis').innerText(),/\d+\s*\/\s*\d+ analiz/);
    assert.match(await card.innerText(),/15 dk \/ 4 saat/);
    assert.equal(await card.evaluate(element=>element.scrollWidth>element.clientWidth+2),false,`${view} ${width} card overflow`);
    assert.equal(await page.locator('.content').evaluate(element=>element.scrollWidth>element.clientWidth+2),false,`${view} ${width} content overflow`);
    await page.screenshot({path:path.join(artifacts,`execution-status-${view.toLowerCase()}-${width}.png`)});
    checks.push({view,width,height,visible:true,overflow:false});
   }
  }
  // A running flag alone cannot prove that an actual child worker can finish.
  let trained=0;
  for(let i=0;i<120;i++){
   const latest=await page.evaluate(()=>window.terminal.request('/snapshot'));
   trained=latest.learning.filter(x=>x.version).length;
   if(trained)break;
   await page.waitForTimeout(1000);
  }
  assert(trained>0,'At least one actual background model must finish with desktop ownership active');
  await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'pause',payload:{}}));
  await page.waitForTimeout(2300);
  assert.match(await page.getByTestId('execution-status').filter({visible:true}).innerText(),/Yeni girişler duraklatıldı/);
  assert.deepEqual(errors,[]);
  const final=await page.evaluate(()=>window.terminal.request('/snapshot'));
  const latestAnalyses=final.decisions.map(({venue,symbol,market,strategy,candle_time,observed,block_code,message,candidate_checks})=>({venue,symbol,market,strategy,candle_time,observed,block_code,message,candidate_checks}));
  fs.writeFileSync(path.join(artifacts,'execution-status-results.json'),JSON.stringify({version:final.version,time:new Date().toISOString(),source:'Actual public BTC/ETH quotes and closed-candle analysis, isolated paper account; no synthetic performance results',execution:state.execution,analysisDuringTraining:true,finalExecution:final.execution,trainedContexts:final.learning.filter(x=>x.version).length,latestAnalyses,paused:!final.running,checks,errors},null,2));
  console.log('PASS: actual execution diagnostics, background-learning counters, reasons, Sade/Pro, two window sizes, pause status.');
 }finally{
  try{await application.evaluate(({app})=>app.quit());}catch{}
  await application.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
