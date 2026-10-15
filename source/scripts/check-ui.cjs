const { _electron: electron } = require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(artifacts,'ui-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
(async()=>{
  const application=await electron.launch({args:[root,'--disable-gpu'],env,timeout:60000});
  try{
    const page=await application.firstWindow();
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.getByText('Piyasaya bir adım yukarıdan bak.').waitFor({timeout:60000});
    await page.getByRole('button',{name:/Atak.*En fazla 12/}).click();
    await page.waitForTimeout(1900);
    let profile=await page.evaluate(()=>window.terminal.request('/snapshot'));
    assert.equal(profile.settings.max_positions,12);
    await page.getByRole('button',{name:/Otomatik karma/}).click();
    await page.waitForTimeout(1900);
    profile=await page.evaluate(()=>window.terminal.request('/snapshot'));
    assert.equal(profile.settings.max_positions,8);
    await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'mode',payload:{mode:'DEMO'}}));
    await page.waitForTimeout(2000);
    await page.locator('[data-testid="price-chart"] canvas').first().waitFor({timeout:20000});
    await page.screenshot({path:path.join(artifacts,'01-genel-bakis.png')});
    const pages=['Piyasalar','İşlemler','Stratejiler','Test laboratuvarı','Haber merkezi','Borsalar','Ayarlar'];
    const checks=[];
    for(const label of pages){
      await page.locator('nav').getByRole('button',{name:label,exact:label!=='Test laboratuvarı'}).click();
      await page.waitForTimeout(250);
      const overflow=await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2);
      assert.equal(overflow,false,'Yatay taşma: '+label);
      await page.screenshot({path:path.join(artifacts,label.replaceAll(' ','-')+'.png')});
      checks.push(label);
    }
    // Exercise actual IPC, persistence, risk sizing, close and research process.
    const started=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'start',payload:{}}));
    assert.equal(started.ok,true);
    const opened=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'demo_signal',payload:{symbol:'BTCUSDT',venue:'Binance',market:'futures'}}));
    assert.equal(opened.ok,true);
    const snapshot=await page.evaluate(()=>window.terminal.request('/snapshot'));
    assert(snapshot.positions.length>=1);
    assert(snapshot.metrics.risk_pct<=2);
    await page.locator('nav').getByRole('button',{name:'İşlemler',exact:true}).click();
    await page.waitForTimeout(2000);
    await page.screenshot({path:path.join(artifacts,'02-acik-pozisyon.png')});
    const closed=await page.evaluate(id=>window.terminal.request('/command','POST',{kind:'close',payload:{id}}),opened.id);
    assert.equal(closed.ok,true);
    const mode=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'mode',payload:{mode:'LIVE'}}));
    assert.equal(mode.ok,false);
    const job=await page.evaluate(()=>window.terminal.request('/jobs','POST',{kind:'backtest',strategy:'intraday',symbol:'BTCUSDT',venue:'Binance',market:'spot',source:'DEMO',months:7,fee_bps:10,slippage_bps:3}));
    assert.equal(job.ok,true);
    let completed;
    for(let i=0;i<60;i++){
      const state=await page.evaluate(()=>window.terminal.request('/snapshot'));
      completed=state.jobs.find(j=>j.id===job.id);
      if(completed.status!=='running')break;
      await page.waitForTimeout(500);
    }
    assert.equal(completed.status,'done',completed.message);
    const report=await page.evaluate(id=>window.terminal.request('/report/'+id),job.id);
    assert.equal(report.source,'DEMO');
    assert.equal(report.eligible,false);
    await page.locator('nav').getByRole('button',{name:'Test laboratuvarı'}).click();
    await page.waitForTimeout(2000);
    await page.screenshot({path:path.join(artifacts,'03-test-laboratuvari.png')});
    // At the minimum native window size, every page remains horizontally contained.
    await application.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1280,800));
    for(const label of ['Genel bakış',...pages]){
      await page.locator('nav').getByRole('button',{name:label,exact:label!=='Test laboratuvarı'}).click();
      await page.waitForTimeout(100);
      assert.equal(await page.locator('.content').evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'1280px taşma: '+label);
    }
    await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
    await page.screenshot({path:path.join(artifacts,'04-minimum-pencere.png')});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(artifacts,'ui-results.json'),JSON.stringify({pages:checks,consoleErrors:errors,research:completed,tradeFlow:'passed',liveGate:'passed',minimumSize:'passed'},null,2));
    console.log('PASS: eight screens, two window sizes, chart, IPC, trade open/close, live lock and research worker.');
  }finally{
    try{await application.evaluate(({app})=>app.quit());}catch{}
    await application.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
