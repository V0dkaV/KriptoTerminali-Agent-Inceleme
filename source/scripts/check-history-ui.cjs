const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(root,'artifacts','history-ui-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const app=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await app.firstWindow();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.getByText('Portföyün bir bakışta.').waitFor({timeout:60000});
  await page.locator('nav').getByRole('button',{name:'Piyasalar',exact:true}).click();
  const cases=[];
  for(const [label,months] of [['6 ay',6],['1 yıl',12]]){
   await page.getByRole('group',{name:'Grafik dönemi'}).getByRole('button',{name:label,exact:true}).click();
   const summary=page.getByTestId('history-summary');
   await summary.waitFor({timeout:120000});
   await summary.getByText(months===12?'1 yıllık geçmiş analizi':'6 aylık geçmiş analizi',{exact:true}).waitFor({timeout:120000});
   assert.match(await summary.innerText(),/Dönem tamam/);assert.doesNotMatch(await summary.innerText(),/Örnek veri/);
   const history=await page.evaluate(m=>window.terminal.request('/history?symbol=BTCUSDT&venue=Binance&market=spot&months='+m+'&interval=1d'),months);
   assert.equal(history.source,'PAPER');assert.equal(history.coverage.status,'complete');assert(history.rows.length>170);
   assert.equal(await page.locator('.content').evaluate(e=>e.scrollWidth>e.clientWidth+2),false);
   await summary.scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(root,'artifacts',`history-real-${months}m.png`)});
   cases.push({months,source:history.source,coverage:history.coverage,summary:history.summary});
  }
  await page.locator('nav').getByRole('button',{name:'Stratejiler',exact:true}).click();
  await page.getByLabel('Kaynaklı analiz kütüphanesi').waitFor();
  assert.equal(await page.locator('.knowledge-card').count(),14);
  await page.getByLabel('Kütüphanede yöntem ara').fill('VWAP');
  assert.equal(await page.locator('.knowledge-card').count(),1);
  await page.locator('.knowledge-card summary').click();
  assert.match(await page.locator('.knowledge-card').innerText(),/Henüz hesaplanmıyor/);
  await page.getByLabel('Kütüphanede yöntem ara').fill('');
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1280,800));
  assert.equal(await page.locator('.content').evaluate(e=>e.scrollWidth>e.clientWidth+2),false);
  await page.locator('.research-library').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'artifacts','research-library.png')});
  const s=await page.evaluate(()=>window.terminal.request('/snapshot'));
  assert.equal(s.version,'0.7.2');assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(root,'artifacts','history-ui-results.json'),JSON.stringify({version:s.version,cases,libraryCards:14,errors},null,2));
  console.log('PASS: real 6/12m history through Electron bridge, chart analysis, library search/details, minimum size.');
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
