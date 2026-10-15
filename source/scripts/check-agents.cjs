const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DATA_DIR:path.join(root,'artifacts','agent-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
delete env.KRIPTO_DISABLE_LOCAL_AI;
(async()=>{
 const application=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await application.firstWindow();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.getByRole('button',{name:'Gerçek veride başlat'}).waitFor({timeout:60000});
  const history=await page.evaluate(()=>window.terminal.request('/history?symbol=BTCUSDT&venue=Binance&market=spot&months=12&interval=1d'));
  assert.equal(history.source,'PAPER');assert.equal(history.coverage.status,'complete');
  await page.getByLabel('Başlangıç sanal bakiyesi',{exact:true}).fill('1000');
  await page.getByRole('button',{name:'Gerçek veride başlat'}).click();
  let s;
  for(let i=0;i<180;i++){
   await page.waitForTimeout(1000);
   s=await page.evaluate(()=>window.terminal.request('/snapshot'));
   if(i%20===0)console.log(JSON.stringify({seconds:i,ai:s.local_ai.status,busy:s.local_ai.busy,experiments:s.local_ai.experiments.map(e=>e.status),selectors:s.learning.length}));
   if(s.local_ai.report.created_at&&s.local_ai.experiments.some(e=>['forward_queue','insufficient_data'].includes(e.status)))break;
  }
  assert(s.local_ai.report.created_at,'No local real-news report');
  assert(s.local_ai.experiments.length,'No automatic local AI experiment');
  const exp=s.local_ai.experiments.at(-1);
  assert(['forward_queue','insufficient_data'].includes(exp.status));
  assert(exp.qualification&&Number.isFinite(exp.qualification.net_r));
  assert(s.local_ai.report.events.every(e=>s.news.some(n=>n.id===e.event_id)));
  assert(!s.local_ai.paid_api);
  assert.equal(s.local_ai.report.knowledge.version,s.knowledge.version);
  assert.equal(s.local_ai.report.knowledge.card_ids.length,5);
  assert(s.local_ai.report.history_context.some(h=>h.symbol==='BTCUSDT'&&h.months===12));
  assert(s.local_ai.report.knowledge_ids.every(id=>s.local_ai.report.knowledge.card_ids.includes(id)));
  await page.waitForTimeout(2000);
  await page.locator('.local-ai-panel').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'artifacts','09-yerel-ai-haber-arastirma.png')});
  await application.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1280,800));
  await page.waitForTimeout(500);
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(root,'artifacts','agents-results.json'),JSON.stringify({time:new Date().toISOString(),version:s.version,knowledgeVersion:s.knowledge.version,
    localAI:s.local_ai,newsSources:s.news_sources,selectors:s.learning,errors},null,2));
  console.log('PASS: local Qwen model, current public news, structured source-bound report, automatic experiment and queue.');
 }finally{
  try{await application.evaluate(({app})=>app.quit());}catch{}
  await application.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
