const {spawn,spawnSync}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');const artifacts=path.join(root,'artifacts');
const dir=path.join(artifacts,'universe-engine-data-'+Date.now());
const source=process.argv.includes('--source');
const binary=source?path.join(root,'.venv/Scripts/python.exe'):(process.argv[2]||path.join(root,'engine-dist/kripto-engine/kripto-engine.exe'));
const token=crypto.randomBytes(32).toString('hex');
const child=spawn(binary,[...(source?['-m','engine.main']:[]),'--data-dir',dir],{cwd:root,windowsHide:true,env:{...process.env,KRIPTO_DISABLE_LOCAL_AI:'1',PYTHONUTF8:'1'},stdio:['pipe','pipe','pipe']});
let out='',err='';child.stdout.on('data',x=>out+=x);child.stderr.on('data',x=>err+=x);
child.stdin.write(JSON.stringify({token,watch_parent:true})+'\n');
async function until(fn,timeout=60000){const start=Date.now();while(Date.now()-start<timeout){const r=await fn();if(r)return r;await new Promise(r=>setTimeout(r,500));}throw Error('Timeout '+err.slice(-1000));}
(async()=>{try{
 const ready=await until(()=>out.match(/KRIPTO_READY (\{[^\n]+\})/));const base='http://127.0.0.1:'+JSON.parse(ready[1]).port;
 const call=async(route,body)=>{const r=await fetch(base+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});assert(r.ok,await r.clone().text());return r.json();};
 await until(async()=>{try{return(await call('/health')).ok;}catch{return false;}});
 const initial=await call('/snapshot');
 let state=await until(async()=>{const s=await call('/snapshot');return s.universe.discovered>100&&s.markets.length>100?s:null;},90000);
 assert.equal(state.version,'0.8.0');assert.equal(state.session.id,initial.session.id);assert.equal(state.metrics.initial,initial.metrics.initial);
 for(const key of ['trade_risk','total_risk','leverage','max_positions'])assert.equal(state.settings[key],initial.settings[key]);
 assert(state.settings.allowlist.length>100);assert.equal(state.running,false);
 assert(state.universe.sources.some(s=>s.status==='ready'));
 assert((await call('/command',{kind:'start',payload:{}})).ok);
 const batches=new Set();let ticks=0;
 state=await until(async()=>{
  const s=await call('/snapshot');if(s.universe.scan_batch.length)batches.add(s.universe.scan_batch.join(','));
  if(++ticks%40===0)console.log(JSON.stringify({analyses:s.decisions.length,models:s.learning.filter(x=>x.version).length,batches:batches.size}));
  return s.decisions.some(d=>!['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','DOTUSDT','LTCUSDT','BCHUSDT','TRXUSDT','SUIUSDT','ICPUSDT','NEARUSDT','APTUSDT','ARBUSDT','OPUSDT','ATOMUSDT','UNIUSDT','AAVEUSDT','FILUSDT','INJUSDT'].includes(d.symbol))&&s.learning.filter(x=>x.version).length>=8&&batches.size>=2?s:null;
 },240000);
 const analysis=state.decisions.map(({symbol,venue,market,strategy,block_code})=>({symbol,venue,market,strategy,block_code}));
 assert((await call('/command',{kind:'pause',payload:{}})).ok);
 const paused=await call('/snapshot');assert(paused.execution.entry_gate.blocked);
 fs.writeFileSync(path.join(artifacts,'universe-engine-results.json'),JSON.stringify({version:state.version,time:new Date().toISOString(),packaged:!source,source:'Actual public exchange catalogs, quotes and closed candles; isolated virtual account, local language model disabled',universe:state.universe,quotes:state.markets.length,streams:state.markets.filter(q=>state.timestamp-(q.stream_observed||0)<15).length,analysisCount:analysis.length,analyzedSymbols:[...new Set(analysis.map(d=>d.symbol))],trainedContexts:state.learning.filter(x=>x.version).length,rotatingBatches:batches.size,sessionPreserved:true,balancePreserved:true,riskPreserved:true,initialBalance:initial.metrics.initial,positions:state.positions.length,closed:state.closed.length,paused:!paused.running,analyses:analysis},null,2));
 await call('/shutdown',{});await until(()=>child.exitCode!==null,20000);
 console.log('PASS broad actual universe: discovery, batch quotes, rotating new-coin analysis, background models, preserved account/risk.');
}finally{if(child.exitCode===null)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
