const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(root,'artifacts','price-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const app=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await app.firstWindow();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.getByText('Piyasaya bir adım yukarıdan bak.').waitFor({timeout:60000});
  await page.locator('nav').getByRole('button',{name:'Piyasalar',exact:true}).click();
  let current;
  for(let i=0;i<60;i++){
   current=await page.evaluate(()=>window.terminal.request('/quote?symbol=BTCUSDT&venue=Binance&market=spot'));
   if(current.quote?.price_transport==='websocket')break;
   await page.waitForTimeout(500);
  }
  assert.equal(current.quote?.price_transport,'websocket','Real Binance last-trade WebSocket missing');
  const samples=[];
  for(let i=0;i<24;i++){
   const r=await page.evaluate(()=>window.terminal.request('/quote?symbol=BTCUSDT&venue=Binance&market=spot'));
   samples.push({price:r.quote.price,source:r.quote.price_transport,eventTime:r.quote.price_observed,age:r.timestamp-r.quote.price_observed});
   await page.waitForTimeout(400);
  }
  const ws=samples.filter(s=>s.source==='websocket');
  const events=new Set(ws.map(s=>s.eventTime));
  assert(ws.length>=16,'Last trade repeatedly fell back to REST');
  assert(events.size>=5,'Last-trade timestamp did not advance independently of REST');
  const maxAge=Math.max(...samples.map(s=>s.age));
  assert(maxAge<5,'Last-trade updates are stale');
  await page.getByTestId('price-freshness').waitFor();
  assert.match(await page.getByTestId('price-freshness').textContent(),/Son işlem.*sn önce/);
  await page.locator('.content').evaluate(el=>el.scrollTop=0);
  await page.screenshot({path:path.join(root,'artifacts','10-binance-fiyat-guncelligi.png')});
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1280,800));
  await page.waitForTimeout(500);
  assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  assert.deepEqual(errors,[]);
  const state=await page.evaluate(()=>window.terminal.request('/snapshot'));
  fs.writeFileSync(path.join(root,'artifacts','price-results.json'),JSON.stringify({version:state.version,time:new Date().toISOString(),uniquePriceEvents:events.size,websocketSamples:ws.length,maxAge,samples,errors},null,2));
  console.log(JSON.stringify({result:'PASS',version:state.version,uniquePriceEvents:events.size,websocketSamples:ws.length,maxAge}));
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
