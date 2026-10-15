const {_electron:electron}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(artifacts,'presentation-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
 const application=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await application.firstWindow();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.getByText('Portföyün bir bakışta.').waitFor({timeout:60000});
  assert.equal(await page.locator('nav button').count(),7);
  assert.equal(await page.locator('[data-testid="app-shell"]').getAttribute('class'),'app-shell presentation-simple');
  // DEMO candles and a labelled DEMO position exercise layout without claiming live/history performance.
  await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'mode',payload:{mode:'DEMO'}}));
  await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'start',payload:{}}));
  const opened=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'demo_signal',payload:{symbol:'BTCUSDT',venue:'Binance',market:'futures'}}));
  assert.equal(opened.ok,true);
  const before=await page.evaluate(()=>window.terminal.request('/snapshot'));
  await page.waitForTimeout(2100);
  await page.locator('[data-testid="price-chart"] canvas').first().waitFor({timeout:20000});
  assert(await page.locator('.positions-panel').getByText('BTC',{exact:false}).count()>0);
  const checks=[];
  for(const [width,height] of [[1440,960],[1280,800]]){
   await application.evaluate(({BrowserWindow},size)=>BrowserWindow.getAllWindows()[0].setSize(...size),[width,height]);
   for(const view of ['Sade','Pro']){
    await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:view,exact:true}).click();
    for(const label of ['Genel bakış','Piyasalar','İşlemler','Stratejiler','Ayarlar']){
     await page.locator('nav').getByRole('button',{name:label,exact:true}).click();
     await page.waitForTimeout(100);
     assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false,`${view} ${width} taşma: ${label}`);
     checks.push({view,width,height,page:label});
     console.log(view,width,label);
    }
    await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
    await page.screenshot({path:path.join(artifacts,`presentation-${view.toLowerCase()}-${width}.png`)});
   }
  }
  const after=await page.evaluate(()=>window.terminal.request('/snapshot'));
  assert.equal(after.mode,before.mode);
  assert.equal(after.metrics.initial,before.metrics.initial);
  assert(after.positions.some(p=>p.id===opened.id),'Görünüm değişimi pozisyonu korumalı');
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.reload();
  await page.getByText('Piyasaya bir adım yukarıdan bak.').waitFor({timeout:20000});
  assert.equal(await page.locator('nav button').count(),10);
  await page.locator('nav').getByRole('button',{name:'Piyasalar',exact:true}).click();
  for(const [label,months] of [['6 ay',6],['1 yıl',12]]){
   await page.getByRole('group',{name:'Grafik dönemi'}).getByRole('button',{name:label,exact:true}).click();
   await page.locator('[data-testid="history-summary"]').getByText(months===12?'1 yıllık geçmiş analizi':'6 aylık geçmiş analizi',{exact:true}).waitFor({timeout:150000});
   await page.locator('[data-testid="price-chart"] canvas').first().waitFor({timeout:20000});
   assert.match(await page.locator('[data-testid="history-summary"]').innerText(),/Örnek veri/);
   assert.match(await page.locator('[data-testid="history-summary"]').innerText(),months===12?/1 yıllık/:/6 aylık/);
   assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  }
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Sade',exact:true}).click();
  assert.equal(await page.getByRole('group',{name:'Mum zaman aralığı'}).getByRole('button').count(),1);
  await page.locator('[data-testid="history-summary"]').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(artifacts,'presentation-history-demo-12m.png')});
  await page.reload();
  await page.getByText('Portföyün bir bakışta.').waitFor({timeout:20000});
  assert.equal(await page.locator('nav button').count(),7);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(artifacts,'presentation-results.json'),JSON.stringify({checks,default:'simple',persistence:'passed',sameAccountAndPosition:'passed',ranges:'6/12 month DEMO candles via real endpoint; layout only',consoleErrors:errors},null,2));
  console.log('PASS: Sade/Pro, persistent appearance, same account/positions, 2 sizes, 6/12 month labelled DEMO history layout.');
 }finally{
  try{await application.evaluate(({app})=>app.quit());}catch{}
  await application.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1;});

