const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(root,'artifacts','paper-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const application=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await application.firstWindow();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.getByRole('button',{name:'Gerçek veride başlat'}).waitFor({timeout:60000});
  await page.getByLabel('Başlangıç sanal bakiyesi',{exact:true}).fill('12000');
  await page.getByRole('button',{name:'Gerçek veride başlat'}).click();
  const taskPlan=await page.evaluate(()=>window.terminal.request('/operations/plan','POST',{capital:100,leverage:2,max_positions:3,duration_hours:24}));
  assert(taskPlan.ok,taskPlan.message);
  const taskReceipt=await page.evaluate(id=>window.terminal.request('/chat/action','POST',{id}),taskPlan.action.id);
  assert(taskReceipt.ok,taskReceipt.message);
  const scanStart=Date.now();let firstAnalysisMs=null,allCoinsMs=null;
  let state;
  let streams=0;
  for(let i=0;i<300;i++){
   await page.waitForTimeout(1000);
   state=await page.evaluate(()=>window.terminal.request('/snapshot'));
   if(firstAnalysisMs===null&&state.decisions.length)firstAnalysisMs=Date.now()-scanStart;
   if(allCoinsMs===null&&new Set(state.decisions.map(d=>d.symbol)).size>=24)allCoinsMs=Date.now()-scanStart;
   streams=state.markets.filter(q=>state.timestamp-(q.stream_observed||0)<10).length;
   if(i%20===0)console.log(JSON.stringify({seconds:i,markets:state.markets.length,streams,analyses:state.decisions.length,models:state.learning.filter(r=>r.schema===3&&r.version).length}));
   if(state.decisions.length>=64&&state.learning.filter(r=>r.schema===3&&r.version).length>=48&&streams>=24&&new Set(state.decisions.map(d=>d.symbol)).size>=24)break;
  }
  assert.equal(state.mode,'PAPER');
  assert.equal(state.metrics.initial,12000);
  assert(state.running);
  assert.equal(state.settings.allowlist.length,24);
  assert(state.markets.length>=48,'Expanded public quotes missing');
  assert(streams>=24,'Expanded public WebSocket streams missing');
  assert(new Set(state.decisions.map(d=>d.symbol)).size>=24,'Expanded actual market analysis missing');
  assert(state.learning.some(r=>r.schema===3),'Automatic real-history learning missing');
  assert(!state.closed.some(t=>t.sample));
  assert(state.learning.every(m=>m.schema===3));
  assert(state.decisions.filter(d=>d.regime!=='unavailable').every(d=>Array.isArray(d.candidates)));
  assert(state.learning.some(m=>m.families.length===5));
  assert.deepEqual(errors,[]);
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  await page.screenshot({path:path.join(root,'artifacts','06-gercek-verili-sanal-oturum.png')});
  await application.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1280,800));
  await page.waitForTimeout(500);
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  await page.screenshot({path:path.join(root,'artifacts','07-sanal-minimum.png')});
  await page.locator('.paper-learning').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'artifacts','08-anlik-analizler.png')});
  await page.locator('nav').getByRole('button',{name:'Piyasalar',exact:true}).click();
  await page.getByLabel('Coin havuzunda ara').fill('SOL');
  assert.equal(await page.locator('.market-tabs button').count(),1);
  await page.locator('.market-tabs button').click();
  await page.getByLabel('Coin havuzunda ara').fill('');
  assert.equal(await page.locator('.market-tabs button').count(),24);
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  await application.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1440,960));
  await page.waitForTimeout(1500);
  await page.screenshot({path:path.join(root,'artifacts','Piyasalar.png')});
  await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Sade',exact:true}).click();
  await page.locator('.content').evaluate(el=>el.scrollTop=0);
  await page.waitForTimeout(1000);
  await page.screenshot({path:path.join(root,'artifacts','11-sade-gercek-piyasa.png')});
  const operations=await page.evaluate(()=>window.terminal.request('/operations'));
  assert.equal(operations.mission.capital,100);
  assert(operations.mission.used_capital<=100.000001);
  await page.locator('nav').getByRole('button',{name:'İşlem merkezi',exact:true}).click();
  await page.getByTestId('operations-panel').waitFor();
  await page.waitForTimeout(2200);
  await page.screenshot({path:path.join(root,'artifacts','operations-real-market.png')});
  const report={packaged:!!process.argv[2],timing:{firstAnalysisMs,allCoinsMs,totalMs:Date.now()-scanStart},execution:state.execution,trainedContexts:state.learning.filter(r=>r.schema===3&&r.version).length,operations,version:state.version,time:new Date().toISOString(),mode:state.mode,balance:state.metrics.initial,streams,
    quotes:state.markets.map(q=>({venue:q.venue,symbol:q.symbol,market:q.market,price:q.price,mark:q.mark_price,age:state.timestamp-q.observed})),
    analyses:state.decisions,learning:state.learning,positions:state.positions,closed:state.closed,
    news:state.news_sources,settings:state.settings,universe:state.universe,errors};
  fs.writeFileSync(path.join(root,'artifacts','paper-results.json'),JSON.stringify(report,null,2));
  console.log('PASS: real public streams, automatic analysis, local learning, virtual session and responsive UI.');
 }finally{
  try{await application.evaluate(({app})=>app.quit());}catch{}
  await application.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
