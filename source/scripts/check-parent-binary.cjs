const {spawn,spawnSync}=require('node:child_process');
const path=require('node:path');const fs=require('node:fs');const crypto=require('node:crypto');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');const dir=path.join(root,'artifacts','parent-binary-'+Date.now());
const binary=process.argv[2]||path.join(root,'engine-dist/kripto-engine/kripto-engine.exe');
const token=crypto.randomBytes(32).toString('hex');let child;
async function waitFor(fn,timeout=60000){const start=Date.now();while(Date.now()-start<timeout){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out');}
async function launch(){
 child=spawn(binary,['--data-dir',dir],{windowsHide:true,env:{...process.env,KRIPTO_DISABLE_LOCAL_AI:'1'},stdio:['pipe','pipe','pipe']});
 let out='',err='';child.stdout.on('data',x=>out+=x);child.stderr.on('data',x=>err+=x);
 child.stdin.write(JSON.stringify({token,watch_parent:true})+'\n');
 const ready=await waitFor(()=>out.match(/KRIPTO_READY (\{[^\n]+\})/));
 const base='http://127.0.0.1:'+JSON.parse(ready[1]).port;
 const call=async(route,body)=>{const r=await fetch(base+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});assert(r.ok,err);return r.json();};
 await waitFor(async()=>{try{return(await call('/health')).ok;}catch{return false;}});
 return call;
}
(async()=>{try{
 let call=await launch();
 const job=await call('/jobs',{kind:'backtest',source:'DEMO',strategy:'intraday',symbol:'BTCUSDT',venue:'Binance',market:'spot',months:7});assert(job.ok);
 await waitFor(async()=>{const item=(await call('/snapshot')).jobs.find(j=>j.id===job.id);if(item.status==='error')throw Error(item.message);return item.status==='done';},60000);
 assert.equal((await call('/report/'+job.id)).execution_model,'bar-causal-v2');
 assert((await call('/command',{kind:'start',payload:{}})).ok);
 const initial=await call('/snapshot');assert(initial.running);
 const start=Date.now();child.stdin.end();await waitFor(()=>child.exitCode!==null,15000);
 const elapsed=Date.now()-start;assert.equal(child.exitCode,0,'Owner loss must pause durably before successful exit');
 call=await launch();const restored=await call('/snapshot');assert.equal(restored.version,'0.8.0');assert.equal(restored.running,false);assert.equal(restored.session.id,initial.session.id);assert.equal(restored.metrics.initial,initial.metrics.initial);
 await call('/shutdown',{});await waitFor(()=>child.exitCode!==null,15000);
 fs.writeFileSync(path.join(root,'artifacts/parent-binary-results.json'),JSON.stringify({version:restored.version,time:new Date().toISOString(),ownerEOF:true,ownershipResearchWorker:true,exitMilliseconds:elapsed,exitCode:0,restartSameDirectory:true,restartPaused:true,accountPreserved:true,normalShutdownWithPipeOpen:true},null,2));
 console.log('PASS: frozen engine ownership, durable pause, bounded exit, lock release and same-account restart.');
}finally{if(child?.exitCode===null)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
