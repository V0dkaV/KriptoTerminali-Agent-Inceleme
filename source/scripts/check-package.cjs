const {_electron:electron}=require('playwright');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const binary=process.argv[2]||path.join(root,'out','Kripto Terminali-win32-x64','KriptoTerminali.exe');
const userData=path.join(root,'artifacts','package-data-'+Date.now());
const env={...process.env,KRIPTO_TEST_HIDDEN:'1',KRIPTO_DISABLE_LOCAL_AI:'1',KRIPTO_DATA_DIR:userData};
delete env.ELECTRON_RUN_AS_NODE;
let application;
async function launch(){
  application=await electron.launch({executablePath:binary,args:['--disable-gpu'],env,timeout:60000});
  const page=await application.firstWindow();
  await page.getByRole('group',{name:'Arayüz görünümü'}).getByRole('button',{name:'Pro',exact:true}).click();
  await page.getByText('Piyasaya bir adım yukarıdan bak.').waitFor({timeout:60000});
  return page;
}
async function close(){
  try{await application.evaluate(({app})=>app.quit());}catch{}
  await application.close();
}
(async()=>{
  try{
    let page=await launch();
    await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'mode',payload:{mode:'DEMO'}}));
    const started=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'start',payload:{}}));
    assert(started.ok);
    const opened=await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'demo_signal',payload:{symbol:'BTCUSDT',venue:'Binance',market:'futures'}}));
    assert(opened.ok,opened.message);
    await page.evaluate(()=>window.terminal.request('/command','POST',{kind:'pause',payload:{}}));
    const saved=await page.evaluate(()=>window.terminal.saveCredential({venue:'Bybit',key:'FAKE_TEST_KEY_ONLY_123',secret:'FAKE_TEST_SECRET_ONLY_456',testnet:true}));
    assert(saved.ok);
    const vault=fs.readFileSync(path.join(userData,'vault.enc'));
    assert(!vault.includes(Buffer.from('FAKE_TEST_SECRET_ONLY_456')));
    await page.screenshot({path:path.join(root,'artifacts','05-paketli-uygulama.png')});
    await close();
    page=await launch();
    let snapshot=await page.evaluate(()=>window.terminal.request('/snapshot'));
    assert.equal(snapshot.running,false);
    assert(snapshot.positions.some(p=>p.id===opened.id));
    assert.equal(snapshot.connections.find(c=>c.venue==='Bybit').status,'stored');
    const closed=await page.evaluate(id=>window.terminal.request('/command','POST',{kind:'close',payload:{id}}),opened.id);
    assert(closed.ok);
    // Make sure the packaged Python worker can spawn itself and write reports.
    const job=await page.evaluate(()=>window.terminal.request('/jobs','POST',{kind:'backtest',strategy:'intraday',symbol:'BTCUSDT',venue:'Binance',market:'spot',source:'DEMO',months:7,fee_bps:10,slippage_bps:3}));
    assert(job.ok);
    let finished;
    for(let i=0;i<120;i++){
      snapshot=await page.evaluate(()=>window.terminal.request('/snapshot'));
      finished=snapshot.jobs.find(j=>j.id===job.id);
      if(finished.status!=='running')break;
      await page.waitForTimeout(500);
    }
    assert.equal(finished.status,'done',JSON.stringify(finished));
    assert.equal(snapshot.version,'0.8.0');
    fs.writeFileSync(path.join(root,'artifacts','package-results.json'),JSON.stringify({version:snapshot.version,standaloneDesktop:true,embeddedPython:true,restartPersistence:true,restartPaused:true,vaultEncrypted:true,researchWorker:true,liveLocked:!snapshot.live_gate.allowed},null,2));
    console.log('PASS: packaged desktop, bundled Python, persistence across restart, encrypted vault and research worker.');
  }finally{if(application)await close().catch(()=>{});}
})().catch(e=>{console.error(e);process.exitCode=1;});
