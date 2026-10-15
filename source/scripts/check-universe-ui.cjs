const {_electron:electron,chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),artifacts=path.join(root,'artifacts');
fs.mkdirSync(artifacts,{recursive:true});
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:path.join(artifacts,'universe-ui-data-'+Date.now())};
delete env.ELECTRON_RUN_AS_NODE;
async function until(fn,ms=90000){const end=Date.now()+ms;while(Date.now()<end){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,250));}throw new Error('UI acceptance timed out');}
(async()=>{
 let base,publicResult;const checks=[],errors=[];
 if(process.env.KRIPTO_FIXTURE_ONLY!=='1'){
 const app=await electron.launch(process.argv[2]?{executablePath:process.argv[2],args:['--disable-gpu'],env,timeout:60000}:{args:[root,'--disable-gpu'],env,timeout:60000});
 try{
  const page=await app.firstWindow();page.on('pageerror',e=>errors.push(e.message));
  await page.getByText('Portföyün bir bakışta.').waitFor({timeout:60000});
  const call=(route,body)=>page.evaluate(({route,body})=>window.terminal.request(route,body===undefined?'GET':'POST',body),{route,body});
  base=await call('/snapshot');const session=base.session.id,initial=base.metrics.initial;
  assert.equal(base.settings.auto_universe,true);
  assert((await call('/universe-refresh',{})).ok);
  let actual=await until(async()=>{const s=await call('/snapshot');return s.universe.discovered>60&&s.settings.allowlist.length>60?s:null;},120000);
  console.log('Real catalog discovered:',actual.universe.discovered);
  publicResult={discovered:actual.universe.discovered,active:actual.settings.allowlist.length,sources:actual.universe.sources,status:actual.universe.status};
  await page.locator('nav').getByRole('button',{name:'Piyasalar',exact:true}).click();
  await until(async()=>await page.locator('[data-testid="universe-coins"] button').count()===60);
  await page.getByRole('button',{name:'Sonraki coin sayfası'}).click();
  assert.equal(await page.locator('[data-testid="universe-coins"] button').count(),60);
  const target=actual.settings.allowlist.at(-1);
  await page.getByRole('textbox',{name:'Coin havuzunda ara'}).fill(target);
  assert.equal(await page.locator('[data-testid="universe-coins"] button').count(),1);
  await page.locator('[data-testid="universe-coins"] button').click();
  await page.getByRole('textbox',{name:'Coin havuzunda ara'}).fill('');
  await page.locator('.content').evaluate(e=>e.scrollTo(0,0));await page.waitForTimeout(100);
  await page.screenshot({path:path.join(artifacts,'universe-real-public.png')});
  // Actual settings and refresh must preserve the account/session.
  await page.locator('nav').getByRole('button',{name:'Ayarlar',exact:true}).click();
  await page.getByRole('checkbox',{name:'Otomatik coin keşfi'}).uncheck();
  assert((await page.getByRole('textbox',{name:'Manuel coin listesi'}).inputValue()).split('\n').filter(Boolean).length<=60);
  await page.getByRole('textbox',{name:'Manuel coin listesi'}).fill('BTCUSDT\nETHUSDT\nSOLUSDT');
  await page.getByRole('button',{name:'Ayarları kaydet',exact:true}).click();
  await until(async()=>{const s=await call('/snapshot');return s.settings.auto_universe===false&&s.settings.allowlist.length===3;});
  await page.getByRole('checkbox',{name:'Otomatik coin keşfi'}).check();
  await page.getByRole('button',{name:'Ayarları kaydet',exact:true}).click();
  actual=await until(async()=>{const s=await call('/snapshot');return s.settings.auto_universe&&s.settings.allowlist.length>60?s:null;});
  console.log('Auto/manual settings and automatic re-discovery passed.');
  assert.equal(actual.session.id,session);assert.equal(actual.metrics.initial,initial);
  // A paused mandate blocks entries even while the engine itself remains running.
  const plan=await call('/operations/plan',{capital:100,leverage:2,max_positions:2,duration_hours:1});assert(plan.ok,plan.message);
  assert((await call('/chat/action',{id:plan.action.id})).ok);
  assert((await call('/operations/pause',{})).ok);
  actual=await call('/snapshot');assert(actual.running);assert(actual.execution.entry_gate.blocked);
  await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
  await page.locator('[data-testid="execution-entry-gate"]:visible').waitFor();
  assert.match(await page.locator('.engine-status').innerText(),new RegExp(actual.execution.entry_gate.label));assert(await page.locator('.engine-status').isVisible());
  for(const size of [[1440,960],[1280,800]]){
   await app.evaluate(({BrowserWindow},size)=>BrowserWindow.getAllWindows()[0].setSize(...size),size);
   for(const view of ['Sade','Pro']){
    await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:view,exact:true}).click();
    for(const name of ['Genel bakış','Piyasalar','Ayarlar']){
     await page.locator('nav').getByRole('button',{name,exact:true}).click();await page.waitForTimeout(100);
     assert.equal(await page.locator('.content').evaluate(e=>e.scrollWidth>e.clientWidth+2),false,`${view} ${size[0]} ${name}`);
     assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false);checks.push({view,width:size[0],page:name});
    }
   }
  }
  await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
  await page.locator('[data-testid="execution-entry-gate"]:visible').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(artifacts,'universe-paused-mission.png')});
  await call('/command',{kind:'pause',payload:{}});
 }finally{try{await app.evaluate(({app})=>app.quit());}catch{}await app.close();}
 }else{
  const r=require('node:child_process').spawnSync(path.join(root,'.venv','Scripts','python.exe'),['-c',"import json,tempfile;from engine.core import Engine;e=Engine(tempfile.mkdtemp(prefix='universe-fixture-base-'));print(json.dumps(e.snapshot(),ensure_ascii=False));e.store.db.close()"],{cwd:root,env:{...env,PYTHONUTF8:'1'},encoding:'utf8',windowsHide:true});
  assert.equal(r.status,0,r.stderr);base=JSON.parse(r.stdout);
 }

 // Explicit UI-only fixture: 1,205 sample symbols test rendering bounds and error states.
 const fixture=structuredClone(base);fixture.mode='PAPER';fixture.running=true;
 fixture.settings.allowlist=['BTCUSDT',...Array.from({length:1204},(_,i)=>`TEST${String(i).padStart(4,'0')}USDT`)];
 fixture.settings.auto_universe=true;
 fixture.session.started_at=Date.now()/1000;
 fixture.decisions=Array.from({length:241},(_,i)=>({symbol:fixture.settings.allowlist[i],venue:'Binance',market:'spot',strategy:'intraday',observed:Date.now()/1000-i,regime:'range',message:'ARAYÜZ TESTİ: Örnek giriş kararı.',accepted:false}));
 fixture.universe={mode:'auto',status:'partial',discovered:1205,symbols:1205,eligible:90,analyzed:64,expected:4820,stream_symbols:60,scan_batch_size:16,scan_batch:fixture.settings.allowlist.slice(0,16),sources:[],error:'ARAYÜZ TESTİ: Örnek kaynak erişim hatası.',updated_at:Date.now()/1000};
 fixture.execution.entry_gate={blocked:true,code:'mission_paused',label:'Görev duraklatıldı',message:'ARAYÜZ TESTİ: Görev girişleri durdu; koruyucu çıkışlar sürer.'};
 const dist=path.join(root,'dist');
 const server=http.createServer((req,res)=>{const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);const file=path.resolve(dist,'.'+(name==='/'?'/index.html':name));if(!file.startsWith(dist+path.sep)){res.writeHead(403);res.end();return;}try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.html')?'text/html':'application/octet-stream');res.end(fs.readFileSync(file));}catch{res.writeHead(404);res.end();}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try{
  browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext();
  await context.addInitScript(fixture=>{window.__universeFixture=fixture;window.terminal={ready:async()=>({ready:true}),request:async route=>route==='/snapshot'?structuredClone(window.__universeFixture):route.startsWith('/quote')?{quote:null,mode:'DEMO'}:route.startsWith('/candles')?{rows:[],source:'DEMO'}:{ok:true,message:'ARAYÜZ TESTİ'},windowAction:async()=>{},openExternal:async()=>{}};},fixture);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.getByText('Portföyün bir bakışta.').waitFor();
  for(const size of [[1440,960],[1280,800]]){
   await page.setViewportSize({width:size[0],height:size[1]});
   for(const view of ['Sade','Pro']){
    await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:view,exact:true}).click();
    await page.locator('nav').getByRole('button',{name:'Piyasalar',exact:true}).click();
    await page.getByRole('textbox',{name:'Coin havuzunda ara'}).fill('');
    assert.equal(await page.locator('[data-testid="universe-coins"] button').count(),60);
    await page.getByRole('button',{name:'Sonraki coin sayfası'}).click();
    assert.equal(await page.locator('[data-testid="universe-coins"] button').count(),60);
    await page.getByRole('textbox',{name:'Coin havuzunda ara'}).fill('TEST1203');
    assert.equal(await page.locator('[data-testid="universe-coins"] button').count(),1);
    await page.getByRole('textbox',{name:'Coin havuzunda ara'}).fill('NOTACOIN');
    await page.getByText('Aramana uygun coin bulunamadı.').waitFor();
    assert.equal(await page.locator('.content').evaluate(e=>e.scrollWidth>e.clientWidth+2),false);
    await page.getByRole('textbox',{name:'Coin havuzunda ara'}).fill('');
    await page.locator('.content').evaluate(e=>e.scrollTo(0,0));await page.waitForTimeout(100);await page.screenshot({path:path.join(artifacts,`universe-fixture-${view.toLowerCase()}-${size[0]}.png`)});
    if(view==='Pro'){
     await page.locator('nav').getByRole('button',{name:'Genel bakış',exact:true}).click();
     await page.getByRole('button',{name:'Analizleri sayfalarla incele (241)',exact:true}).click();
     assert.equal(await page.locator('.adaptive-table tbody tr').count(),60);
     await page.getByRole('button',{name:'Sonraki analiz sayfası'}).click();
     assert.equal(await page.locator('.adaptive-table tbody tr').count(),60);
     await page.getByRole('button',{name:'Daha az göster',exact:true}).click();
     assert.equal(await page.locator('.adaptive-table tbody tr').count(),4);
    }
   }
  }
  assert.deepEqual(errors,[]);
 }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
 fs.writeFileSync(path.join(artifacts,process.env.KRIPTO_FIXTURE_ONLY==='1'?'universe-ui-fixture-results.json':'universe-ui-results.json'),JSON.stringify({version:base.version,packaged:!!process.argv[2],publicCatalog:publicResult,accountPreserved:publicResult?true:'not run',manualAndAutoSettings:publicResult?true:'not run',pausedMissionGate:publicResult?true:'not run',checks,fixture:{label:'UI-only sample universe',symbols:1205,renderedAtOnce:60,analysisRowsAtOnce:60,defaultAnalysisRows:4,searchAndPagination:'passed',emptyAndSourceError:'passed'},consoleErrors:errors},null,2));
 console.log(process.env.KRIPTO_FIXTURE_ONLY==='1'?'PASS: UI-only 1,205-symbol and 241-analysis fixtures; 60-item bounds, default 4 analysis rows, search, pagination, empty/error states, Sade/Pro at two sizes. Public flow was not rerun.':'PASS: real public catalog, account-preserving auto/manual settings, paused mission gate, 1,205-symbol UI fixture, 60-button render limit, Sade/Pro at two sizes.');
})().catch(e=>{console.error(e);process.exitCode=1;});
